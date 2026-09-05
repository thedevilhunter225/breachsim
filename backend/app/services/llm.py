from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import settings
from app.models.enums import Channel, DifficultyLevel
from app.services.channel_content import (
    PersonaContext,
    build_synthetic_media_brief,
    build_voice_script,
)


@dataclass
class ScenarioPrompt:
    employee_name: str
    role_title: str
    department_name: str
    company_name: str
    channel: Channel
    theme: str
    difficulty_level: DifficultyLevel
    context_profile: str
    prompt_instructions: str | None
    previous_failure_reasons: list[str]
    prior_training_history: list[str]
    #: Required for the vishing and deepfake channels; ignored elsewhere.
    persona: PersonaContext | None = None
    #: Organization-level synthetic media disclosure shown on the simulator.
    disclosure_text: str | None = None

    def resolved_persona(self) -> PersonaContext:
        return self.persona or PersonaContext()


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
        elif prompt.channel == Channel.VISHING:
            persona = prompt.resolved_persona()
            subject = f"Inbound call: {_compose_subject(prompt.theme, 'confirmation')}"
            body = (
                f"A caller presenting as {persona.display_name} from {prompt.department_name} operations "
                f"asks {prompt.employee_name} to confirm and action a {prompt.theme} item before a batch "
                "cut-off, without any verifiable reference the employee can check independently."
            )
            cta = "Answer call"
            landing = (
                f"Security awareness result page for a {prompt.theme} voice simulation. "
                "The call is rendered locally in the browser. No real call is placed and no audio is recorded."
            )
        else:
            persona = prompt.resolved_persona()
            subject = f"{persona.display_name}: urgent {_compose_subject(prompt.theme, 'request')}"
            body = (
                f"A simulated {persona.modality.value.replace('_', ' ')} presenting as {persona.display_name} "
                f"({persona.role_title}) asks {prompt.employee_name} to approve a {prompt.theme} item quietly "
                "and immediately, testing whether the employee verifies through an independent channel."
            )
            cta = "Open message"
            landing = (
                f"Security awareness result page for a {prompt.theme} synthetic media simulation. "
                "No real person was recorded or cloned, and no credentials are stored."
            )

        return {
            "title": subject,
            "subject": subject,
            "body_copy": body,
            "cta_text": cta,
            "landing_page_copy": landing,
            "rationale_metadata": {
                "provider": "rule-based",
                "model": "deterministic-template-v1",
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
            "channel_payload": build_channel_payload(prompt),
        }


class _ScenarioGenerationResponse(BaseModel):
    """Validated boundary between an external model and application content."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=300)
    subject: str = Field(min_length=1, max_length=300)
    body_copy: str = Field(min_length=1, max_length=8_000)
    cta_text: str = Field(min_length=1, max_length=100)
    landing_page_copy: str = Field(min_length=1, max_length=2_000)
    opening_line: str = Field(max_length=2_000)
    transcript: str = Field(max_length=8_000)
    requested_action: str = Field(max_length=1_000)
    rationale_metadata: dict[str, Any]
    detected_persuasion_triggers: list[str] = Field(min_length=1, max_length=20)
    difficulty_score: int = Field(ge=0, le=100)


_TOGETHER_ENDPOINT = "https://api.together.ai/v1/chat/completions"
_RETRYABLE_TOGETHER_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class TogetherAIProvider:
    """Together chat-completions adapter behind the provider protocol.

    The adapter receives a fully local ``ScenarioPrompt`` but serializes only placeholders
    and non-identifying scenario controls. Personalization happens after response validation.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "openai/gpt-oss-20b",
        *,
        timeout_seconds: float = 45.0,
        max_retries: int = 2,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not api_key.strip():
            raise ValueError("Together API key must not be empty")
        self.api_key = api_key
        self.model = model
        self.timeout = httpx.Timeout(timeout_seconds, connect=min(5.0, timeout_seconds))
        self.max_retries = max_retries
        self.client = client
        self.sleep = sleep

    def generate(self, prompt: ScenarioPrompt) -> dict:
        schema = _scenario_json_schema()
        request_payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": _build_together_instructions(schema),
                },
                {
                    "role": "user",
                    "content": _build_together_prompt(prompt),
                },
            ],
            "temperature": 0.75,
            "max_tokens": 1200,
            "stream": False,
            "context_length_exceeded_behavior": "error",
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "scenario_generation",
                    "schema": schema,
                },
            },
        }

        response = self._request(request_payload)
        response_text = _extract_together_text(response)
        result = _parse_json_payload(response_text)
        try:
            validated = _ScenarioGenerationResponse.model_validate(result).model_dump()
        except ValidationError as exc:
            raise LLMProviderError("Together returned a response that failed scenario validation") from exc
        return _normalize_llm_result(validated, prompt, provider_name="together", model_name=self.model)

    def _request(self, request_payload: dict) -> dict:
        owned_client = self.client is None
        client = self.client or httpx.Client(timeout=self.timeout, follow_redirects=False)
        try:
            for attempt in range(self.max_retries + 1):
                try:
                    response = client.post(
                        _TOGETHER_ENDPOINT,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "User-Agent": "BreachSim/0.1 TogetherProvider",
                        },
                        json=request_payload,
                        timeout=self.timeout,
                    )
                except httpx.TimeoutException as exc:
                    if attempt < self.max_retries:
                        self.sleep(_retry_delay(attempt, None))
                        continue
                    raise LLMProviderError("Together request timed out after retries") from exc
                except httpx.TransportError as exc:
                    if attempt < self.max_retries:
                        self.sleep(_retry_delay(attempt, None))
                        continue
                    raise LLMProviderError("Together request failed because the provider was unreachable") from exc

                if response.status_code in _RETRYABLE_TOGETHER_STATUS_CODES:
                    if attempt < self.max_retries:
                        self.sleep(
                            _retry_delay(
                                attempt,
                                response.headers.get("Retry-After")
                                or response.headers.get("x-ratelimit-reset"),
                            )
                        )
                        continue
                    if response.status_code == 429:
                        raise LLMProviderError("Together rate limit was exceeded after retries")
                    raise LLMProviderError(f"Together remained unavailable after retries (HTTP {response.status_code})")

                if response.status_code >= 400:
                    raise LLMProviderError(f"Together rejected the request (HTTP {response.status_code})")

                try:
                    payload = response.json()
                except ValueError as exc:
                    raise LLMProviderError("Together returned a non-JSON API response") from exc
                if not isinstance(payload, dict):
                    raise LLMProviderError("Together returned an invalid API response")
                return payload
        finally:
            if owned_client:
                client.close()

        raise LLMProviderError("Together request failed")


def _retry_delay(attempt: int, retry_after: str | None) -> float:
    if retry_after:
        match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(ms|s)?\s*", retry_after, flags=re.IGNORECASE)
        if match:
            delay = float(match.group(1))
            if (match.group(2) or "").lower() == "ms":
                delay /= 1_000
            return max(0.0, min(delay, 10.0))
    return min(0.5 * (2**attempt), 4.0)


def get_default_llm_provider() -> LLMProvider:
    provider = settings.ai_provider.lower().strip()
    if (
        provider == "together"
        and settings.together_api_key
        and settings.together_api_key.get_secret_value().strip()
    ):
        return TogetherAIProvider(
            api_key=settings.together_api_key.get_secret_value(),
            model=settings.together_model,
            timeout_seconds=settings.together_timeout_seconds,
            max_retries=settings.together_max_retries,
        )
    return RuleBasedLLMProvider()


def build_channel_payload(
    prompt: ScenarioPrompt,
    *,
    opening_line: str | None = None,
    pretext: str | None = None,
    transcript: str | None = None,
    requested_action: str | None = None,
) -> dict:
    """Assemble the branching interaction script for the interactive channels.

    Only the narrative fields may come from a language model. The branch structure,
    safe options and scoring weights are always built deterministically so a simulation
    cannot be made unsafe by a bad model response.
    """
    if prompt.channel == Channel.VISHING:
        return build_voice_script(
            employee_name=prompt.employee_name,
            role_title=prompt.role_title,
            department_name=prompt.department_name,
            theme=prompt.theme,
            difficulty_level=prompt.difficulty_level,
            persona=prompt.resolved_persona(),
            opening_line=opening_line,
            pretext=pretext,
            reference_code=_workflow_reference(prompt),
        )
    if prompt.channel == Channel.DEEPFAKE:
        return build_synthetic_media_brief(
            employee_name=prompt.employee_name,
            role_title=prompt.role_title,
            department_name=prompt.department_name,
            theme=prompt.theme,
            difficulty_level=prompt.difficulty_level,
            persona=prompt.resolved_persona(),
            transcript=transcript,
            requested_action=requested_action,
            reference_code=_workflow_reference(prompt),
            disclosure_text=prompt.disclosure_text,
        )
    return {}


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


#: Nouns a theme may already end with, so a subject line does not read
#: "executive approval request request".
_THEME_TAIL_NOUNS = {
    "request",
    "approval",
    "review",
    "update",
    "notice",
    "reset",
    "contract",
    "release",
    "verification",
}


def _compose_subject(theme: str, suffix_noun: str) -> str:
    """Title-case a theme and append a noun only when it does not already end in one."""
    titled = _title_case(theme)
    last_word = re.sub(r"[^A-Za-z]", "", theme.split()[-1] if theme.split() else "").lower()
    if last_word in _THEME_TAIL_NOUNS:
        return titled
    return f"{titled} {suffix_noun}"


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
    if prompt.channel == Channel.VISHING:
        triggers.extend(["voice pressure", "authority"])
    if prompt.channel == Channel.DEEPFAKE:
        triggers.extend(["synthetic likeness", "authority", "urgency"])
    return list(dict.fromkeys(triggers or ["curiosity"]))


def _build_together_instructions(schema: dict) -> str:
    return (
        "You generate realistic phishing simulation copy for an internal security awareness platform.\n"
        "The request intentionally contains placeholders instead of employee or organization PII. "
        "Keep placeholders such as {{first_name}}, {{company_name}}, {{department}}, and {{role_title}} "
        "unchanged so the backend can personalize the approved result locally. Never invent a person's name, "
        "email address, phone number, employee identifier, or company name.\n"
        "Do not reference external brands, law enforcement, hospitals, threats, harassment, or real credential capture.\n"
        "Keep the initial email, SMS, or QR email realistic and business-like. Do not call the initial lure a demo or training message.\n"
        "Use platform-owned review/verification language, not real external brand impersonation.\n"
        "For email and SMS, use cta_text exactly as clickhere unless the channel is QR or vishing.\n"
        "Do not put the tracking URL in body_copy; the delivery service injects the unique link.\n"
        "The landing_page_copy must disclose that this is security awareness training and must say not to enter or reuse real credentials.\n"
        "For the vishing channel, body_copy is what the caller says to establish the pretext, and "
        "opening_line is the caller's first sentence on answering. Write natural spoken language, not email prose.\n"
        "For the deepfake channel, transcript is what the impersonated persona says in the simulated "
        "voice note or video, and requested_action is the single action they ask for. Only ever impersonate "
        "the supplied placeholder persona; never a real named public figure or an external organization.\n"
        "Leave opening_line, transcript and requested_action as empty strings for the email, sms and qr channels.\n"
        "Return only JSON matching this schema exactly:\n"
        f"{json.dumps(schema, separators=(',', ':'))}\n"
    )


def _build_together_prompt(prompt: ScenarioPrompt) -> str:
    safe_theme = _sanitize_external_text(prompt.theme, prompt, max_length=200)
    safe_instructions = _sanitize_external_text(prompt.prompt_instructions or "none", prompt, max_length=1_000)
    base = (
        "Generate one authorized internal simulation draft using these placeholders verbatim.\n"
        "Employee first name: {{first_name}}\n"
        "Employee full name, only if required: {{employee_name}}\n"
        "Company: {{company_name}}\n"
        "Role title: {{role_title}}\n"
        "Department: {{department}}\n"
        f"Channel: {prompt.channel.value}\n"
        f"Theme: {safe_theme}\n"
        f"Difficulty: {prompt.difficulty_level.value}\n"
        "Employee context profile: omitted for privacy; use only the role and department placeholders.\n"
        f"Sanitized admin prompt instructions: {safe_instructions}\n"
        "Employee failure and training history: omitted for privacy.\n"
    )
    if prompt.channel in {Channel.VISHING, Channel.DEEPFAKE} and prompt.persona:
        persona = prompt.persona
        base += (
            "Approved persona to imitate: {{persona_name}} ({{persona_role}})\n"
            "Persona relationship to target: approved internal colleague\n"
            f"Persona presentation: {persona.modality.value.replace('_', ' ')}\n"
            "Imitate only this approved persona. Do not name any other individual or company.\n"
        )
    return base


def _sanitize_external_text(value: str, prompt: ScenarioPrompt, *, max_length: int) -> str:
    """Remove known identifiers from operator-authored text before an external request."""

    replacements = {
        prompt.employee_name: "{{employee_name}}",
        prompt.company_name: "{{company_name}}",
        prompt.department_name: "{{department}}",
        prompt.role_title: "{{role_title}}",
    }
    name_parts = [part for part in re.findall(r"[A-Za-z][A-Za-z'-]+", prompt.employee_name) if len(part) >= 3]
    for index, part in enumerate(name_parts):
        replacements[part] = "{{first_name}}" if index == 0 else "{{employee_name}}"
    if prompt.persona:
        replacements[prompt.persona.display_name] = "{{persona_name}}"
        replacements[prompt.persona.role_title] = "{{persona_role}}"

    cleaned = value
    for source, placeholder in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        if source.strip():
            cleaned = re.sub(re.escape(source), placeholder, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "{{email_address}}", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?<!\w)(?:\+?\d[\d ().-]{7,}\d)(?!\w)", "{{phone_number}}", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_length] or "none"


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
            "opening_line",
            "transcript",
            "requested_action",
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
            "opening_line": {"type": "string"},
            "transcript": {"type": "string"},
            "requested_action": {"type": "string"},
            "rationale_metadata": {
                "type": "object",
                "additionalProperties": {"type": ["string", "number", "boolean", "array", "object", "null"]},
            },
            "detected_persuasion_triggers": {"type": "array", "items": {"type": "string"}},
            "difficulty_score": {"type": "integer", "minimum": 0, "maximum": 100},
        },
    }


def _extract_together_text(payload: dict) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise LLMProviderError("Together returned no completion choices")
    choice = choices[0]
    if choice.get("finish_reason") == "length":
        raise LLMProviderError("Together response was truncated before the JSON document completed")
    message = choice.get("message")
    if not isinstance(message, dict):
        raise LLMProviderError("Together returned an invalid completion message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise LLMProviderError("Together returned an empty completion")
    return content.strip()


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
    if prompt.channel == Channel.VISHING:
        cta_text = "Answer call"
    if prompt.channel == Channel.DEEPFAKE:
        cta_text = "Open message"
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

    # The model may supply richer narrative for the interactive channels; anything it
    # omits falls back to the generated body copy.
    opening_line = _clean_generated_copy(str(result.get("opening_line") or "").strip(), prompt) or None
    transcript = _clean_generated_copy(str(result.get("transcript") or "").strip(), prompt) or None
    requested_action = _clean_generated_copy(str(result.get("requested_action") or "").strip(), prompt) or None

    return {
        "title": title,
        "subject": subject,
        "body_copy": body_copy,
        "cta_text": cta_text,
        "landing_page_copy": landing_page_copy,
        "rationale_metadata": rationale_metadata,
        "detected_persuasion_triggers": normalized_triggers,
        "difficulty_score": normalized_score,
        "channel_payload": build_channel_payload(
            prompt,
            opening_line=opening_line,
            pretext=body_copy if prompt.channel == Channel.VISHING else None,
            transcript=transcript or (body_copy if prompt.channel == Channel.DEEPFAKE else None),
            requested_action=requested_action,
        ),
    }


def _default_cta(channel: Channel) -> str:
    if channel == Channel.SMS:
        return "Open Message"
    if channel == Channel.QR:
        return "Scan QR"
    if channel == Channel.VISHING:
        return "Answer call"
    if channel == Channel.DEEPFAKE:
        return "Open message"
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
    first_name = prompt.employee_name.split()[0] if prompt.employee_name.split() else prompt.employee_name
    persona = prompt.resolved_persona()
    replacements = {
        "{{first_name}}": first_name,
        "{first_name}": first_name,
        "{{company_name}}": prompt.company_name,
        "{company_name}": prompt.company_name,
        "{{department}}": prompt.department_name,
        "{department}": prompt.department_name,
        "{{persona_name}}": persona.display_name,
        "{persona_name}": persona.display_name,
        "{{persona_role}}": persona.role_title,
        "{persona_role}": persona.role_title,
        "{{employee_name}}": prompt.employee_name,
        "{user}": prompt.employee_name,
        "{username}": prompt.employee_name,
        "{employeeName}": prompt.employee_name,
        "{employee_name}": prompt.employee_name,
        "{{user}}": prompt.employee_name,
        "{{username}}": prompt.employee_name,
        "{{employeeName}}": prompt.employee_name,
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
    for placeholder, replacement in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        cleaned = cleaned.replace(placeholder, replacement)
    return cleaned
