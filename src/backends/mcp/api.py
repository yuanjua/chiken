"""
MCP API

Provides API endpoints for MCP server configuration and management.
"""

import asyncio
import multiprocessing
import os
import signal
import sys
from typing import Any

from fastapi import APIRouter, Body, HTTPException
from loguru import logger
from pydantic import BaseModel


# Import with lazy loading to avoid circular imports
def get_manager_singleton():
    from ..manager_singleton import ManagerSingleton

    return ManagerSingleton


# This function must be at the top level of the module to be pickleable by multiprocessing
def mcp_process_target(params: dict[str, Any]):
    """The target function that runs the MCP server in a separate process."""
    # Imports must be inside the function for the new process
    from loguru import logger

    from .kb_mcp_server import mcp

    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"MCP process received signal {signum}, shutting down gracefully...")
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # On Unix systems, set up a new process group to ensure proper signal propagation
    if hasattr(os, "setpgrp"):
        try:
            os.setpgrp()
        except OSError:
            pass  # Ignore if already a process group leader

    transport = params.get("transport", "stdio")
    port = params.get("port", 8000)

    try:
        logger.info(f"MCP process started with transport: {transport}, port: {port}")
        if transport == "stdio":
            mcp.run(transport="stdio")
        elif transport in ("streamable-http", "http", "streamableHttp"):
            mcp.run(transport="http", port=port)
        elif transport == "sse":
            mcp.run(transport="sse", port=port)
        else:
            mcp.run(transport="stdio")
    except Exception as e:
        logger.error(f"MCP server process encountered an error: {e}")
    finally:
        logger.info("MCP server process finished.")


class MCPServerManager:
    """Manages the lifecycle of the MCP server process."""

    def __init__(self):
        self.process: multiprocessing.Process | None = None
        self.is_running: bool = False
        self._monitor_task: asyncio.Task | None = None

    async def start(self, params: dict[str, Any]):
        """Starts the MCP server in a separate process."""
        if self.is_running:
            logger.info("MCP server is already running. Stopping it first...")
            await self.stop()

        if params.get("transport") == "stdio":
            logger.info("MCP transport is 'stdio', server will not be started as a separate process.")
            return

        logger.info(f"🚀 Starting MCP server with parameters: {params}")

        self.process = multiprocessing.Process(
            target=mcp_process_target, args=(params,), name="mcp_server_process", daemon=False
        )
        self.process.start()
        self.is_running = True
        logger.info(f"MCP server process started with PID: {self.process.pid}")

        if self._monitor_task:
            self._monitor_task.cancel()
        self._monitor_task = asyncio.create_task(self._monitor_process())

    async def stop(self):
        """Stops the MCP server process."""
        if not self.is_running or not self.process:
            logger.info("MCP server is not running.")
            return

        logger.info("🛑 Stopping MCP server process...")
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None

        if self.process.is_alive():
            try:
                logger.info(f"Sending SIGTERM to MCP process (PID: {self.process.pid})...")
                self.process.terminate()
                self.process.join(timeout=5)

                if self.process.is_alive():
                    logger.warning("MCP server did not terminate gracefully. Sending SIGKILL...")
                    self.process.kill()
                    self.process.join(timeout=2)
            except Exception as e:
                logger.error(f"Exception during MCP server shutdown: {e}")

        self.is_running = False
        self.process = None
        logger.info("✅ MCP server stopped.")

    async def restart(self):
        """Restarts the MCP server with the current configuration."""
        logger.info("MCP server restart requested")
        ManagerSingleton = get_manager_singleton()
        user_config = await ManagerSingleton.get_user_config()
        config_params = {"transport": user_config.mcp_transport, "port": user_config.mcp_port}
        await self.start(config_params)
        return config_params

    async def _monitor_process(self):
        """Monitors the MCP process and cleans up state if it dies unexpectedly."""
        while self.is_running and self.process:
            if not self.process.is_alive():
                logger.warning(f"MCP process (PID: {self.process.pid}) died unexpectedly. Cleaning up.")
                self.is_running = False
                self.process = None
                break
            await asyncio.sleep(5)

    def get_status(self) -> dict[str, Any]:
        """Returns the current status of the MCP server."""
        if self.is_running and self.process and not self.process.is_alive():
            logger.warning("MCP server process found to be dead. Cleaning up state.")
            self.is_running = False
            self.process = None
        return {"is_running": self.is_running}


# Singleton instance of the MCP manager
mcp_manager = MCPServerManager()

# Router setup
router = APIRouter(prefix="/mcp", tags=["MCP Control"])


# Request/Response Models
class MCPConfigRequest(BaseModel):
    """Request model for MCP configuration updates."""

    transport: str | None = None
    port: int | None = None


class MCPConfigResponse(BaseModel):
    """Response model for MCP configuration."""

    transport: str
    port: int | None


# MCP Configuration Endpoints
@router.get("/config", response_model=MCPConfigResponse)
async def get_mcp_configuration():
    """Get the current MCP configuration."""
    try:
        ManagerSingleton = get_manager_singleton()
        user_config = await ManagerSingleton.get_user_config()
        return MCPConfigResponse(transport=user_config.mcp_transport, port=user_config.mcp_port)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get MCP configuration: {str(e)}")


@router.post("/config")
async def update_mcp_configuration(request: MCPConfigRequest):
    """Update the MCP configuration."""
    try:
        field_mapping = {"transport": "mcp_transport", "port": "mcp_port"}
        updates = {field_mapping.get(k, k): v for k, v in request.dict().items() if v is not None}

        if not updates:
            raise HTTPException(status_code=400, detail="No valid updates provided")

        logger.info(f"MCP config updates to apply: {updates}")
        ManagerSingleton = get_manager_singleton()
        updated_config = await ManagerSingleton.update_user_config(**updates)

        logger.info(
            f"MCP config after update: transport={updated_config.mcp_transport}, port={updated_config.mcp_port}"
        )

        # Trigger a restart of the MCP server to apply the new settings
        await mcp_manager.restart()

        return {
            "success": True,
            "message": "MCP configuration updated and server restarted.",
            "transport": updated_config.mcp_transport,
            "port": updated_config.mcp_port,
        }
    except Exception as e:
        logger.error(f"Failed to update MCP configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update MCP configuration: {str(e)}")


@router.post("/start")
async def start_mcp(params: dict[str, Any] = Body(None, embed=True)):
    """Starts the MCP server with specific parameters."""
    run_params = params or {}
    await mcp_manager.start(run_params)
    return {"message": "MCP server start command issued.", "params": run_params}


@router.post("/stop")
async def stop_mcp():
    """Stops the currently running MCP server."""
    if not mcp_manager.is_running:
        raise HTTPException(status_code=404, detail="MCP server is not running.")
    await mcp_manager.stop()
    return {"message": "MCP server stopped."}


@router.get("/status")
async def get_mcp_status():
    """Returns the current status of the MCP server."""
    return mcp_manager.get_status()


@router.post("/restart")
async def restart_mcp_server():
    """Restart the MCP server with current configuration."""
    try:
        restarted_config = await mcp_manager.restart()
        return {
            "success": True,
            "message": "MCP server restarted successfully",
            "config": restarted_config,
        }
    except Exception as e:
        logger.error(f"Failed to restart MCP server: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to restart MCP server: {str(e)}")
