"""One JSON line per Claude call into ~/.elyoxe/usage.jsonl (ELYOXE_USAGE_LOG overrides) — the file the daily cost
email (~/workspace/automation/cost-report) sums. cinema writes the same file from its own copy of this shape.
Best effort: a logging failure never touches the call it describes, and pytest runs write nothing."""
import json, os, time

PATH = os.environ.get("ELYOXE_USAGE_LOG") or os.path.expanduser("~/.elyoxe/usage.jsonl")
CLAUDE_OFF = os.environ.get("ELYOXE_CLAUDE_OFF") or os.path.expanduser("~/.elyoxe/claude-off")


def claude_off():
    """The owner's kill switch (2026-10-01, «تبند كل استخدامات الclaude مؤقتا»): while ~/.elyoxe/claude-off exists, no
    `claude -p` runs — gen.py falls back to Gemini like any Claude failure, news keeps each story's best original
    headline. Remove the file to switch back on. Ignored under pytest."""
    return os.path.exists(CLAUDE_OFF) and not os.environ.get("PYTEST_CURRENT_TEST")


def record_cli(job, out, secs):
    """out: the parsed `claude -p --output-format json` result. Tifo runs on the owner's subscription, so usd is the
    CLI's list-price equivalent (what the same tokens would cost on the API), not a bill."""
    if os.environ.get("PYTEST_CURRENT_TEST") or not isinstance(out, dict):
        return
    try:
        at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        lines = []
        for model, mu in (out.get("modelUsage") or {}).items():
            lines.append({"at": at, "project": "tifo", "job": job, "via": "subscription",
                          "model": mu.get("canonicalModel") or model, "in": mu.get("inputTokens", 0),
                          "out": mu.get("outputTokens", 0), "cache_read": mu.get("cacheReadInputTokens", 0),
                          "cache_write": mu.get("cacheCreationInputTokens", 0), "usd": round(mu.get("costUSD") or 0, 6),
                          "ok": not out.get("is_error"), "secs": secs})
        if not lines:
            return
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        with open(PATH, "a", encoding="utf-8", newline="\n") as f:
            f.write("".join(json.dumps(r) + "\n" for r in lines))
    except Exception:
        pass
