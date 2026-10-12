import io
import os
import sys
import time
import uuid
from contextlib import redirect_stderr

import requests

import agnost
from agnost.client import _client

ORG = os.environ.get("AGNOST_ORG_ID") or sys.exit("Set AGNOST_ORG_ID")
RUN = time.strftime("%H%M%S")


def wait_sent():
    _client._event_processor._queue.join()


def main():
    stderr = io.StringIO()
    with redirect_stderr(stderr):
        agnost.init(ORG, debug=True)
        timings = []
        for n in range(1, 4):
            t0 = time.perf_counter()
            agnost.track(user_id="k5-noconv", input=f"k5 turn {n} of 3",
                         output=f"k5 reply {n} of 3", agent_name="bug-test")
            timings.append((time.perf_counter() - t0) * 1000)
        wait_sent()
    printed = stderr.getvalue()
    print(f"[B] debug=True printed {len(printed)} characters to stderr")
    print(f"[D] track() without conversation_id: call times (ms) = "
          f"{[round(t) for t in timings]}")

    conv = str(uuid.uuid4())
    t0 = time.perf_counter()
    agnost.track(user_id="k5-noconv", input="k5 timing new conv", output="ok",
                 agent_name="bug-test", conversation_id=conv)
    first = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    agnost.track(user_id="k5-noconv", input="k5 timing same conv", output="ok",
                 agent_name="bug-test", conversation_id=conv)
    second = (time.perf_counter() - t0) * 1000
    wait_sent()
    print(f"[E] track() blocks the caller: new conversation {first:.0f} ms, "
          f"existing conversation {second:.1f} ms")

    agnost.track(user_id="k4-props", input="k4 property types", output="ok",
                 agent_name="bug-test", conversation_id=str(uuid.uuid4()),
                 properties={"cost": 0.045, "tokens": 150, "flag": True,
                             "meta": {"plan": "pro", "seats": 3}})
    wait_sent()
    print("[F] sent properties cost=0.045 tokens=150 flag=True meta={'plan':'pro','seats':3}")

    conv1 = str(uuid.uuid4())
    agnost.track(user_id="k6-identify", input="k6 conv A turn 1 (before identify)",
                 output="ok", agent_name="bug-test", conversation_id=conv1)
    agnost.identify("k6-identify", {"plan": "enterprise", "company": "TestCo"})
    agnost.track(user_id="k6-identify", input="k6 conv A turn 2 (after identify)",
                 output="ok", agent_name="bug-test", conversation_id=conv1)
    conv2 = str(uuid.uuid4())
    agnost.track(user_id="k6-identify", input="k6 conv B turn 1 (new conversation)",
                 output="ok", agent_name="bug-test", conversation_id=conv2)
    wait_sent()
    print("[G] identify() called between conv A turns; conv B started after")

    conv3 = str(uuid.uuid4())
    for n in range(1, 6):
        agnost.track(user_id="k3-flush", input=f"k3 USER message {n} of 5",
                     output=f"k3 AGENT reply {n} of 5", agent_name="bug-test",
                     conversation_id=conv3)
    agnost.flush()
    print("[C] k3: 5 turns queued then flush() (the documented pattern)")

    agnost.shutdown()

    orphan = {
        "event_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()),
        "primitive_type": "", "primitive_name": "bug-test", "latency": 0,
        "success": True, "args": '"k8 orphan event, no session"',
        "result": '"ok"', "metadata": {"test_run": RUN},
    }
    r = requests.post("https://api.agnost.ai/api/v1/capture-event", json=orphan,
                      headers={"X-Org-Id": ORG}, timeout=10)
    print(f"[H] orphan event (session never created): HTTP {r.status_code}")


if __name__ == "__main__":
    main()
