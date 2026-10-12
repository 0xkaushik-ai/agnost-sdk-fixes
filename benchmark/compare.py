import io
import json
import os
import random
import subprocess
import sys
import threading
import time
from contextlib import redirect_stderr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGINAL = os.path.join(ROOT, "benchmark", ".cache", "agnost-0.1.13")
FIXED = os.path.join(ROOT, "sdk")
CONVERSATIONS, TURNS, RUNS = 3, 10, 5


class MockApi(BaseHTTPRequestHandler):
    lock = threading.Lock()
    count = 0
    log = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        time.sleep(random.uniform(0.02, 0.08))
        with MockApi.lock:
            MockApi.count += 1
            fail = MockApi.count % 7 == 0
            if not fail:
                MockApi.log.append((self.path, body))
        self.send_response(503 if fail else 202)
        self.end_headers()

    def log_message(self, *args):
        pass


def run_once(sdk_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockApi)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    sys.path.insert(0, sdk_path)
    import agnost

    stderr = io.StringIO()
    with redirect_stderr(stderr):
        agnost.init("00000000-0000-4000-8000-000000000000",
                    endpoint=f"http://127.0.0.1:{server.server_port}")
        slowest = 0.0
        for c in range(CONVERSATIONS):
            for n in range(1, TURNS + 1):
                start = time.perf_counter()
                agnost.track(user_id=f"u{c}", input=f"turn {n}", output="ok",
                             conversation_id=f"conv-{c}")
                slowest = max(slowest, time.perf_counter() - start)
        agnost.flush()
        agnost.shutdown()

    events = [p for path, p in MockApi.log if path.endswith("capture-event")]
    last_turn, out_of_order = {}, 0
    for e in events:
        turn = int(json.loads(e["args"]).split()[-1])
        out_of_order += turn < last_turn.get(e["session_id"], 0)
        last_turn[e["session_id"]] = max(turn, last_turn.get(e["session_id"], 0))
    print(json.dumps({
        "delivered": len(events),
        "out_of_order": out_of_order,
        "slowest_ms": round(slowest * 1000),
        "timestamp": all("timestamp" in e for e in events),
    }))


def ensure_original():
    if not os.path.isdir(os.path.join(ORIGINAL, "agnost")):
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--no-deps",
                        "--target", ORIGINAL, "agnost==0.1.13"], check=True)


def collect(sdk_path):
    runs = []
    for _ in range(RUNS):
        out = subprocess.run([sys.executable, "-I", __file__, sdk_path],
                             capture_output=True, text=True, check=True)
        runs.append(json.loads(out.stdout))
    return runs


def span(values):
    return f"{min(values)}-{max(values)}" if min(values) != max(values) else str(values[0])


def main():
    ensure_original()
    results = {"agnost 0.1.13": collect(ORIGINAL), "fixed": collect(FIXED)}
    total = CONVERSATIONS * TURNS
    print(f"{RUNS} runs each, {CONVERSATIONS} conversations x {TURNS} turns, "
          f"mock API with 20-80 ms latency and a 503 on every 7th request\n")
    print(f"{'':<24}" + "".join(f"{name:>16}" for name in results))
    rows = [
        ("delivered", lambda r: f"{span([x['delivered'] for x in r])}/{total}"),
        ("out of order", lambda r: span([x["out_of_order"] for x in r])),
        ("slowest track() ms", lambda r: span([x["slowest_ms"] for x in r])),
        ("sends timestamp", lambda r: "yes" if all(x["timestamp"] for x in r) else "no"),
    ]
    for label, fmt in rows:
        print(f"{label:<24}" + "".join(f"{fmt(r):>16}" for r in results.values()))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_once(sys.argv[1])
    else:
        main()
