#!/usr/bin/env python3
"""MCP server for hn.fm — drive the pipeline by talking to an agent.

Stdio JSON-RPC 2.0, no third-party dependencies. The MCP surface an agent
actually needs is small and stable (initialize, tools/list, tools/call), and
hand-rolling it keeps this a single file you can run with the system python
against any hn.fm instance — no image rebuild, no SDK version to track.

Design rules, in order of how much they matter:

  * **Never block on generation.** Video takes minutes and digests take
    tens of seconds. Every generating tool returns immediately with a URL
    where progress is visible, because an agent that waits five minutes for a
    tool result is an agent that has timed out.
  * **Check readiness before spending.** `services_status` is exposed as its
    own tool AND consulted inside the generating tools. The inference
    backends are scaled to zero half the time; starting a video when LTX is
    at 0 replicas produces a broken segment forty minutes later instead of a
    refusal now.
  * **The API is the only interface.** No database access, no imports from
    the app. If it cannot be done over HTTP, it does not belong here — that
    is what keeps this file honest about what the product can actually do.

Usage:
    python3 mcp/hnfm_mcp.py                    # talks to http://localhost:8000
    HNFM_API=http://host:8000 python3 ...      # or somewhere else

Register with Claude Code:
    claude mcp add hnfm -- python3 /path/to/hn.fm/mcp/hnfm_mcp.py
"""

import json
import os
import sys
import urllib.error
import urllib.request

API = os.getenv("HNFM_API", "http://localhost:8000").rstrip("/")
UI = os.getenv("HNFM_UI", "http://localhost:3000").rstrip("/")
TIMEOUT = float(os.getenv("HNFM_MCP_TIMEOUT", "120"))

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "hnfm", "version": "0.1.0"}


# --- HTTP ------------------------------------------------------------------


def _request(method: str, path: str, body=None, params=None):
    url = f"{API}{path}"
    if params:
        pairs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
        if pairs:
            url = f"{url}?{pairs}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:400]
        raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {detail}")
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"cannot reach hn.fm at {API} ({e.reason}). Is the stack running?"
        )


def _service_map() -> dict:
    """role -> status, from the live service registry."""
    data = _request("GET", "/api/services/status")
    out = {}
    for svc in data.get("services", []):
        role = (svc.get("details") or {}).get("role") or svc.get("name")
        out[role] = svc.get("status")
    return out


def _require(roles: list) -> str:
    """Return a refusal string if any required backend is not online.

    Refusing here is the whole point: these backends are routinely scaled to
    zero, and the failure mode without this check is a job that runs for
    minutes and produces a broken artifact.
    """
    statuses = _service_map()
    missing = [r for r in roles if statuses.get(r) != "online"]
    if not missing:
        return ""
    lines = [f"  - {r}: {statuses.get(r) or 'unknown'}" for r in missing]
    return (
        "Cannot start: required inference services are not ready.\n"
        + "\n".join(lines)
        + "\n\nScale them up in the k3s cluster, or choose an output that does "
        "not need them (a digest needs only the LLM)."
    )


# --- tools -----------------------------------------------------------------


def t_services_status(**_):
    data = _request("GET", "/api/services/status")
    lines = [f"all_healthy: {data.get('all_healthy')}"]
    for svc in data.get("services", []):
        d = svc.get("details") or {}
        note = f" — {d.get('note')}" if d.get("note") else ""
        err = f"  [{svc.get('error_message')}]" if svc.get("error_message") else ""
        lines.append(
            f"  {svc.get('status'):<9} {svc.get('name')} ({d.get('role')}){note}{err}"
        )
    return "\n".join(lines)


def t_fetch_stories(source="top", limit=25, **_):
    if source not in ("top", "new"):
        return "source must be 'top' or 'new'"
    data = _request("POST", f"/api/hn/queue-{source}", params={"limit": limit})
    return (
        f"Queued {data.get('queued_count')} new {source} stories "
        f"({data.get('skipped_count')} already known).\n"
        f"They scrape and summarise in the background — watch {UI}/live.\n"
        f"Score them with score_stories once they land."
    )


def t_score_stories(limit=40, **_):
    gate = _require(["LLM"])
    if gate:
        return gate
    data = _request("POST", "/api/triage/score-existing", params={"limit": limit})
    return (
        f"Queued triage scoring for {data.get('queued_count')} stories.\n"
        f"Each produces a Story Brief — the material every digest is built "
        f"from — including the Hacker News discussion and any researched "
        f"links.\nProgress: {UI}/live"
    )


def t_list_stories(limit=20, **_):
    data = _request("GET", "/api/triage", params={"limit": limit})
    rows = data.get("items") or data.get("triage") or []
    if not rows:
        return "No scored stories yet. Run fetch_stories then score_stories."
    out = []
    for r in rows[:limit]:
        out.append(
            f"  {r.get('item_id')}  interest={r.get('interest')}  "
            f"hn={r.get('hn_score')}  {str(r.get('title'))[:64]}"
        )
    return "\n".join(out)


def t_create_digest(limit=5, shape="daily", send=False, skip=0,
                    exclude_recent_days=7, **_):
    gate = _require(["LLM"])
    if gate:
        return gate
    body = {
        "limit": limit, "send": bool(send), "score_first": False,
        "shape": shape, "skip": skip,
        "exclude_recent_days": exclude_recent_days,
    }
    data = _request("POST", "/api/digests", body)
    return (
        f"Digest queued (shape={shape}, {limit} stories, "
        f"{'will be emailed to Kindle' if send else 'not emailed'}).\n"
        f"task: {data.get('task_id')}\n"
        f"Watch it build: {UI}/live\n"
        f"Read it when done: {UI}/digests"
    )


def t_create_video(item_id, aspect_format="16:9", mode="video", **_):
    # A video needs the full stack; a podcast-only run does not need images.
    roles = ["LLM", "TTS", "Image"] if mode == "video" else ["LLM", "TTS"]
    gate = _require(roles)
    if gate:
        return gate
    data = _request(
        "POST", "/api/hn/single-task-pipeline",
        {"item_id": int(item_id), "aspect_format": aspect_format, "mode": mode},
    )
    return (
        f"Pipeline queued for item {item_id} ({mode}, {aspect_format}).\n"
        f"task: {data.get('task_id')}\n"
        f"This takes several minutes. Live progress: {UI}/live\n"
        f"Result will appear at: {UI}/hn/item/{item_id}"
    )


def t_story_detail(item_id, **_):
    data = _request("GET", f"/api/hn/items/{item_id}/generations")
    gens = data.get("generations") or []
    return (
        f"Item {item_id}: {len(gens)} generation(s).\n"
        + "\n".join(
            f"  run {g.get('run')} seg {g.get('seg')} "
            f"video={'yes' if g.get('video_ready') else 'no'}"
            for g in gens
        )
        + f"\n{UI}/hn/item/{item_id}"
    )


def t_list_digests(**_):
    data = _request("GET", "/api/digests")
    out = [f"delivery: {data.get('delivery')} (ready={data.get('delivery_ready')})"]
    for d in data.get("digests", [])[:15]:
        out.append(
            f"  {d.get('slug')}  {'/'.join(d.get('formats') or [])}  "
            f"{d.get('bytes')}b  {d.get('modified')}"
        )
    return "\n".join(out) if len(out) > 1 else out[0] + "\n  (none yet)"


def t_send_digest(slug, **_):
    data = _request("POST", f"/api/digests/{slug}/send")
    return f"Sent {data.get('file')} to the Kindle (id {data.get('message_id')})."


TOOLS = [
    {
        "name": "services_status",
        "description": (
            "Check which inference backends are online (LLM, TTS, image, ASR, "
            "video, music). Call this before asking for generation — the "
            "backends are frequently scaled to zero."
        ),
        "inputSchema": {"type": "object", "properties": {}},
        "_fn": t_services_status,
    },
    {
        "name": "fetch_stories",
        "description": "Scrape new stories from Hacker News top or new lists.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "enum": ["top", "new"],
                           "description": "Which HN list to pull from."},
                "limit": {"type": "integer", "description": "How many (default 25)."},
            },
        },
        "_fn": t_fetch_stories,
    },
    {
        "name": "score_stories",
        "description": (
            "Research and score stories that have been scraped: reads the "
            "article, the HN discussion and a few researched links, then "
            "scores how interesting each is and writes a Story Brief."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer"}},
        },
        "_fn": t_score_stories,
    },
    {
        "name": "list_stories",
        "description": "List scored stories, most interesting first.",
        "inputSchema": {
            "type": "object", "properties": {"limit": {"type": "integer"}},
        },
        "_fn": t_list_stories,
    },
    {
        "name": "create_digest",
        "description": (
            "Build a Kindle digest from the most interesting briefed stories. "
            "Shapes: 'daily' (teaser, quick hits, 1-2 features, bonus), "
            "'deep' (fewer stories, longer features), 'scan' (many short "
            "items), 'narrative' (one continuous essay weaving the stories "
            "together, naming titles and commenters). Use skip and "
            "exclude_recent_days to build several editions that do not repeat "
            "the same stories."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Stories to include."},
                "shape": {"type": "string",
                          "enum": ["daily", "deep", "scan", "narrative"]},
                "send": {"type": "boolean",
                         "description": "Email it to the Kindle when built."},
                "skip": {"type": "integer",
                         "description": "Skip this many top stories — use to cut a "
                                        "second, non-overlapping edition."},
                "exclude_recent_days": {
                    "type": "integer",
                    "description": "Exclude stories used in editions this recent "
                                   "(default 7). 0 disables.",
                },
            },
        },
        "_fn": t_create_digest,
    },
    {
        "name": "create_video",
        "description": (
            "Generate a narrated, illustrated video segment for one story. "
            "Takes several minutes; returns a link to watch progress. Use "
            "mode='audio' for a podcast-only version that needs no image "
            "backend."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "integer", "description": "Hacker News item id."},
                "aspect_format": {"type": "string", "enum": ["16:9", "1:1", "9:16"]},
                "mode": {"type": "string", "enum": ["video", "audio"]},
            },
            "required": ["item_id"],
        },
        "_fn": t_create_video,
    },
    {
        "name": "story_detail",
        "description": "What has been generated for one story.",
        "inputSchema": {
            "type": "object",
            "properties": {"item_id": {"type": "integer"}},
            "required": ["item_id"],
        },
        "_fn": t_story_detail,
    },
    {
        "name": "list_digests",
        "description": "List built digests and whether Kindle delivery is configured.",
        "inputSchema": {"type": "object", "properties": {}},
        "_fn": t_list_digests,
    },
    {
        "name": "send_digest",
        "description": "Email an already-built digest to the Kindle.",
        "inputSchema": {
            "type": "object",
            "properties": {"slug": {"type": "string"}},
            "required": ["slug"],
        },
        "_fn": t_send_digest,
    },
]

_BY_NAME = {t["name"]: t for t in TOOLS}


# --- JSON-RPC --------------------------------------------------------------


def _result(rid, payload):
    return {"jsonrpc": "2.0", "id": rid, "result": payload}


def _error(rid, code, message):
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def handle(msg: dict):
    method, rid = msg.get("method"), msg.get("id")

    if method == "initialize":
        return _result(rid, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        })

    # Notifications carry no id and must not be answered at all.
    if method in ("notifications/initialized", "initialized"):
        return None

    if method == "tools/list":
        return _result(rid, {
            "tools": [
                {k: v for k, v in t.items() if not k.startswith("_")} for t in TOOLS
            ]
        })

    if method == "tools/call":
        params = msg.get("params") or {}
        tool = _BY_NAME.get(params.get("name"))
        if not tool:
            return _error(rid, -32602, f"unknown tool: {params.get('name')}")
        try:
            text = tool["_fn"](**(params.get("arguments") or {}))
            return _result(rid, {"content": [{"type": "text", "text": str(text)}]})
        except TypeError as e:
            return _result(rid, {
                "content": [{"type": "text", "text": f"Bad arguments: {e}"}],
                "isError": True,
            })
        except Exception as e:
            # Reported as tool output rather than a protocol error: the agent
            # can read it, explain it, and retry. A JSON-RPC error just aborts.
            return _result(rid, {
                "content": [{"type": "text", "text": f"Failed: {e}"}],
                "isError": True,
            })

    if method == "ping":
        return _result(rid, {})

    return _error(rid, -32601, f"method not found: {method}")


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            response = handle(msg)
        except Exception as e:  # never let one bad call kill the server
            response = _error(msg.get("id"), -32603, str(e))
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
