from __future__ import annotations

import json

import httpx
import pytest

from app.models.enums import Channel, DifficultyLevel
from app.services.llm import LLMProviderError, ScenarioPrompt, TogetherAIProvider


def scenario_prompt() -> ScenarioPrompt:
    return ScenarioPrompt(
        employee_name="Amina Khan",
        role_title="Senior Treasury Analyst",
        department_name="Finance",
        company_name="Northwind Financial Labs",
        channel=Channel.EMAIL,
        theme="invoice/payment approval",
        difficulty_level=DifficultyLevel.MEDIUM,
        context_profile="Amina Khan manages supplier approvals for Northwind Financial Labs.",
        prompt_instructions=(
            "Address Amina Khan at amina.khan@northwind.example from Finance or +1 (202) 555-0188."
        ),
        previous_failure_reasons=["Amina Khan previously clicked an invoice message."],
        prior_training_history=["Amina Khan completed payment-security training."],
    )


def valid_model_result() -> dict:
    return {
        "title": "{{company_name}} payment review",
        "subject": "Payment approval requested",
        "body_copy": (
            "Hi {{first_name}}, a payment item is waiting in the {{department}} queue assigned to "
            "{{role_title}}."
        ),
        "cta_text": "clickhere",
        "landing_page_copy": (
            "This was a security awareness simulation. Do not enter or reuse real credentials."
        ),
        "opening_line": "",
        "transcript": "",
        "requested_action": "",
        "rationale_metadata": {"reasoning_summary": "Uses a routine internal approval workflow."},
        "detected_persuasion_triggers": ["authority", "role-relevance"],
        "difficulty_score": 50,
    }


def together_response(result: dict | None = None) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": json.dumps(result or valid_model_result())},
                }
            ]
        },
    )


def test_together_request_uses_placeholders_and_personalizes_locally():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return together_response()

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = TogetherAIProvider(api_key="test-key", client=client, sleep=lambda _delay: None)
        result = provider.generate(scenario_prompt())

    serialized_request = json.dumps(captured)
    for private_value in (
        "Amina",
        "Khan",
        "Finance",
        "Senior Treasury Analyst",
        "Northwind Financial Labs",
        "amina.khan@northwind.example",
        "+1 (202) 555-0188",
        "previously clicked",
        "payment-security training",
    ):
        assert private_value not in serialized_request

    assert "{{first_name}}" in serialized_request
    assert "{{company_name}}" in serialized_request
    assert "{{department}}" in serialized_request
    assert captured["model"] == "openai/gpt-oss-20b"
    assert captured["response_format"]["type"] == "json_schema"
    assert result["rationale_metadata"]["provider"] == "together"
    assert result["rationale_metadata"]["model"] == "openai/gpt-oss-20b"
    assert "Hi Amina" in result["body_copy"]
    assert "Finance queue" in result["body_copy"]
    assert result["title"] == "Northwind Financial Labs payment review"


def test_together_retries_rate_limit_and_respects_retry_after():
    attempts = 0
    delays: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={"error": "rate limited"})
        return together_response()

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = TogetherAIProvider(
            api_key="test-key",
            client=client,
            max_retries=2,
            sleep=delays.append,
        )
        result = provider.generate(scenario_prompt())

    assert attempts == 2
    assert delays == [0.0]
    assert result["rationale_metadata"]["provider"] == "together"


def test_together_timeout_raises_safe_provider_error_after_retry():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("timed out", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = TogetherAIProvider(
            api_key="test-key",
            client=client,
            max_retries=1,
            sleep=lambda _delay: None,
        )
        with pytest.raises(LLMProviderError, match="timed out after retries"):
            provider.generate(scenario_prompt())

    assert attempts == 2


def test_together_rejects_invalid_structured_response():
    def handler(_request: httpx.Request) -> httpx.Response:
        return together_response({"subject": "Incomplete"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = TogetherAIProvider(api_key="test-key", client=client, sleep=lambda _delay: None)
        with pytest.raises(LLMProviderError, match="failed scenario validation"):
            provider.generate(scenario_prompt())


def test_together_reports_when_exact_model_requires_a_dedicated_endpoint():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error": {"code": "model_not_available", "message": "Internal provider wording"}},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = TogetherAIProvider(api_key="test-key", client=client, sleep=lambda _delay: None)
        with pytest.raises(LLMProviderError, match="requires an active dedicated endpoint"):
            provider.generate(scenario_prompt())
