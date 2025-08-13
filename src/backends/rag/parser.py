import asyncio
import base64
import hashlib
from typing import Any

import aiohttp
import filetype
from fastapi import HTTPException
from kreuzberg import extract_bytes
from kreuzberg._mime_types import EXT_TO_MIME_TYPE
from loguru import logger

from ..user_config.models import UserConfig, load_config_from_env


def generate_file_hash(pdf_bytes: bytes) -> str:
    """Generate SHA256 hash of PDF file bytes."""
    return hashlib.sha256(pdf_bytes).hexdigest()


class LocalParser:
    """Parser class for PDF documents using kreuzberg library."""

    async def extract_full_text_from_bytes(self, pdf_bytes: bytes, filename: str = None) -> str:
        """Extract full text content from raw PDF bytes using single-threaded async processing."""
        try:
            # Small delay to yield control to event loop
            await asyncio.sleep(0.001)

            kind = filetype.guess_extension(pdf_bytes)
            mime_type = EXT_TO_MIME_TYPE.get("." + kind, "text/plain")
            result = await extract_bytes(pdf_bytes, mime_type=mime_type)
            fulltext = result.content

            return fulltext

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error extracting full text from PDF{f': {filename}' if filename else ''}: {str(e)}")
            return None


def get_parser_from_config(config: UserConfig = None):
    """
    Get a parser instance based on user configuration.
    """
    if config is None:
        config = load_config_from_env()

    if config.pdf_parser_type == "remote":
        return ParserServer(config.pdf_parser_url or "http://127.0.0.1:24008")
    else:
        return LocalParser()


async def extract_full_text_from_bytes(
    pdf_bytes: bytes,
    filename: str = None,
    config: UserConfig = None,
    use_remote: bool = None,
    remote_server_url: str = None,
    remote_options: dict[str, Any] = None,
    file_hash: str = None,
    title: str = None,
) -> str:
    """
    Extract full text content from raw PDF bytes.

    Args:
        pdf_bytes: Raw PDF bytes
        filename: Optional filename for logging
        config: UserConfig instance (preferred way to specify parser)
        use_remote: If True, use Parser Server; if False, use Kreuzberg parser (local)
        remote_server_url: URL for Parser Server server (legacy)
        remote_options: Options for Parser Server processing (legacy)

    Returns:
        Extracted text content (plain text for Kreuzberg, markdown for Parser Server)
    """

    selected_parser = get_parser_from_config(config)
    is_remote = config.pdf_parser_type == "remote"
    options = remote_options

    try:
        if is_remote:
            # Import here to avoid circular imports
            if not isinstance(selected_parser, ParserServer):
                selected_parser = ParserServer(remote_server_url or "http://127.0.0.1:24008")

            # Parser Server returns markdown
            if not file_hash:
                file_hash = generate_file_hash(pdf_bytes)

            if not title:
                title = filename

            # Process with Parser Server using hash as key
            content = await selected_parser.process_pdf(pdf_bytes, file_hash, options)
            return content
        else:
            # Local parser returns plain text
            return await selected_parser.extract_full_text_from_bytes(pdf_bytes, filename)
    finally:
        if is_remote and hasattr(selected_parser, "close"):
            await selected_parser.close()


async def extract_full_text_from_bytes_with_config(
    pdf_bytes: bytes, filename: str = None, config_id: str = "default"
) -> str:
    """Extract full text using configuration-based parser selection."""
    from ..user_config.models import load_config_from_db

    config = await load_config_from_db(config_id)
    return await extract_full_text_from_bytes(pdf_bytes, filename, config=config)


# =====================================================
# Parser Server
# =====================================================


class ParserServerError(Exception):
    """Custom exception for Parser Server errors with better categorization."""

    def __init__(self, message: str, error_type: str = "unknown", status_code: int = 500):
        self.message = message
        self.error_type = error_type
        self.status_code = status_code
        super().__init__(message)


class ParserServer:
    """Generic Parser Server for servers implementing /predict and /download endpoints."""

    def __init__(self, server_url: str = "http://127.0.0.1:24008"):
        self.server_url = server_url.rstrip("/")
        self.session = None

    async def _get_session(self):
        """Get or create aiohttp session."""
        if self.session is None:
            # More patient timeouts for AI-powered processing, but fail fast on connection
            timeout = aiohttp.ClientTimeout(
                total=None,  # No total timeout - let server decide when processing is done
                connect=5,  # Fail fast if the parser server is not reachable
                sock_read=None,  # No read timeout - some AI processing can take very long
            )
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def close(self):
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None

    async def process_pdf(
        self, pdf_bytes: bytes, file_key: str | None = None, options: dict[str, Any] | None = None
    ) -> str:
        """
        Process PDF using remote server and retrieve markdown text.

        Args:
            pdf_bytes: Raw PDF bytes
            file_key: Optional unique identifier for the file
            options: Optional processing options for the Parser Server

        Returns:
            Markdown content as string

        Raises:
            ParserServerError: With specific error type and message for frontend handling
        """
        # Validate PDF bytes first
        if not pdf_bytes or len(pdf_bytes) < 10:
            raise ParserServerError("Invalid or empty PDF bytes provided", error_type="invalid_input", status_code=400)

        if not pdf_bytes.startswith(b"%PDF"):
            raise ParserServerError(
                "Invalid PDF format - file does not appear to be a valid PDF",
                error_type="invalid_pdf",
                status_code=400,
            )

        try:
            # Step 1: Send PDF to /predict endpoint
            prediction_result = await self._call_predict(pdf_bytes, file_key, options)

            # Step 2: Extract file key from result
            extracted_file_key = self._extract_file_key(prediction_result, file_key)

            # Step 3: Retrieve markdown from /download endpoint
            markdown_content = await self._call_download(extracted_file_key)

            return markdown_content

        except ParserServerError:
            # Re-raise our custom errors as-is
            raise
        except (TimeoutError, aiohttp.ClientError) as e:
            logger.error(f"Network error with Parser Server at {self.server_url}: {str(e)}")
            raise ParserServerError(
                f"Cannot connect to Parser Server server at {self.server_url}. "
                f"Please check if the server is running and accessible. Error: {str(e)}",
                error_type="connection_error",
                status_code=502,
            )
        except Exception as e:
            logger.error(f"Unexpected error processing PDF with Parser Server: {str(e)}")
            raise ParserServerError(
                f"Parser Server encountered an unexpected error: {str(e)}",
                error_type="processing_error",
                status_code=500,
            )

    async def _call_predict(
        self, pdf_bytes: bytes, file_key: str | None = None, options: dict[str, Any] | None = None
    ) -> dict[str, str]:
        """
        Call /predict endpoint to submit PDF for processing.

        Returns:
            Dictionary with processing result information
        """
        try:
            session = await self._get_session()

            # Encode PDF to base64
            file_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

            # Default options optimized for best results
            default_options = {
                "backend": "pipeline",
                "method": "auto",
                "lang": "en",
                "formula_enable": True,
                "table_enable": True,
            }

            # Use provided options if any, otherwise use defaults
            if options:
                default_options.update(options)

            payload = {"file": file_b64, "options": default_options}

            if file_key:
                payload["file_key"] = file_key

            async with session.post(f"{self.server_url}/predict", json=payload) as response:
                if response.status == 200:
                    result = await response.json(encoding="utf-8")
                    logger.info("Parser Server successfully processed PDF")
                    return result
                else:
                    error_text = await response.text(encoding="utf-8")
                    logger.error(f"Parser Server /predict failed: {response.status} - {error_text}")

                    # Parse error message for better user feedback
                    if "Data format error" in error_text:
                        raise ParserServerError(
                            "The PDF file format is corrupted or not supported by the Parser Server. "
                            "Please try using Kreuzberg parser instead.",
                            error_type="unsupported_pdf",
                            status_code=400,
                        )
                    elif "NoneType" in error_text:
                        raise ParserServerError(
                            "Parser Server server configuration error. "
                            "Please contact the administrator or try Kreuzberg parser.",
                            error_type="server_config_error",
                            status_code=502,
                        )
                    else:
                        raise ParserServerError(
                            f"Parser Server server returned error: {error_text}. "
                            f"Status: {response.status}. Consider using Kreuzberg parser instead.",
                            error_type="server_error",
                            status_code=response.status,
                        )

        except ParserServerError:
            raise
        except (TimeoutError, aiohttp.ClientError) as e:
            raise ParserServerError(
                f"Failed to connect to Parser Server at {self.server_url}: {str(e)}",
                error_type="connection_error",
                status_code=502,
            )

    def _extract_file_key(self, prediction_result: dict[str, str], original_file_key: str | None) -> str:
        """Extract file key from prediction result."""
        if "markdown_route" in prediction_result:
            # Extract file key from the markdown route: /download/{file_key}/file.md
            route_parts = prediction_result["markdown_route"].split("/")
            if len(route_parts) >= 3:
                return route_parts[2]
            else:
                raise ParserServerError(
                    f"Parser Server returned invalid response format. Route: {prediction_result['markdown_route']}",
                    error_type="invalid_response",
                    status_code=502,
                )
        elif original_file_key:
            return original_file_key
        else:
            raise ParserServerError(
                "Parser Server did not return a file key for retrieving results",
                error_type="missing_file_key",
                status_code=502,
            )

    async def _call_download(self, file_key: str) -> str:
        """
        Call /download endpoint to retrieve processed markdown content.

        Args:
            file_key: File key returned from processing

        Returns:
            Markdown content as string
        """
        try:
            session = await self._get_session()

            # URL encode the file_key to handle special characters
            from urllib.parse import quote

            encoded_file_key = quote(file_key, safe="")

            # More patient retry logic - some PDFs take longer to process
            delays = [1, 2, 3, 5, 8, 10, 15, 20, 30]  # Up to ~97s total wait

            for attempt, delay in enumerate(delays):
                if attempt > 0:  # Skip delay on first attempt
                    await asyncio.sleep(delay)

                markdown_url = f"{self.server_url}/download/{encoded_file_key}/file.md"

                async with session.get(markdown_url) as response:
                    if response.status == 200:
                        markdown_content = await response.text()

                        if markdown_content and markdown_content.strip():
                            logger.info(f"Successfully downloaded markdown content ({len(markdown_content)} chars)")
                            return markdown_content
                        else:
                            # Continue retrying for empty content - it might just need more time
                            continue
                    elif response.status == 404:
                        # File not ready yet, continue retrying
                        continue
                    else:
                        error_text = await response.text()
                        # For 4xx/5xx errors (except 404), don't keep retrying
                        if response.status >= 400 and response.status < 500 and response.status != 404:
                            raise ParserServerError(
                                f"Download failed with client error {response.status}: {error_text}",
                                error_type="download_error",
                                status_code=response.status,
                            )

            # All attempts failed
            raise ParserServerError(
                f"Failed to retrieve processed content from Parser Server after {len(delays)} attempts. "
                f"The server may be overloaded or the file processing failed. "
                f"URL attempted: {self.server_url}/download/{encoded_file_key}/file.md",
                error_type="download_timeout",
                status_code=408,
            )

        except ParserServerError:
            raise
        except (TimeoutError, aiohttp.ClientError) as e:
            raise ParserServerError(
                f"Network error while downloading results: {str(e)}",
                error_type="download_error",
                status_code=502,
            )
