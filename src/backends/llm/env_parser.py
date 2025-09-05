"""
Robust Environment Variable Parsing System

Provides validation, type conversion, and fallback logic for environment variables.
"""

import os
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from loguru import logger


class EnvVarConfig:
    """Configuration for an environment variable."""

    def __init__(
        self,
        name: str,
        type_: type = str,
        required: bool = False,
        default: Any = None,
        validator: Optional[Callable[[Any], bool]] = None,
        description: str = "",
    ):
        self.name = name
        self.type_ = type_
        self.required = required
        self.default = default
        self.validator = validator
        self.description = description


class EnvVarParser:
    """Robust environment variable parser with validation and type conversion."""

    # Predefined configurations for common environment variables
    ENV_CONFIGS = {
        "OLLAMA_API_BASE": EnvVarConfig(
            name="OLLAMA_API_BASE",
            type_=str,
            required=False,
            default="http://localhost:11434",
            validator=lambda x: _validate_url(x),
            description="Ollama server base URL"
        ),
        "OPENAI_API_KEY": EnvVarConfig(
            name="OPENAI_API_KEY",
            type_=str,
            required=False,
            validator=lambda x: _validate_openai_key(x),
            description="OpenAI API key"
        ),
        "OPENAI_BASE_URL": EnvVarConfig(
            name="OPENAI_BASE_URL",
            type_=str,
            required=False,
            validator=lambda x: _validate_url(x),
            description="OpenAI API base URL"
        ),
        "ANTHROPIC_API_KEY": EnvVarConfig(
            name="ANTHROPIC_API_KEY",
            type_=str,
            required=False,
            validator=lambda x: _validate_anthropic_key(x),
            description="Anthropic API key"
        ),
        "AZURE_OPENAI_API_KEY": EnvVarConfig(
            name="AZURE_OPENAI_API_KEY",
            type_=str,
            required=False,
            description="Azure OpenAI API key"
        ),
        "AZURE_OPENAI_ENDPOINT": EnvVarConfig(
            name="AZURE_OPENAI_ENDPOINT",
            type_=str,
            required=False,
            validator=lambda x: _validate_url(x),
            description="Azure OpenAI endpoint"
        ),
        "GOOGLE_API_KEY": EnvVarConfig(
            name="GOOGLE_API_KEY",
            type_=str,
            required=False,
            description="Google API key"
        ),
        "HOSTED_VLLM_API_BASE": EnvVarConfig(
            name="HOSTED_VLLM_API_BASE",
            type_=str,
            required=False,
            validator=lambda x: _validate_url(x),
            description="Hosted VLLM API base URL"
        ),
        "HOSTED_VLLM_API_KEY": EnvVarConfig(
            name="HOSTED_VLLM_API_KEY",
            type_=str,
            required=False,
            description="Hosted VLLM API key"
        ),
        "REQUEST_TIMEOUT": EnvVarConfig(
            name="REQUEST_TIMEOUT",
            type_=int,
            required=False,
            default=60,
            validator=lambda x: isinstance(x, int) and x > 0,
            description="Request timeout in seconds"
        ),
        "MAX_RETRIES": EnvVarConfig(
            name="MAX_RETRIES",
            type_=int,
            required=False,
            default=3,
            validator=lambda x: isinstance(x, int) and x >= 0,
            description="Maximum number of retries"
        ),
    }

    @classmethod
    def parse_env_var(cls, name: str, config: Optional[EnvVarConfig] = None) -> Any:
        """
        Parse an environment variable with validation and type conversion.

        Args:
            name: Environment variable name
            config: Configuration for the variable (uses predefined if None)

        Returns:
            Parsed and validated value

        Raises:
            ValueError: If validation fails or required variable is missing
        """
        if config is None:
            config = cls.ENV_CONFIGS.get(name)
            if config is None:
                # Fallback for unknown variables - treat as optional string
                config = EnvVarConfig(name=name, type_=str, required=False)

        value = os.environ.get(name)

        if value is None:
            if config.required:
                raise ValueError(f"Required environment variable {name} not set")
            if config.default is not None:
                logger.debug(f"Using default value for {name}: {config.default}")
                return config.default
            return None

        try:
            # Type conversion
            parsed_value = cls._convert_type(value, config.type_)

            # Validation
            if config.validator and not config.validator(parsed_value):
                raise ValueError(f"Environment variable {name} failed validation: {parsed_value}")

            logger.debug(f"Successfully parsed {name}: {parsed_value}")
            return parsed_value

        except (ValueError, TypeError) as e:
            error_msg = f"Invalid value for {name}: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    @classmethod
    def _convert_type(cls, value: str, target_type: type) -> Any:
        """Convert string value to target type."""
        if target_type == bool:
            return value.lower() in ('true', '1', 'yes', 'on', 'enabled')
        elif target_type == int:
            return int(value)
        elif target_type == float:
            return float(value)
        elif target_type == str:
            return value
        else:
            # For custom types, try direct conversion
            return target_type(value)

    @classmethod
    def get_provider_credentials(cls, provider: str) -> dict[str, Any]:
        """
        Get credentials for a specific provider with robust parsing.

        Args:
            provider: Provider name (ollama, openai, anthropic, etc.)

        Returns:
            Dictionary of credentials and configuration
        """
        credentials = {}

        try:
            if provider == "ollama":
                base_url = cls.parse_env_var("OLLAMA_API_BASE")
                if base_url:
                    credentials["api_base"] = base_url

            elif provider == "openai":
                api_key = cls.parse_env_var("OPENAI_API_KEY")
                base_url = cls.parse_env_var("OPENAI_BASE_URL")
                if api_key:
                    credentials["api_key"] = api_key
                if base_url:
                    credentials["api_base"] = base_url

            elif provider == "anthropic":
                api_key = cls.parse_env_var("ANTHROPIC_API_KEY")
                if api_key:
                    credentials["api_key"] = api_key

            elif provider == "azure":
                api_key = cls.parse_env_var("AZURE_OPENAI_API_KEY")
                endpoint = cls.parse_env_var("AZURE_OPENAI_ENDPOINT")
                if api_key:
                    credentials["api_key"] = api_key
                if endpoint:
                    credentials["api_base"] = endpoint

            elif provider == "google":
                api_key = cls.parse_env_var("GOOGLE_API_KEY")
                if api_key:
                    credentials["api_key"] = api_key

            elif provider == "hosted_vllm":
                base_url = cls.parse_env_var("HOSTED_VLLM_API_BASE")
                api_key = cls.parse_env_var("HOSTED_VLLM_API_KEY") or cls.parse_env_var("OPENAI_API_KEY")
                if base_url:
                    credentials["api_base"] = base_url
                if api_key:
                    credentials["api_key"] = api_key

            # Add common settings
            timeout = cls.parse_env_var("REQUEST_TIMEOUT")
            if timeout:
                credentials["timeout"] = timeout

            max_retries = cls.parse_env_var("MAX_RETRIES")
            if max_retries:
                credentials["max_retries"] = max_retries

            logger.info(f"Loaded credentials for {provider}: {list(credentials.keys())}")
            return credentials

        except ValueError as e:
            logger.error(f"Failed to load credentials for {provider}: {e}")
            raise


# Validation helper functions
def _validate_url(url: str) -> bool:
    """Validate URL format."""
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
    except Exception:
        return False


def _validate_openai_key(key: str) -> bool:
    """Validate OpenAI API key format."""
    return isinstance(key, str) and len(key) > 20 and key.startswith('sk-')


def _validate_anthropic_key(key: str) -> bool:
    """Validate Anthropic API key format."""
    return isinstance(key, str) and len(key) > 20 and key.startswith('sk-ant-')
