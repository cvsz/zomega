from dataclasses import dataclass

@dataclass(frozen=True)
class ProviderResult:
    output: str
    provider_response_id: str
    input_tokens: int
    output_tokens: int
