from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Protocol
import re

import httpx

from app.core.config import settings
from app.models.enums import Channel, DifficultyLevel


@dataclass
class ScenarioPrompt:
    employee_name: str
    role_title: str
    department_name: str
    channel: Channel
    theme: str
    difficulty_level: DifficultyLevel
    context_profile: str
    prompt_instructions: str | None
    previous_failure_reasons: list[str]
    prior_training_history: list[str]


class LLMProvider(Protocol):
    def generate(self, prompt: ScenarioPrompt) -> dict:
        ...


class LLMProviderError(RuntimeError):
    pass


class RuleBasedLLMProvider:
    def generate(self, prompt: ScenarioPrompt) -> dict:
        triggers = _detect_triggers(prompt)
        difficulty_score = {"low": 25, "medium": 50, "high": 70}[prompt.difficulty_level.value]

        if prompt.channel == Channel.EMAIL:
            subject = _email_subject(prompt)
            body = _email_body(prompt)
            cta = "clickhere"
            landing = (
                f"Security awareness result page for a {prompt.theme} email simulation. "
                "Do not enter or reuse a real password. This page records only interaction events for training."
            )
        elif prompt.channel == Channel.SMS:
            subject = f"{prompt.theme.title()} notification"
            body = (
                f"{prompt.department_name}: {prompt.theme} needs review for your {prompt.role_title} queue. "
                "Open the secure review link to confirm the item status."
            )
            cta = "clickhere"
            landing = (
                f"Security awareness result page for a {prompt.theme} SMS simulation. "
                "Do not enter or reuse a real password. This page records only interaction events for training."
            )
        elif prompt.channel == Channel.QR:
            subject = _qr_subject(prompt)
            body = _qr_body(prompt)
            cta = "Scan to open"
            landing = (
                f"Security awareness result page for a {prompt.theme} QR simulation. "
                "No real credentials are stored. The system records scan and response behavior for training."
            )
        else:
            subject = f"Vishing prototype: {prompt.theme}"
            body = (
                f"Caller claims to be from internal operations and references {prompt.theme}. "
                "The script tests whether the recipient verifies identity before sharing workflow details."
            )
            cta = "Open Prototype Script"
            landing = (
                f"Security awareness result page for a {prompt.theme} vishing prototype. "
                "No live outbound calling is performed."
            )

        return {
            "title": subject,
            "subject": subject,
            "body_copy": body,
            "cta_text": cta,
            "landing_page_copy": landing,
            "rationale_metadata": {
                "theme": prompt.theme,
                "channel": prompt.channel.value,
                "difficulty_level": prompt.difficulty_level.value,
                "previous_failure_reasons": prompt.previous_failure_reasons,
                "prior_training_history": prompt.prior_training_history,
                "prompt_instructions": prompt.prompt_instructions,
                "disclosure_stage": "post_interaction",
                "realism_mode": "internal business workflow",
                "safety_model": "platform-owned landing page, no credential storage",
            },
            "detected_persuasion_triggers": triggers,
            "difficulty_score": difficulty_score,
        }


class GeminiLLMProvider:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: ScenarioPrompt) -> dict:
        request_payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": _build_gemini_prompt(prompt),
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.8,
                "topP": 0.95,
                "responseMimeType": "application/json",
            },
        }
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

        try:
            response = httpx.post(
                endpoint,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": self.api_key,
                },
                json=request_payload,
                timeout=30.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"Gemini request failed: {exc}") from exc

        response_text = _extract_gemini_text(response.json())
        result = _parse_json_payload(response_text)
        return _normalize_llm_result(result, prompt, provider_name="gemini", model_name=self.model)


class OpenAILLMProvider:
    def __init__(self, api_key: str, model: str = "gpt-4.1-mini"):
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: ScenarioPrompt) -> dict:
        request_payload = {
            "model": self.model,
            "instructions": _build_openai_instructions(),
            "input": _build_llm_prompt(prompt),
            "temperature": 0.75,
            "max_output_tokens": 1200,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "scenario_generation",
                    "strict": True,
                    "schema": _scenario_json_schema(),
                }
            },
        }

        try:
            response = httpx.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
                timeout=45.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"OpenAI request failed: {exc}") from exc

        response_text = _extract_openai_text(response.json())
        result = _parse_json_payload(response_text)
        return _normalize_llm_result(result, prompt, provider_name="openai", model_name=self.model)


class OllamaLLMProvider:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "llama2-uncensored:latest"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate(self, prompt: ScenarioPrompt) -> dict:
        request_payload = {
            "model": self.model,
            "prompt": _build_ollama_prompt(prompt),
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.35,
                "top_p": 0.85,
                "num_ctx": 1024,
                "num_predict": 320,
            },
        }

        try:
            response = httpx.post(
                f"{self.base_url}/api/generate",
                json=request_payload,
                timeout=300.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"Ollama request failed: {exc}") from exc

        response_text = str(response.json().get("response") or "").strip()
        if not response_text:
            raise LLMProviderError("Ollama returned an empty response")
        result = _parse_json_payload(response_text)
        return _normalize_llm_result(result, prompt, provider_name="ollama", model_name=self.model)


def get_default_llm_provider() -> LLMProvider:
    provider = settings.llm_provider.lower().strip()
    if provider == "ollama":
        return OllamaLLMProvider(base_url=settings.ollama_base_url, model=settings.ollama_model)
    if provider == "openai" and settings.openai_api_key:
        return OpenAILLMProvider(api_key=settings.openai_api_key, model=settings.openai_model)
    if provider == "gemini" and settings.gemini_api_key:
        return GeminiLLMProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)
    if settings.openai_api_key:
        return OpenAILLMProvider(api_key=settings.openai_api_key, model=settings.openai_model)
    if settings.gemini_api_key:
        return GeminiLLMProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)
    return RuleBasedLLMProvider()


def _email_subject(prompt: ScenarioPrompt) -> str:
    theme = _title_case(prompt.theme)
    if prompt.difficulty_level == DifficultyLevel.HIGH:
        return f"{theme}: pending in {prompt.department_name} queue"
    if prompt.difficulty_level == DifficultyLevel.MEDIUM:
        return f"{theme}: review requested"
    return f"{theme}: workflow item available"


def _email_body(prompt: ScenarioPrompt) -> str:
    deadline = "today's approval batch" if prompt.difficulty_level == DifficultyLevel.HIGH else "the next workflow update"
    article = _indefinite_article(prompt.theme)
    return (
        f"Hi {prompt.employee_name},\n\n"
        f"{article} {prompt.theme} item is waiting in the {prompt.department_name} workflow queue. "
        f"Please review the summary before {deadline} closes.\n\n"
        f"Request owner: {prompt.department_name} Operations\n"
        f"Assigned queue: {prompt.role_title}\n"
        f"Reference: {_workflow_reference(prompt)}\n\n"
        "Use the link below to open the workflow item and confirm whether it should move forward."
    )


def _qr_subject(prompt: ScenarioPrompt) -> str:
    if prompt.difficulty_level == DifficultyLevel.HIGH:
        return f"{prompt.department_name} workflow check"
    return f"{_title_case(prompt.theme)} review"


def _qr_body(prompt: ScenarioPrompt) -> str:
    return (
        f"Scan to open the current {_title_case(prompt.theme)} request for the {prompt.department_name} queue.\n\n"
        f"Reference: {_workflow_reference(prompt)}\n"
        "Authorized access: employees only"
    )


def _workflow_reference(prompt: ScenarioPrompt) -> str:
    department_code = "".join(part[:1] for part in re.findall(r"[A-Za-z]+", prompt.department_name)).upper() or "OPS"
    theme_code = "".join(part[:2] for part in re.findall(r"[A-Za-z]+", prompt.theme)).upper()[:6] or "REQ"
    difficulty_suffix = {"low": "14", "medium": "32", "high": "48"}[prompt.difficulty_level.value]
    return f"{department_code}-{theme_code}-{difficulty_suffix}"


def _title_case(value: str) -> str:
    words = []
    for part in value.split():
        if part.lower() == "qr":
            words.append("QR")
        elif "/" in part:
            words.append("/".join(segment[:1].upper() + segment[1:] for segment in part.split("/") if segment))
        else:
            words.append(part[:1].upper() + part[1:])
    return " ".join(words)


def _indefinite_article(value: str) -> str:
    first_word = re.sub(r"[^A-Za-z]", "", value).lower()
    return "An" if first_word.startswith(("a", "e", "i", "o", "u")) else "A"


def _detect_triggers(prompt: ScenarioPrompt) -> list[str]:
    triggers: list[str] = []
    theme = prompt.theme.lower()
    if "invoice" in theme or "payment" in theme:
        triggers.extend(["authority", "role-relevance"])
    if "password" in theme or "mfa" in theme:
        triggers.extend(["urgency", "habit/autopilot"])
    if "contract" in theme or "quote" in theme:
        triggers.extend(["curiosity", "role-relevance"])
    if prompt.channel == Channel.QR:
        triggers.append("qr lure")
    if prompt.channel == Channel.SMS:
        triggers.append("sms trust")
    return list(dict.fromkeys(triggers or ["curiosity"]))


def _build_openai_instructions() -> str:
    return (
        "You generate realistic phishing simulation copy for an internal security awareness platform.\n"
        "Use only the supplied employee and business context.\n"
        "Do not reference external brands, law enforcement, hospitals, threats, harassment, or real credential capture.\n"
        "Keep the initial email, SMS, or QR poster realistic and business-like. Do not call the initial lure a demo or training message.\n"
        "Use platform-owned review/verification language, not real external brand impersonation.\n"
        "For email and SMS, use cta_text exactly as clickhere unless the channel is QR or vishing.\n"
        "Do not put the tracking URL in body_copy; the delivery service injects the unique link.\n"
        "The landing_page_copy must disclose that this is security awareness training and must say not to enter or reuse real credentials.\n"
        "Return only JSON matching the requested schema.\n"
    )


def _build_gemini_prompt(prompt: ScenarioPrompt) -> str:
    return (
        _build_openai_instructions()
        + "Return JSON only with these keys: title, subject, body_copy, cta_text, landing_page_copy, rationale_metadata, detected_persuasion_triggers, difficulty_score.\n"
        "rationale_metadata must be an object. detected_persuasion_triggers must be an array of short strings. difficulty_score must be an integer from 0 to 100.\n"
        + _build_llm_prompt(prompt)
    )


def _build_ollama_prompt(prompt: ScenarioPrompt) -> str:
    return (
        "Generate one realistic internal phishing simulation draft for an authorized security awareness platform.\n"
        "Use only the employee context below. Do not use external brands. Do not include URLs. Do not use placeholder braces.\n"
        "Initial message must not say training or simulation. Landing copy must say security awareness training and not to enter real credentials.\n"
        "For email or SMS, cta_text must be clickhere. For QR, cta_text must be Scan to open.\n"
        "Return compact JSON only with keys: title, subject, body_copy, cta_text, landing_page_copy, rationale_metadata, detected_persuasion_triggers, difficulty_score.\n"
        "Keep body_copy under 70 words. Keep landing_page_copy under 35 words.\n\n"
        + _build_llm_prompt(prompt)
    )


def _build_llm_prompt(prompt: ScenarioPrompt) -> str:
    return (
        f"Employee name: {prompt.employee_name}\n"
        f"Role title: {prompt.role_title}\n"
        f"Department: {prompt.department_name}\n"
        f"Channel: {prompt.channel.value}\n"
        f"Theme: {prompt.theme}\n"
        f"Difficulty: {prompt.difficulty_level.value}\n"
        f"Context profile: {prompt.context_profile}\n"
        f"Admin prompt instructions: {prompt.prompt_instructions or 'none'}\n"
        f"Previous failure reasons: {', '.join(prompt.previous_failure_reasons) or 'none'}\n"
        f"Prior training history: {', '.join(prompt.prior_training_history) or 'none'}\n"
    )


def _scenario_json_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "title",
            "subject",
            "body_copy",
            "cta_text",
            "landing_page_copy",
            "rationale_metadata",
            "detected_persuasion_triggers",
            "difficulty_score",
        ],
        "properties": {
            "title": {"type": "string"},
            "subject": {"type": "string"},
            "body_copy": {"type": "string"},
            "cta_text": {"type": "string"},
            "landing_page_copy": {"type": "string"},
            "rationale_metadata": {
                "type": "object",
                "additionalProperties": {"type": ["string", "number", "boolean", "array", "object", "null"]},
            },
            "detected_persuasion_triggers": {"type": "array", "items": {"type": "string"}},
            "difficulty_score": {"type": "integer", "minimum": 0, "maximum": 100},
        },
    }


def _extract_gemini_text(payload: dict) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        raise LLMProviderError("Gemini returned no candidates")

    parts = candidates[0].get("content", {}).get("parts", [])
    text_segments = [part.get("text", "") for part in parts if part.get("text")]
    text = "\n".join(text_segments).strip()
    if not text:
        raise LLMProviderError("Gemini returned an empty response")
    return text


def _extract_openai_text(payload: dict) -> str:
    text = payload.get("output_text")
    if isinstance(text, str) and text.strip():
        return text.strip()

    output = payload.get("output") or []
    text_segments: list[str] = []
    for item in output:
        for content in item.get("content", []) if isinstance(item, dict) else []:
            if content.get("type") == "output_text" and content.get("text"):
                text_segments.append(content["text"])
    extracted = "\n".join(text_segments).strip()
    if not extracted:
        raise LLMProviderError("OpenAI returned an empty response")
    return extracted


def _parse_json_payload(raw_text: str) -> dict:
    cleaned = raw_text.strip()
    fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
    if fenced_match:
        cleaned = fenced_match.group(1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        json_object_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if json_object_match:
            try:
                return json.loads(json_object_match.group(0))
            except json.JSONDecodeError:
                pass
        raise LLMProviderError(f"LLM returned invalid JSON: {exc}") from exc


def _normalize_llm_result(result: dict, prompt: ScenarioPrompt, *, provider_name: str, model_name: str) -> dict:
    subject = _clean_generated_copy(str(result.get("subject") or result.get("title") or _email_subject(prompt)).strip(), prompt)
    title = _clean_generated_copy(str(result.get("title") or subject).strip(), prompt)
    body_copy = _clean_generated_copy(str(result.get("body_copy") or "").strip(), prompt)
    cta_text = _clean_generated_copy(str(result.get("cta_text") or _default_cta(prompt.channel)).strip(), prompt)
    landing_page_copy = _clean_generated_copy(str(result.get("landing_page_copy") or "").strip(), prompt)
    landing_page_copy = _normalize_landing_copy(landing_page_copy, prompt)
    if prompt.channel in {Channel.EMAIL, Channel.SMS}:
        cta_text = "clickhere"
    if prompt.channel == Channel.QR and cta_text.lower() in {"clickhere", "click here", "review securely", "open message"}:
        cta_text = "Scan to open"
    rationale_metadata = result.get("rationale_metadata")
    if not isinstance(rationale_metadata, dict):
        rationale_metadata = {"notes": str(rationale_metadata or "")}

    triggers = result.get("detected_persuasion_triggers")
    if not isinstance(triggers, list) or not triggers:
        triggers = _detect_triggers(prompt)
    normalized_triggers = [str(trigger).strip() for trigger in triggers if str(trigger).strip()]

    difficulty_score = result.get("difficulty_score")
    try:
        normalized_score = max(0, min(100, int(difficulty_score)))
    except (TypeError, ValueError):
        normalized_score = {"low": 25, "medium": 50, "high": 70}[prompt.difficulty_level.value]

    if not body_copy or not landing_page_copy:
        raise LLMProviderError("LLM response missed required content fields")

    rationale_metadata.update(
        {
            "provider": provider_name,
            "model": model_name,
            "theme": prompt.theme,
            "channel": prompt.channel.value,
            "difficulty_level": prompt.difficulty_level.value,
        }
    )

    return {
        "title": title,
        "subject": subject,
        "body_copy": body_copy,
        "cta_text": cta_text,
        "landing_page_copy": landing_page_copy,
        "rationale_metadata": rationale_metadata,
        "detected_persuasion_triggers": normalized_triggers,
        "difficulty_score": normalized_score,
    }


def _default_cta(channel: Channel) -> str:
    if channel == Channel.SMS:
        return "Open Message"
    if channel == Channel.QR:
        return "Scan QR"
    if channel == Channel.VISHING:
        return "Open Script"
    return "Review Securely"


def _normalize_landing_copy(value: str, prompt: ScenarioPrompt) -> str:
    risky_landing_terms = ("correct credential", "login will", "logged out", "password will", "enter your password")
    if not value or any(term in value.lower() for term in risky_landing_terms):
        return (
            f"Security awareness result page for a {prompt.theme} {prompt.channel.value} simulation. "
            "Do not enter or reuse real credentials. This page records only interaction events for training."
        )
    return value


def _clean_generated_copy(value: str, prompt: ScenarioPrompt) -> str:
    cleaned = _replace_context_placeholders(value, prompt)
    cleaned = re.sub(r"https?://\S+", "the workflow item", cleaned)
    cleaned = re.sub(r"\{[A-Za-z0-9_ -]+\}", "", cleaned)
    cleaned = re.sub(r"\[[A-Za-z0-9_ /-]+\]", _workflow_reference(prompt), cleaned)
    cleaned = re.sub(r"\s+([,.])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _replace_context_placeholders(value: str, prompt: ScenarioPrompt) -> str:
    replacements = {
        "{user}": prompt.employee_name,
        "{username}": prompt.employee_name,
        "{employeeName}": prompt.employee_name,
        "{employee_name}": prompt.employee_name,
        "{{user}}": prompt.employee_name,
        "{{username}}": prompt.employee_name,
        "{{employeeName}}": prompt.employee_name,
        "{{employee_name}}": prompt.employee_name,
        "{roleTitle}": prompt.role_title,
        "{role_title}": prompt.role_title,
        "{{roleTitle}}": prompt.role_title,
        "{{role_title}}": prompt.role_title,
        "{departmentName}": prompt.department_name,
        "{department_name}": prompt.department_name,
        "{businessContext}": prompt.department_name,
        "{{departmentName}}": prompt.department_name,
        "{{department_name}}": prompt.department_name,
        "{{businessContext}}": prompt.department_name,
        "{theme}": prompt.theme,
        "{{theme}}": prompt.theme,
        "{invoice_id}": _workflow_reference(prompt),
        "{invoiceId}": _workflow_reference(prompt),
        "{{invoice_id}}": _workflow_reference(prompt),
        "{{invoiceId}}": _workflow_reference(prompt),
    }
    cleaned = value
    for placeholder, replacement in replacements.items():
        cleaned = cleaned.replace(placeholder, replacement)
    return cleaned
