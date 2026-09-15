"""Whop 'create listing' last-mile — turns a generated opportunity into a HIDDEN draft
product on a Whop business, so the human only has to attach files + publish.

Deliberately conservative:
  * Creates the product as visibility="hidden" (a DRAFT). Never publishes publicly and
    never uploads files (Whop has no clean REST path for the deliverable) — those stay
    manual, human steps.
  * Per-operator Whop business via auth.resolve_whop_credentials (Cael-default fallback).
  * Clean marketing copy is written from the (often rough) product brief by the LLM;
    falls back to a plain title if no classifier is available. Nothing fabricated about
    the product itself — copy is derived from the brief.
"""
from __future__ import annotations
import json
import urllib.request
import urllib.error

API = "https://api.whop.com/api/v1/products"


class WhopError(Exception):
    pass


def _clean_copy(clf, brief: dict) -> dict:
    """LLM rewrites the rough brief into a clean title/headline/description. Falls back to
    a trimmed title if the LLM is unavailable."""
    aud = brief.get("target_customer") or "this audience"
    outcome = brief.get("desired_outcome") or brief.get("product_promise") or ""
    fallback = {"title": (f"The Essential Kit for {aud}")[:80],
                "headline": (outcome or "A focused, done-for-you kit.")[:80],
                "description": outcome or brief.get("core_problem") or ""}
    if not clf:
        return fallback
    try:
        import research_engine as RE
        system = ("Write clean, honest sales copy for a digital product from its brief. STRICT "
                  "JSON {\"title\":str,\"headline\":str,\"description\":str}. title <=70 chars, a real "
                  "product name (no placeholders, no the-word-'calculator'-if-it-isn't-one); headline "
                  "<=80 chars (HARD limit); description 2-4 sentences, concrete, no hype, no invented features.")
        user = json.dumps({"audience": aud, "problem": brief.get("core_problem"),
                           "outcome": outcome, "format": brief.get("product_format")}, ensure_ascii=False)
        d = RE._extract_json(clf.classify(system, user)) or {}
        title = (d.get("title") or "").strip()
        if not title:
            return fallback
        return {"title": title[:80],
                "headline": (d.get("headline") or fallback["headline"]).strip()[:80],
                "description": (d.get("description") or fallback["description"]).strip()}
    except Exception:
        return fallback


def create_draft(opp_id: str, whop: dict, creds: dict | None = None,
                 operator: str = "unknown", title: str | None = None,
                 description: str | None = None) -> dict:
    """Create a HIDDEN draft product on the resolved Whop business. Optional title/
    description override the LLM copy. Returns the product id + admin/public route."""
    if not whop.get("api_key") or not whop.get("biz_id"):
        raise WhopError("no Whop API key / business id configured (operator's own or the default "
                        "CAEL_WHOP_API_KEY + CAEL_WHOP_BIZ_ID)")
    import distribution as DI, research_engine as RE
    try:
        brief = DI.load_opportunity(opp_id)["brief"]
    except Exception as e:
        raise WhopError(f"no product brief for '{opp_id}' — generate the product first ({e})")

    if title:
        copy = {"title": title[:80], "headline": (description or "")[:80],
                "description": description or ""}
    else:
        copy = _clean_copy(RE.get_classifier(creds, layer="product"), brief)

    body = json.dumps({
        "account_id": whop["biz_id"],
        "title": copy["title"],
        "headline": copy["headline"],
        "description": copy["description"],
        "visibility": "hidden",              # DRAFT only — human publishes + uploads files
    }).encode()
    req = urllib.request.Request(API, data=body, method="POST", headers={
        "Authorization": f"Bearer {whop['api_key']}",
        "Content-Type": "application/json",
        "User-Agent": "opportunity-engine/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode()[:400]
        except Exception:
            detail = e.reason
        raise WhopError(f"Whop HTTP {e.code}: {detail}")
    except urllib.error.URLError as e:
        raise WhopError(f"Whop request failed: {e}")

    pid = data.get("id") or data.get("product_id")
    route = data.get("route")
    public_url = f"https://whop.com/{route}" if route else data.get("url")
    return {
        "product_id": pid, "route": route, "public_url": public_url,
        "admin_url": f"https://whop.com/dashboard/products/{pid}" if pid else None,
        "visibility": data.get("visibility", "hidden"),
        "title": copy["title"], "headline": copy["headline"], "description": copy["description"],
        "owner": whop.get("owner"), "requested_by": operator,
        "next_steps": ["Attach the ebook PDF + files via a Whop 'content/files' experience",
                       "Add a one-time price plan", "Set visibility to visible & publish",
                       "Copy the public link into your outreach"],
    }
