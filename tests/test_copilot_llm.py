from app.copilot.copilot_service import CopilotService
from app.copilot.llm_provider import (
    CopilotLLMProvider,
    DisabledLLMProvider,
    GeminiProvider,
    OllamaProvider,
    ProviderChain,
    build_llm_provider,
)

from test_copilot_phase10 import ExposureServiceStub


def _provider_settings(mode: str, api_key: str = "test-only-key"):
    return type(
        "ProviderSettings",
        (),
        {
            "copilot_llm_enabled": True,
            "copilot_llm_provider": mode,
            "gemini_api_key": api_key,
            "gemini_model": "gemini-3.8-flash",
            "copilot_llm_timeout_seconds": 1,
            "copilot_ollama_base_url": "http://localhost:11434",
            "copilot_ollama_model": "llama3.2",
        },
    )()


def test_provider_selection_matrix():
    assert isinstance(build_llm_provider(_provider_settings("deterministic")), DisabledLLMProvider)
    assert [provider.provider_name for provider in build_llm_provider(_provider_settings("gemini")).providers] == ["gemini"]
    assert [provider.provider_name for provider in build_llm_provider(_provider_settings("ollama")).providers] == ["ollama"]
    assert [provider.provider_name for provider in build_llm_provider(_provider_settings("auto")).providers] == ["gemini", "ollama"]


def test_selected_gemini_without_credentials_does_not_call_ollama():
    provider = build_llm_provider(_provider_settings("gemini", api_key=""))
    assert isinstance(provider, ProviderChain)
    assert provider.providers == []


def test_selected_ollama_does_not_include_gemini():
    provider = build_llm_provider(_provider_settings("ollama"))
    assert all(not isinstance(item, GeminiProvider) for item in provider.providers)


class RecordingProvider(CopilotLLMProvider):
    provider_name = "gemini"
    def __init__(self) -> None:
        self.context = None

    def generate_explanation(self, question, context):
        self.context = context
        return "Backend-derived explanation."


def test_llm_only_replaces_explanation_and_receives_sanitized_context():
    provider = RecordingProvider()
    service = CopilotService(
        exposure_service=ExposureServiceStub(),
        llm_provider=provider,
    )

    response = service.query_copilot("AUTH00000001", "How is my financial health?")

    assert response.summary == "Backend-derived explanation."
    assert response.metadata["generated_by"] == "gemini"
    assert "test-only-key" not in response.model_dump_json()
    assert response.recommendation
    assert provider.context["financial_snapshot"]["monthly_income"] == 50000.0
    assert "password" not in provider.context
    assert "jwt" not in provider.context


def test_llm_failure_preserves_deterministic_response():
    class UnavailableProvider(CopilotLLMProvider):
        def generate_explanation(self, question, context):
            return None

    response = CopilotService(
        exposure_service=ExposureServiceStub(),
        llm_provider=UnavailableProvider(),
    ).query_copilot("AUTH00000001", "What is my exposure?")

    assert response.metadata["generated_by"] == "deterministic_fallback"
    assert response.metadata["llm_fallback"] is True
    assert response.recommendation


class FakeGeminiModels:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class FakeGeminiClient:
    def __init__(self, models):
        self.models = models


def test_gemini_provider_uses_configured_model_and_trusted_context():
    models = FakeGeminiModels(response=type("Response", (), {"text": "Gemini explanation"})())
    provider = GeminiProvider(
        api_key="test-only-key",
        model="gemini-3.8-flash",
        timeout_seconds=2,
        client=FakeGeminiClient(models),
    )
    context = {"financial_snapshot": {"exposure_score": 24.3}}

    assert provider.generate_explanation("Why is exposure high?", context) == "Gemini explanation"
    call = models.calls[0]
    assert call["model"] == "gemini-3.8-flash"
    assert "24.3" in call["contents"]
    assert "test-only-key" not in call["contents"]


def test_gemini_failure_falls_back_to_ollama():
    class SuccessfulOllama(CopilotLLMProvider):
        provider_name = "ollama"

        def generate_explanation(self, question, context):
            return "Ollama explanation"

    chain = ProviderChain(
        providers=[
            GeminiProvider(
                api_key="test-only-key",
                model="gemini-3.8-flash",
                timeout_seconds=1,
                client=FakeGeminiClient(FakeGeminiModels(error=TimeoutError())),
            ),
            SuccessfulOllama(),
        ]
    )

    assert chain.generate_explanation("question", {}) == "Ollama explanation"
    assert chain.last_provider == "ollama"


def test_gemini_and_ollama_failure_use_deterministic_fallback():
    class FailedProvider(CopilotLLMProvider):
        def generate_explanation(self, question, context):
            return None

    chain = ProviderChain(providers=[FailedProvider(), FailedProvider()])
    response = CopilotService(
        exposure_service=ExposureServiceStub(),
        llm_provider=chain,
    ).query_copilot("AUTH00000001", "What is my exposure?")

    assert response.metadata["generated_by"] == "deterministic_fallback"
    assert response.metadata["llm_fallback"] is True
