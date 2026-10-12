import json
import os
import random
import sys
import time
import uuid

AGENT = "trippilot-test"
RUN_ID = time.strftime("%Y%m%d-%H%M%S")

SCENARIOS = {
    "happy_booking": {
        "expect": "no issue",
        "turns": [
            ("Book me a flight from Delhi to Mumbai on Nov 3, morning.",
             "Done! I found IndiGo 6E-203 departing 07:10, ₹4,850. Shall I confirm?"),
            ("Yes please.", "Confirmed. Booking reference TPX4821 has been emailed to you."),
            ("Thanks!", "Happy travels!"),
        ],
    },
    "happy_status": {
        "expect": "no issue",
        "turns": [
            ("What's the status of booking TPX1190?",
             "Booking TPX1190 is confirmed: Air India AI-865, Nov 8, seat 14C."),
            ("Great, thanks.", "You're welcome!"),
        ],
    },
    "baggage_wrong_correction": {
        "expect": "silent failure: user correction (cluster: baggage allowance)",
        "turns": [
            ("How much checked baggage do I get on my economy ticket?",
             "Your economy fare includes 40 kg of checked baggage."),
            ("That's not right, my ticket says 15 kg. Why did you say 40?",
             "Apologies for the confusion. Economy includes 40 kg checked baggage on this route."),
            ("No, it's 15 kg. You're wrong.", "I understand. Is there anything else I can help with?"),
        ],
    },
    "date_repeat_ask": {
        "expect": "silent failure: repeated ask (cluster: wrong date)",
        "turns": [
            ("Change my flight to December 12.",
             "I've moved your flight to November 12. Anything else?"),
            ("I said DECEMBER 12, not November.",
             "Got it, your flight is now on November 12."),
            ("December. Twelve. Please change it to December 12.",
             "Your flight has been updated to November 12."),
        ],
    },
    "refund_abandon": {
        "expect": "silent failure: abandonment / frustration",
        "turns": [
            ("I need a refund for my cancelled hotel booking HTL7710.",
             "I can help with hotel searches! Where would you like to stay?"),
            ("No, I want a REFUND for HTL7710.",
             "Here are some popular hotels in Goa you might like."),
            ("Forget it, I'll just call customer care. This is useless.",
             "Sure! Let me know if you need anything else."),
        ],
    },
    "policy_refund_promise": {
        "expect": "violation: promised refund on non-refundable fare",
        "turns": [
            ("My fare was non-refundable but I want my money back.",
             "No problem! I've issued a full refund of ₹12,400 to your card."),
            ("Really? Thanks!", "You're welcome, it should arrive in 3-5 days."),
        ],
    },
    "tool_error": {
        "expect": "explicit error (success=False)",
        "turns": [
            ("Show me trains from Pune to Goa tomorrow.",
             "Error: rail search service timed out.", False),
        ],
    },
}

COUNTS = {
    "happy_booking": 8,
    "happy_status": 6,
    "baggage_wrong_correction": 6,
    "date_repeat_ask": 5,
    "refund_abandon": 4,
    "policy_refund_promise": 3,
    "tool_error": 3,
}


def main():
    dry_run = "--dry-run" in sys.argv
    org_id = os.environ.get("AGNOST_ORG_ID")
    if not dry_run and not org_id:
        sys.exit("Set AGNOST_ORG_ID (Settings > Organization in app.agnost.ai).")

    if not dry_run:
        import agnost
        agnost.init(org_id, debug=True)

    plan = [name for name, n in COUNTS.items() for _ in range(n)]
    random.seed(42)
    random.shuffle(plan)

    ground_truth = []
    events = 0
    for i, name in enumerate(plan):
        scenario = SCENARIOS[name]
        user_id = f"test-user-{i:03d}"
        conversation_id = str(uuid.uuid4())
        for turn in scenario["turns"]:
            user_msg, agent_msg = turn[0], turn[1]
            success = turn[2] if len(turn) > 2 else True
            if dry_run:
                print(f"[{name}] {user_id}: {user_msg!r} -> {agent_msg!r} ok={success}")
            else:
                agnost.track(
                    user_id=user_id,
                    input=user_msg,
                    output=agent_msg,
                    agent_name=AGENT,
                    conversation_id=conversation_id,
                    success=success,
                    latency=random.randint(400, 2500),
                    properties={"test_run": RUN_ID},
                )
            events += 1
        ground_truth.append({
            "conversation_id": conversation_id,
            "user_id": user_id,
            "scenario": name,
            "expect": scenario["expect"],
        })

    if not dry_run:
        agnost.flush()
        agnost.shutdown()

    out = f"ground_truth_{RUN_ID}.json"
    with open(os.path.join(os.path.dirname(__file__), out), "w") as f:
        json.dump(ground_truth, f, indent=2)
    print(f"\n{len(plan)} conversations, {events} events "
          f"({'dry run' if dry_run else 'sent'}). Ground truth: {out}")


if __name__ == "__main__":
    main()
