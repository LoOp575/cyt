"""Tests for the funding-rounds/investor layer + one-stop token intel (all mocked)."""
import asyncio

import httpx
import pytest

from backend import cryptorank


def run(coro):
    return asyncio.run(coro)


FUNDING_BODY = {
    "data": {
        "totalRaise": "25000000",
        "totalFundingRaise": "25000000",
        "lastValuation": "400000000",
        "fundraisingDescription": "Seed + private rounds",
        "fundingRounds": [
            {
                "stage": "Private",
                "announcementDate": "2024-03-15",
                "raise": "15000000",
                "valuation": "400000000",
                "priceUSD": "0.05",
                "roi": 2.5,
                "athRoi": 9.1,
                "funds": [
                    {"id": 11, "key": "a16z", "name": "a16z crypto", "tier": 1, "isLead": True},
                    {"id": 12, "key": "paradigm", "name": "Paradigm", "tier": 1, "isLead": False},
                ],
            },
            {
                "stage": "Seed",
                "announcementDate": "2023-06-01",
                "raise": "10000000",
                "valuation": "80000000",
                "funds": [
                    {"id": 11, "key": "a16z", "name": "a16z crypto", "tier": 1, "isLead": False},
                    {"id": 13, "key": "binance-labs", "name": "Binance Labs", "tier": 1, "isLead": True},
                ],
            },
        ],
    },
    "status": {"timestamp": 1780000000000, "usedCredits": 1},
}

PRO_STATUS = {
    "plan": "Pro",
    "rateLimitPerMinute": 60,
    "credits": {"monthlyLimit": 1000000, "monthlyUsed": 1, "monthlyRemaining": 999999},
    "endpoints": [
        "/v3/currencies/list",
        "/v3/currencies/{id}",
        "/v3/currencies/upcoming-token-unlocks",
        "/v3/currencies/{id}/funding-rounds",
    ],
}

SANDBOX_STATUS = {
    "plan": "Sandbox",
    "rateLimitPerMinute": 10,
    "credits": {"monthlyLimit": 10000, "monthlyUsed": 0, "monthlyRemaining": 10000},
    "endpoints": ["/v3/currencies/list", "/v3/currencies/map", "/v3/currencies/{id}", "/v3/status"],
}

LIST_BODY = {
    "data": [
        {
            "id": 1,
            "slug": "bitcoin",
            "symbol": "BTC",
            "name": "Bitcoin",
            "rank": 1,
            "price": "67000.5",
            "marketCap": "1310000000000",
            "volume24h": "32000000000",
            "circulatingSupply": "19700000",
            "imageUrl": None,
        }
    ],
    "meta": {"page": 1, "hasNextPage": False},
    "status": {"timestamp": 1780000000000, "usedCredits": 1},
}


class Router:
    def __init__(self, handlers=None):
        self.requests = []
        # {exact_path: responder} — matched on the exact URL path (no prefix bleed).
        self.handlers = handlers or {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        responder = self.handlers.get(request.url.path)
        if responder is not None:
            return responder(request)
        return httpx.Response(404, json={})


@pytest.fixture(autouse=True)
def _clear_cache():
    cryptorank._cr_cache.clear()
    cryptorank._credits_used = 0
    yield


def test_coin_funding_parses_rounds_and_investors(monkeypatch):
    monkeypatch.setenv("CRYPTORANK_API_KEY", "k")
    router = Router({
        "/v3/status": lambda r: httpx.Response(200, json=PRO_STATUS),
        "/v3/currencies/7/funding-rounds": lambda r: httpx.Response(200, json=FUNDING_BODY),
    })
    client = httpx.AsyncClient(transport=httpx.MockTransport(router))
    out = run(cryptorank.coin_funding(client, 7))
    assert out["ok"] is True
    data = out["data"]
    assert data["totalRaiseUsd"] == pytest.approx(2.5e7)
    assert data["lastValuationUsd"] == pytest.approx(4.0e8)
    assert len(data["rounds"]) == 2
    # rounds sorted newest first
    assert data["rounds"][0]["stage"] == "Private"
    # investors deduped, leads first: a16z is lead in round 1
    names = [i["name"] for i in data["investors"]]
    assert set(names) == {"a16z crypto", "Paradigm", "Binance Labs"}
    assert data["investors"][0]["isLead"] is True
    req = next(r for r in router.requests if "funding-rounds" in r.url.path)
    assert req.headers["X-Api-Key"] == "k"


def test_coin_funding_denied_on_sandbox_without_credit(monkeypatch):
    monkeypatch.setenv("CRYPTORANK_API_KEY", "k")
    router = Router({"/v3/status": lambda r: httpx.Response(200, json=SANDBOX_STATUS)})
    client = httpx.AsyncClient(transport=httpx.MockTransport(router))
    out = run(cryptorank.coin_funding(client, 7))
    assert out["ok"] is False
    assert out["code"] == "PLAN_LIMIT_EXCEEDED"
    # No request may hit the funding endpoint when the plan denies it
    assert all("funding-rounds" not in r.url.path for r in router.requests)
    assert cryptorank.stats()["creditsUsed"] == 0


def test_coin_funding_survives_http_error(monkeypatch):
    monkeypatch.setenv("CRYPTORANK_API_KEY", "k")
    router = Router({
        "/v3/status": lambda r: httpx.Response(200, json=PRO_STATUS),
        "/v3/currencies/7/funding-rounds": lambda r: httpx.Response(500, json={}),
    })
    client = httpx.AsyncClient(transport=httpx.MockTransport(router))
    out = run(cryptorank.coin_funding(client, 7))
    assert out["ok"] is False
    assert "reason" in out


def test_intel_full_pro_plan(monkeypatch):
    monkeypatch.setenv("CRYPTORANK_API_KEY", "k")

    unlock_feed = {
        "data": [
            {"currencyId": 1, "date": "2026-12-05", "unlockValue": "20000000",
             "percentOfMcap": 1.6, "tokens": "100000", "id": 9002},
        ],
        "meta": {"hasNextPage": False},
        "status": {"timestamp": 1780000000000, "usedCredits": 1},
    }

    def status(_):
        return httpx.Response(200, json=PRO_STATUS)

    router = Router({
        "/v3/status": status,
        "/v3/currencies/list": lambda r: httpx.Response(200, json=LIST_BODY),
        "/v3/currencies/1": lambda r: httpx.Response(
            200,
            json={
                "data": {"id": 1, "slug": "bitcoin", "symbol": "BTC", "name": "Bitcoin",
                         "rank": 1, "price": "67000.5", "marketCap": "1310000000000",
                         "fullyDilutedValuation": "1400000000000", "hasNextUnlock": True},
                "status": {"usedCredits": 1},
            },
        ),
        "/v3/currencies/upcoming-token-unlocks": lambda r: httpx.Response(200, json=unlock_feed),
        "/v3/currencies/1/funding-rounds": lambda r: httpx.Response(200, json=FUNDING_BODY),
    })
    client = httpx.AsyncClient(transport=httpx.MockTransport(router))
    out = run(cryptorank.intel_for_symbol(client, "BTCUSDT"))
    assert out["ok"] is True
    assert out["symbol"] == "BTC"
    assert out["plan"]["tier"] == "Pro"
    assert out["profile"]["ok"] is True
    assert out["profile"]["data"]["fullyDilutedValuation"] == pytest.approx(1.4e12)
    assert out["unlock"]["ok"] is True
    assert out["unlock"]["data"]["percentOfMcap"] == pytest.approx(1.6)
    assert out["funding"]["ok"] is True
    assert out["funding"]["data"]["totalRaiseUsd"] == pytest.approx(2.5e7)


def test_intel_sandbox_degrades_per_block(monkeypatch):
    """Sandbox key: profile works, unlock+funding say 'butuh Pro', never raises."""
    monkeypatch.setenv("CRYPTORANK_API_KEY", "k")
    router = Router({
        "/v3/status": lambda r: httpx.Response(200, json=SANDBOX_STATUS),
        "/v3/currencies/list": lambda r: httpx.Response(200, json=LIST_BODY),
        "/v3/currencies/1": lambda r: httpx.Response(
            200,
            json={
                "data": {"id": 1, "slug": "bitcoin", "symbol": "BTC", "name": "Bitcoin", "rank": 1},
                "status": {"usedCredits": 1},
            },
        ),
    })
    client = httpx.AsyncClient(transport=httpx.MockTransport(router))
    out = run(cryptorank.intel_for_symbol(client, "BTCUSDT"))
    assert out["ok"] is True
    assert out["profile"]["ok"] is True
    assert out["unlock"]["ok"] is False and out["unlock"]["planDenied"] is True
    assert "Pro" in out["unlock"]["reason"]
    assert out["funding"]["ok"] is False and out["funding"]["planDenied"] is True
    assert "Pro" in out["funding"]["reason"]
    # funding endpoint must never be called on a plan that denies it
    assert all("funding-rounds" not in r.url.path for r in router.requests)


def test_intel_without_key(monkeypatch):
    monkeypatch.delenv("CRYPTORANK_API_KEY", raising=False)
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    out = run(cryptorank.intel_for_symbol(client, "BTCUSDT"))
    assert out["ok"] is False
    assert "CRYPTORANK_API_KEY" in out["reason"]
    for block in ("profile", "unlock", "funding"):
        assert out[block]["ok"] is False


def test_intel_unknown_symbol(monkeypatch):
    monkeypatch.setenv("CRYPTORANK_API_KEY", "k")
    router = Router({
        "/v3/status": lambda r: httpx.Response(200, json=PRO_STATUS),
        "/v3/currencies/list": lambda r: httpx.Response(200, json=LIST_BODY),
    })
    client = httpx.AsyncClient(transport=httpx.MockTransport(router))
    out = run(cryptorank.intel_for_symbol(client, "ZZZZUSDT"))
    assert out["profile"]["ok"] is False
    assert "tidak ada" in out["profile"]["reason"]
    assert out["funding"]["ok"] is False


def test_new_readable_module_has_no_payload_bootstrap():
    """Regression guard: the module must stay plain source (no exec'd payload)."""
    import inspect

    src = inspect.getsource(cryptorank)
    assert "exec(" not in src
    assert "zlib" not in src
    assert hasattr(cryptorank, "coin_funding")
    assert hasattr(cryptorank, "intel_for_symbol")
