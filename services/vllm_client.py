from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import requests


class VLLMClient:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.base_url = config["base_url"].rstrip("/")
        self.model = config["model"]
        self.timeout = int(config.get("timeout_seconds", 90))
        self.api_key = config.get("api_key", "EMPTY")
        self.health_path = config.get("health_path", "/models")
        self.session = requests.Session()
        self.session.trust_env = False

    def health(self) -> Dict[str, Any]:
        url = f"{self.base_url}{self.health_path}"
        response = self.session.get(url, timeout=5)
        response.raise_for_status()
        return response.json()

    def chat(
        self,
        messages: List[Dict[str, str]],
        sampling: Dict[str, Any],
        response_format: Optional[Dict[str, str]] = None,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": sampling.get("temperature", 0.2),
            "top_p": sampling.get("top_p", 0.9),
            "max_tokens": sampling.get("max_tokens", 1200),
            "frequency_penalty": sampling.get("frequency_penalty", 0.0),
            "presence_penalty": sampling.get("presence_penalty", 0.0),
        }
        for key in ("top_k", "seed", "repetition_penalty"):
            if sampling.get(key) is not None:
                payload[key] = sampling[key]
        if response_format:
            payload["response_format"] = response_format

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = self.session.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
