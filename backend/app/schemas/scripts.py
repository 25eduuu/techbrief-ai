from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContentCategory(str, Enum):
    AI_TOOLS = "AI_TOOLS"
    AI_NEWS = "AI_NEWS"
    PROGRAMMING = "PROGRAMMING"
    CLOUD = "CLOUD"
    CYBERSECURITY = "CYBERSECURITY"
    PRODUCTIVITY = "PRODUCTIVITY"
    SOFTWARE = "SOFTWARE"
    FREE_TOOLS = "FREE_TOOLS"
    TECH_NEWS = "TECH_NEWS"


class ScriptGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    topic: str = Field(min_length=3, max_length=240)
    brief: str | None = Field(default=None, min_length=10, max_length=2000)
    category: ContentCategory = ContentCategory.SOFTWARE
    language: str = Field(default="en", pattern=r"^[a-zA-Z]{2}$")
    target_duration: int = Field(default=45, ge=30, le=60)


class GeneratedScript(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    hook: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=4000)
    cta: str = Field(min_length=1, max_length=300)
    estimated_duration: int = Field(ge=30, le=60)
    visual_suggestions: list[str] = Field(min_length=1, max_length=8)
    caption: str = Field(min_length=1, max_length=1000)
    hashtags: list[str] = Field(min_length=3, max_length=12)

    @field_validator("hashtags")
    @classmethod
    def validate_hashtags(cls, hashtags: list[str]) -> list[str]:
        normalized: list[str] = []
        for hashtag in hashtags:
            clean = hashtag.strip().replace(" ", "_")
            if not clean:
                raise ValueError("hashtags cannot be empty")
            normalized.append(clean if clean.startswith("#") else f"#{clean}")
        return normalized
