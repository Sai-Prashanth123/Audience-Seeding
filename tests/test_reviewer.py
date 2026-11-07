from types import SimpleNamespace as NS

import pandas as pd

from seeding.reviewer import (LIST_SCHEMA, SEGMENT_SCHEMA, account_prompt, build_queue, parse_result,
                              segment_system)
from seeding.seedmap import load_config


def _ok(text, stop="end_turn"):
    msg = NS(stop_reason=stop, stop_details=None, content=[NS(type="text", text=text)],
             usage=NS(input_tokens=100, output_tokens=20))
    return NS(custom_id="acct-x", result=NS(type="succeeded", message=msg))


def test_rubric_contains_every_segment_and_exclusion():
    cfg = load_config()
    s = segment_system(cfg)
    for key in ["b2b:", "ai:", "tech:", "none:", "crypto", "giveaway"]:
        assert key in s


def test_parse_valid_answer():
    r = parse_result(_ok('{"segment": "ai", "also": "b2b", "confidence": 0.9, "reason": "builds agents"}'),
                     SEGMENT_SCHEMA)
    assert r == {"status": "ok", "segment": "ai", "also": "b2b", "confidence": 0.9, "reason": "builds agents"}


def test_parse_never_guesses():
    assert parse_result(_ok("not json"), SEGMENT_SCHEMA)["status"] == "skipped"
    assert parse_result(_ok('{"segment": "crypto", "also": "", "confidence": 1, "reason": "x"}'),
                        SEGMENT_SCHEMA)["reason"].startswith("invalid segment")
    assert parse_result(_ok('{"worth": true}'), LIST_SCHEMA)["reason"].startswith("answer missing")
    refused = _ok("", stop="refusal")
    refused.result.message.stop_details = NS(category="cyber")
    assert parse_result(refused, LIST_SCHEMA) == {"status": "skipped", "reason": "model declined (cyber)"}
    errored = NS(custom_id="x", result=NS(type="errored", error=NS(type="invalid_request")))
    assert parse_result(errored, LIST_SCHEMA)["status"] == "skipped"


def test_queue_is_disagreements_plus_fixed_audit_and_skips_human_done():
    ai = pd.DataFrame({"username": ["a", "b", "c", "d", "e", "f"], "status": ["ok"] * 6,
                       "segment": ["ai", "b2b", "tech", "none", "ai", "ai"], "also": [""] * 6,
                       "confidence": [0.9] * 6, "reason": ["r"] * 6})
    model = pd.DataFrame({"username": ["a", "b", "c", "d", "e", "f"],
                          "segment": ["ai", "ai", "tech", "b2b", "ai", "tech"], "also": ["", "b2b", "", "", "", ""]})
    q = build_queue(ai, model, human_done={"f"}, week_seed=202645, audit_n=2)
    assert set(q[q.kind == "AI and model disagree"].username) == {"d"}   # b agrees via the model's 2nd segment
    assert len(q[q.kind == "random audit"]) == 2 and "f" not in set(q.username)
    q2 = build_queue(ai, model, human_done={"f"}, week_seed=202645, audit_n=2)
    assert q.username.tolist() == q2.username.tolist()                  # same week -> same audit sample


def test_account_prompt_handles_missing_data():
    p = account_prompt("x", None, [])
    assert "(no bio)" in p and "(no posts available)" in p
