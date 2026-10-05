import json
import re

from pydantic import ValidationError

from app.schemas.scripts import GeneratedScript, ScriptGenerationRequest
from app.services.ai.ollama import AIProvider


class ScriptGenerationError(ValueError):
    """Raised when the model does not return a valid script JSON object."""


class ScriptGenerator:
    def __init__(self, provider: AIProvider):
        self.provider = provider

    async def generate(self, request: ScriptGenerationRequest) -> GeneratedScript:
        result = await self.provider.generate(self._build_prompt(request))
        try:
            return GeneratedScript.model_validate(self._parse_json(result.response))
        except (json.JSONDecodeError, TypeError, ValidationError) as exc:
            raise ScriptGenerationError("Ollama returned an invalid script") from exc

    @staticmethod
    def _build_prompt(request: ScriptGenerationRequest) -> str:
        return f"""You are a short-form technology content writer.

Create one original faceless video script about: {request.topic}
Category: {request.category.value}
Language: {request.language}
Target duration: {request.target_duration} seconds

Return ONLY one valid JSON object. Do not use Markdown, code fences, or extra text.
Use exactly these keys:
hook, body, cta, estimated_duration, visual_suggestions, caption, hashtags

Requirements:
- hook must be attention-grabbing and specific;
- body must be clear, accurate, and suitable for a voice-over;
- cta must invite a relevant action;
- estimated_duration must be an integer between 30 and 60;
- visual_suggestions must contain 1 to 8 concrete visual ideas;
- caption must be suitable for TikTok, Instagram Reels, and YouTube Shorts;
- hashtags must contain 3 to 12 hashtag strings, each beginning with '#';
- do not invent precise claims, prices, features, or news if they are not supported by the topic.
"""

    @staticmethod
    def _parse_json(raw: str) -> object:
        cleaned = raw.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            cleaned = fenced.group(1).strip()
        return json.loads(cleaned)
