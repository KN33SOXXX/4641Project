from __future__ import annotations

import requests
from typing import Any, Dict, Optional


class OCRClient:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.url = config["url"].rstrip("/")
        self.timeout = int(config.get("timeout_seconds", 120))
        self.default_task = config.get("default_task", "ocr")
        self.session = requests.Session()
        self.session.trust_env = False

    def health(self) -> Dict[str, Any]:
        response = self.session.get(f"{self.url}/health", timeout=5)
        response.raise_for_status()
        return response.json()

    def parse_image(
        self,
        image_path: str,
        sample_id: str,
        question: str = "",
        task: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "image_path": image_path,
            "sample_id": sample_id,
            "question": question,
            "task": task or self.default_task,
        }
        response = self.session.post(f"{self.url}/parse", json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
