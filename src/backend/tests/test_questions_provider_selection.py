import pytest

from app.api import ai_settings
from app.api import questions as questions_api
from app.agents import question_generator
from app.core import ai_service as ai_service_module
from app.core.ai_service import AIProvider, AIService
from app.core.config import settings
from fastapi import HTTPException


def test_resolve_provider_id_upstage():
    assert questions_api.resolve_provider_id("upstage-solar-pro3") == AIProvider.UPSTAGE_SOLAR
    assert questions_api.resolve_provider_id("solar-pro3") == AIProvider.UPSTAGE_SOLAR


def test_resolve_provider_id_gemini():
    assert questions_api.resolve_provider_id("gemini-flash") == AIProvider.GEMINI_FLASH
    assert questions_api.resolve_provider_id("google-gemini") == AIProvider.GEMINI_FLASH


def test_resolve_provider_id_invalid():
    with pytest.raises(HTTPException):
        questions_api.resolve_provider_id("unknown-model")


@pytest.mark.asyncio
async def test_generate_questions_route_passes_preferred_provider(monkeypatch):
    captured = {}

    class FakeGenerator:
        def __init__(self, preferred_provider=None):
            captured["preferred_provider"] = preferred_provider

        async def generate_questions(self, **kwargs):
            return {"success": True, "questions": []}

    monkeypatch.setattr(questions_api, "QuestionGenerator", FakeGenerator)

    request = questions_api.QuestionGenerationRequest(
        repo_url="https://github.com/nodejs/node",
        analysis_result={"analysis_id": "analysis-1"},
        provider_id="upstage-solar-pro3",
    )

    result = await questions_api.generate_questions(request)

    assert result.success is True
    assert captured["preferred_provider"] == AIProvider.UPSTAGE_SOLAR


@pytest.mark.asyncio
async def test_question_generator_uses_preferred_provider_for_ai_calls(monkeypatch):
    called = []

    async def fake_generate_analysis(prompt, provider=None, api_keys=None, **kwargs):
        called.append(provider)
        return {"content": "질문", "model": "stub", "provider": "stub"}

    monkeypatch.setattr(question_generator.ai_service, "generate_analysis", fake_generate_analysis)

    generator = question_generator.QuestionGenerator(preferred_provider=AIProvider.UPSTAGE_SOLAR)
    state = question_generator.QuestionState(
        repo_url="https://github.com/nodejs/node",
        difficulty_level="medium",
    )

    await generator._generate_single_architecture_question("architecture-context", state)
    await generator._generate_single_code_analysis_question(
        {
            "content": "def run():\n    return True\n",
            "metadata": {
                "file_path": "src/app.py",
                "language": "python",
                "file_type": "service",
                "complexity": 4.5,
                "extracted_elements": {
                    "classes": [],
                    "functions": ["run"],
                    "imports": ["fastapi"],
                },
            },
        },
        state,
    )

    assert called == [AIProvider.UPSTAGE_SOLAR, AIProvider.UPSTAGE_SOLAR]


def test_ai_settings_exposes_pinned_upstage_model():
    providers = ai_settings.get_effective_providers({"upstage_api_key": "upstage-key"})

    solar = next(provider for provider in providers if provider["id"] == AIProvider.UPSTAGE_SOLAR.value)

    assert solar["model"] == settings.upstage_solar_model
    assert solar["model"] == "solar-pro3-260126"


@pytest.mark.asyncio
async def test_upstage_generation_uses_pinned_model(monkeypatch):
    captured = {}

    class FakeResponse:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def json(self):
            return {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def post(self, endpoint, json, headers, timeout):
            captured["endpoint"] = endpoint
            captured["payload"] = json
            captured["headers"] = headers
            captured["timeout"] = timeout
            return FakeResponse()

    monkeypatch.setattr(ai_service_module.aiohttp, "ClientSession", lambda: FakeSession())

    service = AIService()
    result = await service._generate_with_upstage(
        "hello",
        api_keys={"upstage_api_key": "test-key"},
    )

    assert captured["payload"]["model"] == settings.upstage_solar_model
    assert captured["payload"]["model"] == "solar-pro3-260126"
    assert result["model"] == settings.upstage_solar_model
