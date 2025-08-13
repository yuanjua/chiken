from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..manager_singleton import ManagerSingleton
from ..user_config import UserConfig
from .service import LLMService

# Router setup
router = APIRouter(prefix="/llm", tags=["LLM"])


class LLMConfigResponse(BaseModel):
    """Response model for LLM configuration."""

    provider: str
    model_name: str
    embed_model: str | None = None
    embed_provider: str | None = None
    temperature: float
    num_ctx: int
    base_url: str | None = None
    api_key: str | None = None
    available_models: list[str] = Field(default_factory=list)


class OllamaModelResponse(BaseModel):
    """Response model for Ollama model list."""

    models: list[dict[str, Any]]
    count: int
    timestamp: str


class SetProviderBaseUrlRequest(BaseModel):
    """Request model for setting provider base URL."""

    provider: str
    base_url: str


class SetModelParamsRequest(BaseModel):
    """Request model for setting model parameters."""

    model_name: str
    temperature: float | None = None
    num_ctx: int | None = None
    embedding_model: str | None = None
    base_url: str | None = None
    api_key: str | None = None


class OllamaModelListRequest(BaseModel):
    base_url: str


@router.get("/providers")
async def get_providers():
    """Get list of available providers."""
    providers = LLMService.get_available_providers()
    return {"providers": providers}


@router.get("/config", response_model=LLMConfigResponse)
async def get_llm_config(config: UserConfig = Depends(ManagerSingleton.get_user_config)):
    """Get current LLM configuration."""
    config_data = await LLMService.get_llm_config(config)
    return LLMConfigResponse(**config_data)


@router.get("/models")
async def get_model_list(config: UserConfig = Depends(ManagerSingleton.get_user_config)):
    """Get list of available models for the current provider."""
    return await LLMService.get_provider_model_list(config)


@router.get("/models/ollama", response_model=OllamaModelResponse)
async def get_ollama_model_list():
    """Get list of available Ollama models."""
    model_data = await LLMService.get_ollama_model_list()
    return OllamaModelResponse(**model_data)


@router.get("/models/suggestions/{provider}")
async def get_model_suggestions(
    provider: str,
    partial_model: str = "",
    base_url: str | None = None,
    config: UserConfig = Depends(ManagerSingleton.get_user_config),
):
    """Get model completion suggestions for a provider."""
    suggestions = await LLMService.get_model_completion_suggestions(provider, partial_model, base_url)
    return {
        "provider": provider,
        "suggestions": suggestions,
        "count": len(suggestions),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/models/litellm")
async def get_litellm_models():
    """Get all models supported by LiteLLM."""
    models = LLMService.get_litellm_model_list()
    return {
        "models": models,
        "count": len(models),
        "source": "litellm",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/models/litellm/{provider}")
async def get_litellm_provider_models(provider: str):
    """Get models for a specific provider from LiteLLM."""
    models = LLMService.get_litellm_models_by_provider(provider)
    return {
        "provider": provider,
        "models": models,
        "count": len(models),
        "source": "litellm",
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/model/params")
async def set_model_params(
    request: SetModelParamsRequest, config: UserConfig = Depends(ManagerSingleton.get_user_config)
):
    """Set model parameters and update configuration."""
    updates = {}
    if request.model_name:
        updates["model_name"] = request.model_name
    if request.base_url is not None:
        updates["base_url"] = request.base_url
    if request.api_key is not None:
        updates["api_key"] = request.api_key
    if request.embedding_model is not None:
        updates["embed_model"] = request.embedding_model
    if request.temperature is not None:
        updates["temperature"] = request.temperature
    if request.num_ctx is not None:
        updates["num_ctx"] = request.num_ctx

    return await LLMService.set_model_params(config, updates)
