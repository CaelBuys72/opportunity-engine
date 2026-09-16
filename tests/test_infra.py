#!/usr/bin/env python3
"""Deploy-infra tests — auth, credential routing, storage, concurrency, cache.
Runs against the LOCAL backend in a temp dir (no Supabase, no API spend, no server).

    python3 tests/test_infra.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

# isolate storage in a temp dir so tests never touch real data
_TMP = tempfile.mkdtemp(prefix="oe_test_")
os.environ["STORAGE_BACKEND"] = "local"
import storage
storage.UNIVERSE_DIR = Path(_TMP) / "universe"
storage.RESEARCH_DIR = Path(_TMP) / "research"
storage._BACKEND = None  # rebuild against temp dirs

import auth

_passed = _failed = 0
def check(name, cond):
    global _passed, _failed
    if cond:
        _passed += 1; print(f"  ok  {name}")
    else:
        _failed += 1; print(f"FAIL  {name}")


print("== auth: password hashing ==")
h = auth.hash_password("s3cret")
check("verify correct password", auth.verify_password("s3cret", h))
check("reject wrong password", not auth.verify_password("nope", h))
check("hash not reversible (no plaintext)", "s3cret" not in h)

print("== auth: login + session (auth enabled) ==")
os.environ["CAEL_PASSWORD_HASH"] = auth.hash_password("cael-pw")
os.environ["SHEYLYN_PASSWORD_HASH"] = auth.hash_password("shey-pw")
check("auth_enabled when hashes set", auth.auth_enabled())
tok = auth.login("cael", "cael-pw")
check("cael login works", bool(tok))
check("cael session resolves", auth.resolve_session(tok) == "cael")
check("invalid login rejected", auth.login("cael", "wrong") is None)
check("unknown operator rejected", auth.login("mallory", "x") is None)
tok_s = auth.login("sheylyn", "shey-pw")
check("sheylyn login works", auth.resolve_session(tok_s) == "sheylyn")
auth.logout(tok)
check("logout invalidates session", auth.resolve_session(tok) is None)
check("no session => no operator (auth on)", auth.current_operator(None) is None)

print("== credential routing: no cross-operator fallback ==")
os.environ["CAEL_GEMINI_API_KEY"] = "cael-gem"; os.environ["CAEL_SERPER_API_KEY"] = "cael-ser"
os.environ.pop("SHEYLYN_GEMINI_API_KEY", None); os.environ.pop("SHEYLYN_SERPER_API_KEY", None)
c = auth.resolve_operator_credentials("cael")
s = auth.resolve_operator_credentials("sheylyn")
check("cael resolves cael keys", c["gemini"] == "cael-gem" and c["serper"] == "cael-ser")
check("sheylyn missing keys => None (NOT cael's)", s["gemini"] is None and s["serper"] is None)
check("no cross fallback to cael", s["gemini"] != "cael-gem")

print("== storage: rows upsert idempotent ==")
b = storage.get_backend()
b.replace_collection("markets", [{"id": "mkt-a", "name": "A"}, {"id": "mkt-b", "name": "B"}])
b.upsert_rows("markets", [{"id": "mkt-a", "name": "A"}])  # duplicate id
check("no duplicate rows on re-upsert", len(b.list_rows("markets")) == 2)
b.upsert_rows("markets", [{"id": "mkt-c", "name": "C"}])
check("new row added", len(b.list_rows("markets")) == 3)
check("get_row works", b.get_row("markets", "mkt-b")["name"] == "B")

print("== storage: concurrency claim ==")
check("first claim succeeds", b.claim_expansion("aud-x", "cael") is True)
check("second claim blocked (no double-gen)", b.claim_expansion("aud-x", "sheylyn") is False)
b.release_expansion("aud-x")

print("== storage: dossier + shared read ==")
b.write_dossier_file("opp-x", "product_brief", {"product_format": "spreadsheet"})
check("dossier file persists", b.read_dossier_file("opp-x", "product_brief")["product_format"] == "spreadsheet")
check("read_dossier returns merged", b.read_dossier("opp-x").get("product_brief") is not None)

print("== storage: usage attribution is operator-aware ==")
b.record_usage({"operator": "cael", "provider": "serper", "queries": 8, "results": 40})
b.record_usage({"operator": "sheylyn", "provider": "serper", "queries": 3, "results": 12})
u = b.read_doc("research_usage")
check("cael usage tracked", u["by_operator"]["cael"]["queries"] == 8)
check("sheylyn usage separate", u["by_operator"]["sheylyn"]["queries"] == 3)

print("== cache-first: reading children does NOT invoke providers ==")
# children live as rows; listing them is a pure storage read (no Serper/Gemini)
import research_engine as RE
os.environ.pop("SERPER_API_KEY", None); os.environ.pop("GEMINI_API_KEY", None)
check("no provider without keys", RE.get_search_provider({}) is None and RE.get_classifier({}) is None)
b.upsert_rows("submarkets", [{"id": "sub-a-1", "name": "S1", "market_id": "mkt-a"}])
check("stored child loads with zero generation", len(b.list_rows("submarkets")) == 1)

print("== provider routing: research NEVER uses the product (Groq) provider ==")
os.environ["CF_ACCOUNT_ID"] = "a"; os.environ["CF_API_TOKEN"] = "t"   # enable cloudflare in chains
_creds = {"operator": "cael", "groq": "g", "gemini": "m", "mistral": "mi"}
def _chain(layer):
    c = RE.get_classifier(_creds, layer=layer)
    return [p.name for p in c.providers] if hasattr(c, "providers") else ([c.name] if c else [])
for _layer in ("research", "explore", "rescore", "creator"):
    _ch = _chain(_layer)
    check(f"{_layer} excludes groq", "groq" not in _ch)
    check(f"{_layer} primary is mistral", _ch[:1] == ["mistral"])
check("product uses groq primary", _chain("product")[:1] == ["groq"])
check("product overflows to gemini", "gemini" in _chain("product"))
# research with NO research providers must FAIL CLEARLY, not fall back to groq
os.environ.pop("CF_ACCOUNT_ID", None); os.environ.pop("CF_API_TOKEN", None)
_c_nores = RE.get_classifier({"operator": "cael", "groq": "g"}, layer="research")
check("research fails clearly (no groq fallback) when research providers absent", _c_nores is None)
check("product still resolves when only groq present",
      RE.get_classifier({"operator": "cael", "groq": "g"}, layer="product") is not None)

print("== creator qualification: non-creator entities are rejected ==")
import distribution as DI
check("reddit is a non-creator domain", DI._is_non_creator_domain("https://www.reddit.com/r/freelance/x"))
check("medium is a non-creator domain", DI._is_non_creator_domain("https://medium.com/@someone/post"))
check("dev.to is a non-creator domain", DI._is_non_creator_domain("https://dev.to/foo"))
check("notion is a non-creator domain", DI._is_non_creator_domain("https://www.notion.so/templates"))
check("youtube is NOT denylisted (creators live there)", not DI._is_non_creator_domain("https://youtube.com/@gm"))
check("instagram is NOT denylisted", not DI._is_non_creator_domain("https://instagram.com/creator"))
check("substack is NOT denylisted", not DI._is_non_creator_domain("https://foo.substack.com"))
check("individual_creator is a creator type", "individual_creator" in DI._CREATOR_TYPES)
check("saas is NOT a creator type", "saas" not in DI._CREATOR_TYPES)
check("publication is NOT a creator type", "publication" not in DI._CREATOR_TYPES)

print(f"\n{_passed} passed, {_failed} failed")
sys.exit(1 if _failed else 0)
