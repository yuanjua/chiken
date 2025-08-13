from collections.abc import AsyncIterator
from typing import Any

from langchain_core.callbacks import AsyncCallbackManagerForLLMRun
from langchain_core.language_models.chat_models import agenerate_from_stream
from langchain_core.messages import AIMessageChunk, BaseMessage
from langchain_core.outputs import (
    ChatGenerationChunk,
    ChatResult,
)
from langchain_litellm.chat_models.litellm import (
    ChatLiteLLM,
    _convert_delta_to_message_chunk,
    _create_retry_decorator,
)


class LLM(ChatLiteLLM):
    """Customize"""

    num_ctx: int | None = 2000

    # Temporary override for ChatLiteLLM to fix issue:
    # https://github.com/Akshay-Dongare/langchain-litellm/issues/21
    # Also for passing num_ctx for Ollama
    async def acompletion_with_retry(
        self, run_manager: AsyncCallbackManagerForLLMRun | None = None, **kwargs: Any
    ) -> Any:
        """Use tenacity to retry the async completion call."""
        retry_decorator = _create_retry_decorator(self, run_manager=run_manager)

        @retry_decorator
        async def _completion_with_retry(**kwargs: Any) -> Any:
            return await self.client.acompletion(num_ctx=self.num_ctx, **kwargs)

        return await _completion_with_retry(**kwargs)

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        message_dicts, params = self._create_message_dicts(messages, stop)
        params = {**params, **kwargs, "stream": True}

        default_chunk_class = AIMessageChunk
        async for chunk in await self.acompletion_with_retry(messages=message_dicts, run_manager=run_manager, **params):
            if not isinstance(chunk, dict):
                chunk = chunk.model_dump()
            if len(chunk["choices"]) == 0:
                continue
            delta = chunk["choices"][0]["delta"]
            chunk = _convert_delta_to_message_chunk(delta, default_chunk_class)
            default_chunk_class = chunk.__class__
            cg_chunk = ChatGenerationChunk(message=chunk)
            if run_manager:
                await run_manager.on_llm_new_token(chunk.content, chunk=cg_chunk)
            yield cg_chunk

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        stream: bool | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        should_stream = stream if stream is not None else self.streaming
        if should_stream:
            stream_iter = self._astream(messages=messages, stop=stop, run_manager=run_manager, **kwargs)
            return await agenerate_from_stream(stream_iter)

        message_dicts, params = self._create_message_dicts(messages, stop)
        params = {**params, **kwargs}
        response = await self.acompletion_with_retry(messages=message_dicts, run_manager=run_manager, **params)
        return self._create_chat_result(response)
