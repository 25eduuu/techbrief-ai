import asyncio
from unittest.mock import AsyncMock
import httpx
import pytest
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app
from app.services.ai.ollama import AIResult, OllamaProvider
from app.services.ai.script_generator import ScriptGenerationError, ScriptGenerator


def make_app(limit=6):
    settings = Settings(_env_file=None, database_url="postgresql+asyncpg://test:test@localhost/test",
                        api_key="x" * 32, ollama_model="test-model", ai_requests_per_minute=limit)
    app = create_app(settings)
    app.state.database = AsyncMock()
    app.state.ai = AsyncMock()
    app.state.ai.generate.return_value = AIResult(model="test-model", response="Tool A")
    return app


AUTH = {"X-API-Key": "x" * 32}


def test_health():
    app = make_app()
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}
    app.state.database.ping.side_effect = RuntimeError("secret")
    assert client.get("/health").status_code == 503


def test_auth_and_validation():
    app = make_app()
    client = TestClient(app)
    assert client.post("/api/ai/test", json={"prompt": "hello"}).status_code == 401
    for prompt in ["", "   ", "x" * 2001]:
        assert client.post("/api/ai/test", headers=AUTH, json={"prompt": prompt}).status_code == 422
    app.state.ai.generate.assert_not_awaited()


def test_generation_and_rate_limit():
    app = make_app(limit=1)
    client = TestClient(app)
    result = client.post("/api/ai/test", headers=AUTH, json={"prompt": "hello"})
    assert result.status_code == 200
    assert result.json()["response"] == "Tool A"
    assert client.post("/api/ai/test", headers=AUTH, json={"prompt": "hello"}).status_code == 429


@pytest.mark.parametrize("error,status", [(httpx.ReadTimeout("timeout"), 504),
    (httpx.ConnectError("offline"), 503), (ValueError("invalid"), 502)])
def test_provider_errors(error, status):
    app = make_app()
    app.state.ai.generate.side_effect = error
    assert TestClient(app).post("/api/ai/test", headers=AUTH, json={"prompt": "hello"}).status_code == status


def test_body_limit_and_cors():
    client = TestClient(make_app())
    assert client.post("/api/ai/test", headers=AUTH, content="x" * 17000).status_code == 413
    result = client.options("/api/ai/test", headers={"Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "X-API-Key"})
    assert result.status_code == 200
    assert result.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_ollama_wire_contract():
    async def run():
        def handler(request):
            import json
            payload = json.loads(request.content)
            assert payload["model"] == "custom-model"
            assert payload["stream"] is False
            assert request.url.path == "/api/generate"
            return httpx.Response(200, json={"model": "custom-model", "response": "Hello", "done": True,
                                             "prompt_eval_count": 3, "eval_count": 5})
        async with httpx.AsyncClient(base_url="http://ollama", transport=httpx.MockTransport(handler)) as client:
            result = await OllamaProvider(client, "custom-model").generate("hi")
            assert result.prompt_tokens == 3 and result.completion_tokens == 5
    asyncio.run(run())


def test_settings_require_secrets():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="sqlite:///test", api_key="short", ollama_model="test")


def test_lifespan_cleanup():
    app = make_app()
    with TestClient(app) as client:
        assert app.state.ai.model == "test-model"
        assert client.get("/openapi.json").status_code == 200


def test_script_generation_endpoint():
    app = make_app()
    app.state.ai.generate.return_value = AIResult(
        model="test-model",
        response='{"hook":"Stop scrolling","body":"Try this tool.","cta":"Follow for more tools.","estimated_duration":30,"visual_suggestions":["Screen recording of the tool"],"caption":"A useful developer tool.","hashtags":["#AI","#developers","#tools"]}',
    )
    result = TestClient(app).post("/api/scripts/generate", headers=AUTH, json={
        "topic": "An AI tool for developers",
        "category": "AI_TOOLS",
        "language": "en",
        "target_duration": 30,
    })
    assert result.status_code == 200
    assert result.json()["estimated_duration"] == 30
    assert result.json()["hashtags"] == ["#AI", "#developers", "#tools"]


def test_script_generator_strips_json_fences():
    async def run():
        provider = AsyncMock()
        provider.generate.return_value = AIResult(
            model="test-model",
            response='```json\n{"hook":"Hook","body":"Body","cta":"CTA","estimated_duration":45,"visual_suggestions":["Dashboard"],"caption":"Caption","hashtags":["#one","#two","#three"]}\n```',
        )
        from app.schemas.scripts import ScriptGenerationRequest
        script = await ScriptGenerator(provider).generate(ScriptGenerationRequest(topic="AI tools"))
        assert script.hook == "Hook"

    asyncio.run(run())


def test_script_generator_rejects_invalid_json():
    async def run():
        provider = AsyncMock()
        provider.generate.return_value = AIResult(model="test-model", response="not json")
        from app.schemas.scripts import ScriptGenerationRequest
        with pytest.raises(ScriptGenerationError):
            await ScriptGenerator(provider).generate(ScriptGenerationRequest(topic="AI tools"))

    asyncio.run(run())


def test_script_schema_rejects_invalid_hashtags():
    from pydantic import ValidationError
    from app.schemas.scripts import GeneratedScript

    with pytest.raises(ValidationError):
        GeneratedScript(
            hook="Hook", body="Body", cta="CTA", estimated_duration=45,
            visual_suggestions=["Dashboard"], caption="Caption",
            hashtags=["AI", "#two", "#three"],
        )
