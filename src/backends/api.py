from fastapi import APIRouter

from .agents.api import router as agents_router
from .llm.api import router as llm_router
from .mcp.api import router as mcp_router
from .rag.api import router as rag_router
from .sessions.api import router as sessions_router
from .user_config.api import router as config_router
from .zotero.api import router as zotero_router

router = APIRouter()
router.include_router(llm_router)
router.include_router(rag_router)
router.include_router(sessions_router)
router.include_router(config_router, prefix="/config")
router.include_router(zotero_router)
router.include_router(agents_router)
router.include_router(mcp_router)


@router.get("/health")
async def health_check():
    return {"status": "healthy"}
