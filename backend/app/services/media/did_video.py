"""D-ID talking-head video provider.

Animates a single consented still image so it speaks supplied audio (or text). D-ID
renders asynchronously: ``POST /talks`` returns an id, then ``GET /talks/{id}`` is
polled until ``status == done`` and a result URL is available.

Auth is HTTP Basic with the API key (D-ID accepts the key as the basic-auth username).
The consented face image is uploaded per render and never retained by BreachSim beyond
the persona's media store and retention clock.
"""

from __future__ import annotations

import base64

import httpx

from app.services.media.base import GeneratedMedia, MediaKind, ProviderError


class DIDVideoProvider:
    name = "did"

    def __init__(self, *, api_key: str, base_url: str = "https://api.d-id.com") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _auth_header(self) -> dict:
        # D-ID accepts "Basic base64(api_key)" — the key already encodes the colon pair.
        token = base64.b64encode(f"{self.api_key}".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {token}"}

    def supports_talking_head(self) -> bool:
        return True

    def _upload_image(self, face_image: bytes, content_type: str) -> str:
        try:
            response = httpx.post(
                f"{self.base_url}/images",
                headers=self._auth_header(),
                files={"image": ("persona.jpg", face_image, content_type or "image/jpeg")},
                timeout=90.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProviderError(f"D-ID image upload failed: {exc.response.text[:300]}") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"D-ID image upload request failed: {exc}") from exc
        url = response.json().get("url")
        if not url:
            raise ProviderError("D-ID did not return an image URL.")
        return url

    def _upload_audio(self, audio: bytes, content_type: str) -> str:
        try:
            response = httpx.post(
                f"{self.base_url}/audios",
                headers=self._auth_header(),
                files={"audio": ("speech.mp3", audio, content_type or "audio/mpeg")},
                timeout=120.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProviderError(f"D-ID audio upload failed: {exc.response.text[:300]}") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"D-ID audio upload request failed: {exc}") from exc
        url = response.json().get("url")
        if not url:
            raise ProviderError("D-ID did not return an audio URL.")
        return url

    def generate_talking_head(
        self,
        *,
        face_image: bytes,
        face_content_type: str,
        audio: bytes | None,
        audio_content_type: str | None,
        text: str | None,
        options: dict | None = None,
    ) -> GeneratedMedia:
        source_url = self._upload_image(face_image, face_content_type)

        if audio:
            script = {"type": "audio", "audio_url": self._upload_audio(audio, audio_content_type or "audio/mpeg")}
        elif text:
            # Fall back to D-ID's own TTS if we were not handed cloned audio.
            script = {"type": "text", "input": text, "provider": {"type": "microsoft"}}
        else:
            raise ProviderError("A talking-head render needs either audio or text.")

        try:
            response = httpx.post(
                f"{self.base_url}/talks",
                headers={**self._auth_header(), "Content-Type": "application/json"},
                json={"source_url": source_url, "script": script},
                timeout=90.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProviderError(f"D-ID talk creation failed: {exc.response.text[:300]}") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"D-ID talk creation request failed: {exc}") from exc

        talk_id = response.json().get("id")
        if not talk_id:
            raise ProviderError("D-ID did not return a talk id.")
        return GeneratedMedia(
            kind=MediaKind.VIDEO,
            provider=self.name,
            content_type="video/mp4",
            remote_ref=talk_id,
            status="pending",
        )

    def poll(self, remote_ref: str) -> GeneratedMedia:
        try:
            response = httpx.get(
                f"{self.base_url}/talks/{remote_ref}",
                headers=self._auth_header(),
                timeout=60.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"D-ID poll failed: {exc}") from exc

        body = response.json()
        status = body.get("status")
        if status == "done" and body.get("result_url"):
            try:
                clip = httpx.get(body["result_url"], timeout=120.0)
                clip.raise_for_status()
            except httpx.HTTPError as exc:
                raise ProviderError(f"D-ID result download failed: {exc}") from exc
            return GeneratedMedia(
                kind=MediaKind.VIDEO,
                provider=self.name,
                content_type="video/mp4",
                content=clip.content,
                remote_ref=remote_ref,
                status="ready",
            )
        if status in {"error", "rejected"}:
            return GeneratedMedia(
                kind=MediaKind.VIDEO,
                provider=self.name,
                content_type="video/mp4",
                remote_ref=remote_ref,
                status="failed",
                detail={"error": body.get("error") or status},
            )
        return GeneratedMedia(
            kind=MediaKind.VIDEO,
            provider=self.name,
            content_type="video/mp4",
            remote_ref=remote_ref,
            status="pending",
        )
