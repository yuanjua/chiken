import argparse
import asyncio
import multiprocessing
import os
import sys
import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from backends.api import router as api_router
from backends.manager_singleton import ManagerSingleton
from backends.mcp.api import mcp_manager  # Import the manager instance

# Load environment variables from keychain at startup
from backends.user_config.keychain_loader import load_env_from_keychain

loaded_env = load_env_from_keychain()
if loaded_env:
    logger.info(f"Loaded {len(loaded_env)} environment variables from keychain at startup")
else:
    logger.info("No environment variables loaded from keychain at startup")

# # Load environment variables
# load_dotenv(override=True)

# Global shutdown event and main loop reference
shutdown_event = asyncio.Event()
main_loop = None

# Set up loguru for console logging
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} {level} {name}: {message}",
    colorize=True,
)


def stdin_monitor():
    """Monitor stdin for closure and trigger shutdown when parent process exits."""
    global main_loop
    try:
        # This will block until stdin is closed (when parent process exits)
        for line in sys.stdin:
            # Process any commands from parent if needed
            # For now, we just ignore input
            pass
    except (EOFError, OSError):
        pass

    # When we reach here, stdin was closed (parent process exited)
    logger.warning("Stdin closed - parent process exited, initiating shutdown...")

    # Use the stored main loop reference for thread-safe shutdown
    if main_loop and not main_loop.is_closed():
        try:
            asyncio.run_coroutine_threadsafe(shutdown_event.set(), main_loop)
            logger.info("Shutdown event set successfully")
        except Exception as e:
            logger.error(f"Failed to set shutdown event: {e}")
            logger.warning("Forcing immediate exit")
            os._exit(0)
    else:
        logger.error("Main loop not available, forcing exit")
        os._exit(0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup, background tasks, and graceful shutdown.
    """
    global main_loop

    # ====== STARTUP ======
    logger.info("Application Starting Up")

    # Store the main event loop for thread-safe communication
    main_loop = asyncio.get_running_loop()
    logger.info("Main event loop stored for stdin monitoring")

    await ManagerSingleton.initialize()

    # Start the stdin monitor in a separate thread to watch for parent process exit
    stdin_thread = threading.Thread(target=stdin_monitor, daemon=True)
    stdin_thread.start()
    logger.info("Stdin monitor started.")

    # This coroutine waits for the external shutdown signal from the stdin_monitor
    async def shutdown_watcher():
        try:
            await shutdown_event.wait()
            logger.warning("Shutdown event from stdin detected. Cleanup will proceed in the 'finally' block.")
        except asyncio.CancelledError:
            pass  # Expected during normal shutdown

    # Create and start all long-running background tasks
    logger.info("Starting background services...")

    # Start MCP server with existing configuration
    logger.info("Starting MCP server with existing configuration...")
    try:
        user_config = await ManagerSingleton.get_user_config()
        config_params = {"transport": user_config.mcp_transport, "port": user_config.mcp_port}
        await mcp_manager.start(config_params)
        logger.info("MCP server start command issued.")
    except Exception as e:
        logger.error(f"Failed to start MCP server: {e}")

    watcher_task = asyncio.create_task(shutdown_watcher(), name="shutdown_watcher")
    background_tasks = [watcher_task]
    logger.info("Background services are running.")
    try:
        # Application is now running and ready to accept requests
        yield
    finally:
        # ====== SHUTDOWN ======
        # This block is the single source of truth for cleanup.
        # It runs on normal exit (CTRL+C) or when the shutdown_event is triggered.
        logger.info("Application Shutting Down")
        # Stop MCP server if running
        try:
            if mcp_manager.is_running:
                logger.info("Stopping MCP server...")
                await mcp_manager.stop()
        except Exception as e:
            logger.error(f"Error stopping MCP server: {e}")
        # Signal all background tasks to cancel.
        for task in background_tasks:
            task.cancel()
        # Wait for all tasks to acknowledge cancellation.
        await asyncio.gather(*background_tasks, return_exceptions=True)
        await ManagerSingleton.close_all()
        logger.info("Graceful shutdown complete.")
        # If shutdown was triggered by the parent process exiting, force this process to exit.
        if shutdown_event.is_set():
            logger.warning("Forcing exit after parent process closed.")
            os._exit(0)


app = FastAPI(
    title="Zotero Deep Researcher API",
    description="AI-powered research assistant with Zotero integration",
    version="0.2.0",
    lifespan=lifespan,
)

# Configure loguru for debug level on specific modules
logger.add(
    sys.stderr,
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} {level} {name}: {message}",
    filter=lambda record: record["name"] in ["backends.rag.service", "backends.rag.db", "uvicorn.access"],
    colorize=True,
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(https?://(localhost|127\.0\.0\.1|tauri\.localhost)(:\d+)?|tauri://localhost)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="")


@app.get("/")
async def root():
    return {"message": "ChiKen API is running", "version": "0.1.0"}


if __name__ == "__main__":
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(description="ChiKen API")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8009, help="Port to listen on")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--reload-dirs", type=str, default="src", help="Directories to watch for changes")
    parser.add_argument("--origins", type=str, default="http://localhost:3000", help="Origins to allow")
    parser.add_argument("--mcp", action="store_true", help="Start MCP server STDIO")

    args = parser.parse_args()
    reload = args.reload or os.getenv("DEBUG", "false").lower() in ["true", "1", "yes"]

    if args.mcp:
        from backends.mcp.kb_mcp_server import mcp

        mcp.run()

    elif reload:
        import litellm

        litellm._turn_on_debug()

        reload_dirs = args.reload_dirs.split(",") if args.reload_dirs else ["src"]
        uvicorn.run(
            "main:app",
            host=args.host,
            port=args.port,
            reload=True,
            reload_dirs=reload_dirs,
            log_level="debug",
            access_log=True,
        )

    else:
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
        )
