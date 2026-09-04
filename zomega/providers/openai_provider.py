import json
from openai import AsyncOpenAI
from .types import ProviderResult
from ..config import settings

_client = AsyncOpenAI(api_key=settings.openai_api_key)

async def execute(instructions: str, context: dict) -> ProviderResult:
    response = await _client.responses.create(
        model=settings.openai_model,
        instructions=instructions,
        input=json.dumps(context, ensure_ascii=False),
        store=settings.openai_store,
    )
    usage = response.usage
    return ProviderResult(
        output=response.output_text,
        provider_response_id=response.id,
        input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
    )
