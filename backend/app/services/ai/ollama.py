from typing import Protocol
import httpx
from pydantic import BaseModel, ConfigDict, Field


class AIResult(BaseModel):
    model: str
    response: str
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)


class AIProvider(Protocol):
    async def generate(self, prompt: str) -> AIResult: ...


class OllamaResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    model: str
    response: str
    done: bool
    prompt_eval_count: int = Field(default=0, ge=0)
    eval_count: int = Field(default=0, ge=0)


class OllamaProvider:
    def __init__(self, client: httpx.AsyncClient, model: str):
        self.client, self.model = client, model

    async def generate(self, prompt: str) -> AIResult:
        response = await self.client.post("/api/generate", json={
            "model": self.model, "prompt": prompt, "stream": False,
            "options": {"num_predict": 512},
        })
        response.raise_for_status()
        data = OllamaResponse.model_validate(response.json())
        if not data.done:
            raise ValueError("Incomplete Ollama response")
        return AIResult(model=data.model, response=data.response,
                        prompt_tokens=data.prompt_eval_count, completion_tokens=data.eval_count)
