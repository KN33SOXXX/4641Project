from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

sys.dont_write_bytecode = True

from agent import ScratchMathFeedbackAgent, load_config


class AgentHTTPHandler(BaseHTTPRequestHandler):
    agent: ScratchMathFeedbackAgent

    def _send(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Any:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8")) if raw else {}

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, self.agent.health())
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        try:
            payload = self._read_json()
            if self.path == "/diagnose":
                self._send(200, self.agent.diagnose(payload).to_dict())
            elif self.path == "/batch":
                if not isinstance(payload, list):
                    self._send(400, {"error": "batch expects a JSON array"})
                    return
                self._send(200, self.agent.diagnose_many(payload))
            elif self.path == "/analytics":
                rows = payload.get("results", payload) if isinstance(payload, dict) else payload
                if not isinstance(rows, list):
                    self._send(400, {"error": "analytics expects a JSON array or {results: [...]}"})
                    return
                self._send(200, self.agent.class_analytics(rows, with_llm_summary=True))
            else:
                self._send(404, {"error": "not found"})
        except Exception as exc:
            self._send(500, {"error": str(exc)})


def main() -> None:
    parser = argparse.ArgumentParser(description="ScratchMath Agent HTTP API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10005)
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()
    AgentHTTPHandler.agent = ScratchMathFeedbackAgent(load_config(args.config))
    server = ThreadingHTTPServer((args.host, args.port), AgentHTTPHandler)
    print(f"ScratchMath agent API listening on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
