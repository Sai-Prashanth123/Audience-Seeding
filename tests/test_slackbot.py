from seeding.slackbot import format_slack, parse

CLIENTS = ["itsalexvacca", "Kenny_GTM"]


def test_parse_handles_mentions_and_formats():
    assert parse("@itsalexvacca Cold email isn't dead. Your targeting is.", CLIENTS) == \
        ("itsalexvacca", "Cold email isn't dead. Your targeting is.")
    assert parse("<@U123ABC> kenny_gtm: AI agents will replace SDR busywork first", CLIENTS) == \
        ("Kenny_GTM", "AI agents will replace SDR busywork first")
    assert parse("predict @ITSALEXVACCA - a long enough draft here", CLIENTS)[0] == "itsalexvacca"


def test_parse_ignores_chatter_and_unknown_clients():
    assert parse("thanks!", CLIENTS) is None
    assert parse("@someoneelse this is a draft for a non client", CLIENTS) is None
    assert parse("@itsalexvacca short", CLIENTS) is None


def test_format_slack_mentions_range_and_usual():
    a = {"expected": 1200.0, "low": 600.0, "high": 2500.0, "usual": 1000.0, "vs_usual": 1.2}
    res = {"client": "itsalexvacca", "format": "short text", "hook": "statement", "day_position": 1,
           "actions": {"views": a, "likes": a, "xscore": a}, "drivers": [("n_chars", "raises", 12)], "x_rules": []}
    out = format_slack(res)
    assert "~1,200" in out and "600–2,500" in out and "1.20× usual" in out and "Not a guarantee" in out
