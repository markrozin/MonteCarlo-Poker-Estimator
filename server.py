"""
Local web UI for the equity estimator.

    python server.py            # then open http://localhost:8000

Standard library only - no extra dependencies. Threaded so a slow preflop
sample doesn't block the page from loading.
"""

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from simulator import outcomes_auto

STATIC_DIR = Path(__file__).resolve().parent / "static"
PORT = 8000

# A real board is dealt in streets. Allowing 1 or 2 cards would send
# equities_auto off enumerating C(45,4) runouts for a board that can't exist.
LEGAL_BOARD_SIZES = {0, 3, 4, 5}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_POST(self):
        if self.path != "/api/equity":
            self.send_error(404, "unknown endpoint")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
            body, status = self._solve(payload), 200
        except ValueError as exc:
            body, status = {"error": str(exc)}, 400
        except Exception as exc:  # noqa: BLE001 - surface anything to the UI
            body, status = {"error": f"unexpected error: {exc}"}, 500
        self._respond(body, status)

    @staticmethod
    def _solve(payload):
        hands = payload.get("hands") or []
        board = payload.get("board") or []
        trials = int(payload.get("trials") or 25_000)

        for i, cards in enumerate(hands, 1):
            if len(cards) != 2:
                raise ValueError(f"hand {i} needs exactly 2 cards")
        if len(board) not in LEGAL_BOARD_SIZES:
            raise ValueError("a board has 0, 3, 4, or 5 cards")

        return {
            "results": outcomes_auto(hands, board=board, n=trials),
            "exact": bool(board),
            "trials": None if board else trials,
        }

    def _respond(self, body, status):
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        if not self.path.startswith("/api"):
            return  # keep the console to API calls only
        super().log_message(fmt, *args)


if __name__ == "__main__":
    print(f"Poker equity UI running at http://localhost:{PORT}  (ctrl-c to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
