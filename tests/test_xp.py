import pytest

from seeding import xp as xpmod


class Resp:
    def __init__(self, code):
        self.status_code = code

    def raise_for_status(self):
        if self.status_code >= 400:
            e = xpmod.requests.exceptions.HTTPError(f"HTTP {self.status_code}")
            e.response = self
            raise e

    def json(self):
        return {"ok": True}


def _client(codes, monkeypatch):
    monkeypatch.setattr(xpmod.time, "sleep", lambda s: None)
    c = xpmod.XPlatform(api_key="test")
    seq = iter(codes)
    c.s.get = lambda *a, **k: Resp(next(seq))
    return c


def test_get_rides_out_a_short_outage(monkeypatch):
    assert _client([502, 503, 200], monkeypatch).get("/x") == {"ok": True}


def test_get_fails_fast_on_client_errors(monkeypatch):
    with pytest.raises(xpmod.requests.exceptions.HTTPError):
        _client([404, 200], monkeypatch).get("/x")


def test_get_gives_up_after_all_tries(monkeypatch):
    with pytest.raises(xpmod.requests.exceptions.HTTPError):
        _client([502] * 6, monkeypatch).get("/x")
