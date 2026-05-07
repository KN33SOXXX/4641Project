from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional


class PaddleOCRVLBackend:
    def __init__(self, model_id: str, model_dir: str, device: str, dtype: str) -> None:
        self.model_id = model_id
        self.model_dir = model_dir
        self.device_name = device
        self.dtype_name = dtype
        self.model = None
        self.processor = None
        self.device = None
        self.load_error: Optional[str] = None

    def load(self) -> None:
        if self.model is not None:
            return
        self.load_error = None
        try:
            import torch
            from PIL import Image  # noqa: F401
            from transformers import AutoModelForCausalLM, AutoProcessor

            self.device = "cuda" if self.device_name == "cuda" and torch.cuda.is_available() else "cpu"
            dtype = torch.bfloat16 if self.dtype_name == "bfloat16" and self.device == "cuda" else torch.float32
            model_path = self.model_dir if Path(self.model_dir).exists() and any(Path(self.model_dir).iterdir()) else self.model_id
            self.processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                trust_remote_code=True,
                torch_dtype=dtype,
            ).to(self.device).eval()
        except Exception as exc:
            self.load_error = str(exc)

    def health(self) -> Dict[str, Any]:
        return {
            "backend": "PaddlePaddle/PaddleOCR-VL",
            "loaded": self.model is not None,
            "model_id": self.model_id,
            "model_dir": self.model_dir,
            "device": self.device_name,
            "error": self.load_error,
        }

    def parse(self, image_path: str, task: str = "ocr") -> Dict[str, Any]:
        self.load()
        if self.model is None or self.processor is None:
            return {
                "ocr_lines": [],
                "detected_regions": [],
                "formula_candidates": [],
                "visual_features": {},
                "parse_confidence": 0.0,
                "error": self.load_error or "PaddleOCR-VL backend is not loaded",
            }

        import torch
        from PIL import Image

        prompt = {
            "ocr": "OCR:",
            "table": "Table Recognition:",
            "chart": "Chart Recognition:",
            "formula": "Formula Recognition:",
        }.get(task, "OCR:")
        image = Image.open(image_path).convert("RGB")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        inputs = self.processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
        ).to(self.device)
        with torch.inference_mode():
            output = self.model.generate(
                **inputs,
                max_new_tokens=1024,
                do_sample=False,
                use_cache=True,
            )
        text = self.processor.batch_decode(output, skip_special_tokens=True)[0]
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        formulas = [line for line in lines if any(ch in line for ch in "=+-*/^√∑∫()[]{}")]
        return {
            "ocr_lines": lines,
            "detected_regions": [],
            "formula_candidates": formulas,
            "visual_features": {"image_size": list(image.size), "task": task},
            "parse_confidence": 0.75 if lines else 0.2,
            "raw_text": text,
        }


class OCRHandler(BaseHTTPRequestHandler):
    backend: PaddleOCRVLBackend

    def _send(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8")) if raw else {}

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, self.backend.health())
        elif self.path == "/ready":
            self.backend.load()
            payload = self.backend.health()
            self._send(200 if payload.get("loaded") else 503, payload)
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/parse":
            self._send(404, {"error": "not found"})
            return
        try:
            payload = self._read_json()
            image_path = str(payload.get("image_path", ""))
            if not image_path or not Path(image_path).exists():
                self._send(400, {"error": f"image_path does not exist: {image_path}"})
                return
            result = self.backend.parse(image_path, task=str(payload.get("task", "ocr")))
            result["sample_id"] = payload.get("sample_id", "")
            self._send(200, result)
        except Exception as exc:
            self._send(500, {"error": str(exc)})


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def main() -> None:
    parser = argparse.ArgumentParser(description="PaddleOCR-VL JSON service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10004)
    parser.add_argument("--model-id", default=os.environ.get("OCR_MODEL_ID", "PaddlePaddle/PaddleOCR-VL"))
    parser.add_argument("--model-dir", default=os.environ.get("OCR_MODEL_DIR", "/data2/social_workspace/models/PaddleOCR-VL"))
    parser.add_argument("--device", default=os.environ.get("OCR_DEVICE", "cuda"))
    parser.add_argument("--dtype", default=os.environ.get("OCR_DTYPE", "bfloat16"))
    args = parser.parse_args()
    OCRHandler.backend = PaddleOCRVLBackend(args.model_id, args.model_dir, args.device, args.dtype)
    server = ReusableThreadingHTTPServer((args.host, args.port), OCRHandler)
    print(f"PaddleOCR-VL service listening on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
