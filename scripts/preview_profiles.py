"""실제 Cosmos 뷰 렌더러 + Lingua 원본의 격리된 설정 왕복 검증 서버.

인증/권한/모델까지 포함한 실사용 검증은 아니다. 사용자 데이터에는 접근하지 않는다.
실행: ../cosmos-billy/venv/bin/python scripts/preview_profiles.py --port 8802
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlparse, parse_qs

os.environ["COSMOS_HOME"] = tempfile.mkdtemp(prefix="lingua-preview-")
os.environ["COSMOS_LANG"] = "ko"

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, default=HERE.parent / "cosmos-billy")
    parser.add_argument("--port", type=int, default=8802)
    args = parser.parse_args()
    sys.path.insert(0, str(args.core))
    spec = importlib.util.spec_from_file_location("cosmos_lingua_preview", args.core / "scripts/shoot_lingua_view.py")
    preview = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preview)
    from cosmos.contracts import ToolContext
    from cosmos.core.agent_panel import canvas
    from lingua_live import LinguaLive

    class Context(ToolContext):
        @property
        def user_id(self):
            return "preview-sean"

        @property
        def lang(self):
            return "ko"

    ctx, agent = Context(), LinguaLive()
    agent.run(ctx, action="set", language="en", language_order=["en", "es", "ja"],
              goal="자연스럽게 대화하기", interests="재미있는 영상과 다양한 일상 예시", _tab="settings")

    def update_view():
        from cosmos.contracts.view import spaces_of, chosen_space, normalize
        result = normalize(agent.view(ctx))
        result["space"] = {"allowed": list(spaces_of(agent)), "chosen": chosen_space(agent)}
        preview._view_json = json.dumps(result, ensure_ascii=False).replace("<", "\\u003c")

    update_view()

    class Handler(preview._Handler):
        def end_headers(self):
            if self.path.startswith('/api/agent/canvas'):
                from shells.web.server import PANEL_CSP_DIRECTIVES
                self.send_header('Content-Security-Policy', '; '.join(f'{k} {v}' for k, v in PANEL_CSP_DIRECTIVES.items()))
            # 실제 서버와 같이 공개 글꼴은 sandbox 액자의 null origin에도 허용한다.
            if self.path.startswith("/fonts/"):
                self.send_header("Access-Control-Allow-Origin", "*")
            super().end_headers()

        def do_GET(self):
            if self.path.split("?", 1)[0] == "/base.css":
                return self._blob((preview.APP.parent / "base.css").read_bytes(), "text/css")
            if self.path.startswith("/vendor/"):
                relative = self.path.split("?", 1)[0].lstrip("/")
                root = preview.APP.parent.resolve()
                path = (root / relative).resolve()
                if path.is_relative_to(root) and path.is_file() and path.suffix == ".js":
                    return self._blob(path.read_bytes(), "text/javascript")
                return self._empty(404)
            if self.path.startswith("/api/agent/canvas"):
                names = parse_qs(urlparse(self.path).query).get('libraries', [''])[0]
                return self._blob(canvas(names.split(',') if names else []).encode(), "text/html; charset=utf-8")
            if self.path.startswith("/api/agent/view"):
                update_view()
                return self._json({"ok": True, "agent": "lingua",
                                   "agents": [{"agent": "lingua", "title": "Lingua Live"}],
                                   "view": json.loads(preview._view_json)})
            return super().do_GET()

        def do_POST(self):
            if self.path.rstrip("/") != "/api/agent/action":
                return super().do_POST()
            payload = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))))
            if payload.get("tool") != "lingua":
                return self._json({"ok": False, "error": "Preview only supports Lingua"})
            result = agent.run(ctx, **payload.get("args", {}))
            update_view()
            return self._json({"ok": True, "result": result, "view": json.loads(preview._view_json)})

    server = preview.http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Isolated preview: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
