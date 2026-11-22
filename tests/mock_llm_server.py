import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ANSWER = "根据政策片段，青年人才租房补贴申报需要劳动合同和社保记录。[1]"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        length = int(self.headers.get("content-length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        if payload.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            pieces = ["根据政策片段，", "青年人才租房补贴申报", "需要劳动合同和社保记录。", "[1]"]
            for piece in pieces:
                data = json.dumps({"choices": [{"delta": {"content": piece}}]}, ensure_ascii=False)
                self.wfile.write(f"data: {data}\n\n".encode())
                self.wfile.flush()
            usage = {
                "choices": [],
                "usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 24,
                    "total_tokens": 144,
                },
            }
            self.wfile.write(f"data: {json.dumps(usage)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            return
        response = {
            "choices": [{"message": {"content": ANSWER}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 24, "total_tokens": 144},
        }
        body = json.dumps(response, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
