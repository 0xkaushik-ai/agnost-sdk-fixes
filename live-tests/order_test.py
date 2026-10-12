import logging
import os
import sys
import time
import uuid

import agnost
from agnost.client import _client

TURNS = 5
GAP_SECONDS = {"k1": 0, "k2": 2}


def main():
    org_id = os.environ.get("AGNOST_ORG_ID") or sys.exit("Set AGNOST_ORG_ID")
    logging.basicConfig(level=logging.WARNING)
    agnost.init(org_id)

    for user, gap in GAP_SECONDS.items():
        conversation_id = str(uuid.uuid4())
        for n in range(1, TURNS + 1):
            agnost.track(
                user_id=user,
                input=f"{user} USER message {n} of {TURNS}",
                output=f"{user} AGENT reply {n} of {TURNS}",
                agent_name="order-test",
                conversation_id=conversation_id,
                properties={"test_run": "order-test", "turn": n},
            )
            _client._event_processor._queue.join()
            print(f"{time.strftime('%H:%M:%S')}.{int(time.time()*1000)%1000:03d} {user} sent turn {n}")
            if gap and n < TURNS:
                time.sleep(gap)
        print(f"{user}: conversation {conversation_id}")

    agnost.shutdown()


if __name__ == "__main__":
    main()
