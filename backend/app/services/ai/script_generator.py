import json
import logging
import re

from pydantic import ValidationError

from app.schemas.scripts import GeneratedScript, ScriptGenerationRequest
from app.services.ai.ollama import AIProvider

logger = logging.getLogger(__name__)


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
            logger.warning(
                "Invalid generated script: %s; raw response: %r",
                str(exc), result.response[:4000],
            )
            raise ScriptGenerationError("Ollama returned an invalid script") from exc

    @staticmethod
    def _build_prompt(request: ScriptGenerationRequest) -> str:
        return f"""You are a short-form technology content writer.

Create one original faceless video script about: {request.topic}
Category: {request.category.value}
Language: {request.language}
Target duration: {request.target_duration} seconds
Additional factual brief: {request.brief or "No additional factual brief was provided."}

Return ONLY one valid JSON object. Do not use Markdown, code fences, or extra text.
Use exactly these keys:
hook, body, cta, estimated_duration, visual_suggestions, caption, hashtags

Requirements:
- hook must be attention-grabbing and specific;
- body must be clear, accurate, natural, and suitable for a voice-over;
- cta must invite a relevant action;
- estimated_duration must be an integer between 30 and 60 and close to the target duration;
- visual_suggestions must contain 1 to 8 concrete visual ideas;
- caption must be suitable for TikTok, Instagram Reels, and YouTube Shorts;
- hashtags must contain 3 to 12 hashtag strings, each beginning with '#';
- write like a native speaker of the requested language and proofread spelling and grammar;
- do not invent a product, tool, brand, feature, price, statistic, date, or news event;
- if the topic does not name a specific product, never invent a product name: say "questo strumento" or an equivalent generic phrase;
- do not claim that a tool replaces apps or solves a problem unless the topic explicitly supports that claim;
- do not mention a duration different from the target duration;
- treat the topic as the only source of factual information;
- when a factual brief is provided, use it as the only source for product details and claims;
- when no factual brief is provided, do not pretend to review a specific product and keep the script explicitly educational and generic;
- do not use unsupported hype such as "rivoluzionario", "rivoluzionare", "potrebbe cambiarti la vita", "il nostro strumento", or "clicca qui";
- do not call a generic topic "nuovo" unless the topic explicitly says it is new;
- for a generic topic without a named product, make the script educational and clearly generic instead of pretending to review a real product;
- use a truthful CTA such as saving the video, following the channel, or asking viewers to comment;
- avoid generic filler and avoid repeating the same hook pattern.
"""

    @staticmethod
    def _parse_json(raw: str) -> object:
        cleaned = raw.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            cleaned = fenced.group(1).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start, end = cleaned.find("{"), cleaned.rfind("}")
            if start < 0 or end <= start:
                raise
            return json.loads(cleaned[start:end + 1])
