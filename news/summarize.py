"""One Arabic headline and a two-sentence summary per story, from all its sources at once, through `claude -p` on the
owner's subscription (the way site/ai/gen.py writes match texts: no API key, no per-token bill). A failure returns None
and the story shows its best original headline instead; three failures in a row stop Claude for the rest of the run."""
import json, os, shutil, subprocess, time

import usage_log

SYSTEM = """أنت محرر أخبار كورة في «تيفو»، موقع عربي لكل العرب. تكتب عنوان وخلاصة لقصة وحدة من عدة مصادر (عربية وأجنبية).
القواعد:
- لا تكتب أي معلومة مب موجودة في المصادر. لا أرقام ولا تواريخ ولا أسماء من عندك.
- لو المصادر تقول «تقارير» أو «قريب» أو «مفاوضات»، اكتبها كذا: لا تحوّل الإشاعة إلى خبر مؤكد. «رسمي» بس إذا مصدر رسمي أو كلمة رسمي موجودة.
- لو المصادر تختلف، اذكر الاختلاف بجملة قصيرة («حسب ماركا…»).
- الأسماء بالعربي بالضبط مثل ما تجي في «names» (لا تغيّر كتابتها). الأرقام غربية (0-9).
- عربي واضح وخفيف يفهمه أي عربي: جمل قصيرة، بدون مبالغة ولا عناوين صفراء، بدون إيموجي وبدون علامات تعجب.
- العنوان سطر واحد (حتى 90 حرف). الخلاصة جملتين (حتى 240 حرف).
- stage للانتقالات فقط: rumour إشاعة، talks مفاوضات، agreed اتفاق، here_we_go «Here we go» من فابريزيو رومانو، official رسمي. غير الانتقالات: none."""
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["title_ar", "summary_ar", "stage"],
          "properties": {"title_ar": {"type": "string", "maxLength": 110}, "summary_ar": {"type": "string", "maxLength": 300},
                         "stage": {"type": "string", "enum": ["rumour", "talks", "agreed", "here_we_go", "official", "none"]}}}
FAILS = [0]


def claude_json(system, payload, schema, model="haiku", timeout=90):
    if FAILS[0] >= 3:
        return None
    exe = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
    cmd = [exe, "-p", "--model", model, "--output-format", "json", "--tools", "", "--strict-mcp-config", "--disable-slash-commands",
           "--no-session-persistence", "--setting-sources", "", "--settings", '{"alwaysThinkingEnabled":false}',
           "--system-prompt", "You are the Arabic football news editor of Tifo. Follow the rules at the top of the message exactly. Reply with JSON only, matching the schema.",
           "--json-schema", json.dumps(schema)]
    # the Arabic rules and the payload go over stdin: a long multi-line Arabic argument is cut short by cmd.exe on Windows
    # (claude.CMD), and stdin costs nothing on the Fold
    msg = system + "\n\nجاوب بـ JSON بس، مطابق للـ schema.\n\nالمدخلات:\n" + json.dumps(payload, ensure_ascii=False)
    t0 = time.time()
    try:
        r = subprocess.run(cmd, input=msg, capture_output=True, text=True, encoding="utf-8",
                           timeout=timeout, cwd="/tmp" if os.path.isdir("/tmp") else None, env=dict(os.environ, MAX_THINKING_TOKENS="0"))
        out = json.loads(r.stdout or "{}")
        usage_log.record_cli("news", out, round(time.time() - t0, 1))
        if r.returncode or out.get("is_error"):
            raise RuntimeError((out.get("result") or r.stderr or "")[:200])
        res = out.get("structured_output") or json.loads(out.get("result") or "")
        if not isinstance(res, dict) or any(k not in res for k in schema["required"]):
            raise ValueError("schema")
        FAILS[0] = 0
        return res
    except Exception as e:
        FAILS[0] += 1
        print("claude failed:", str(e)[:160])
        return None


def summarize(story, sources, names):
    """sources: cluster.sources_of(); names: {name as written: …} the Arabic names of the story's entities."""
    payload = {"kind": story["kind"], "names": sorted(set(names)),
               "sources": [{"outlet": s["name"], "lang": s["lang"], "title": s["title"], "at": s["at"]} for s in sources[:8]]}
    t0 = time.time()
    res = claude_json(SYSTEM, payload, SCHEMA)
    if not res:
        return None
    return {"title_ar": res["title_ar"][:110].strip(), "summary_ar": res["summary_ar"][:300].strip(),
            "stage": None if res["stage"] == "none" else res["stage"], "secs": round(time.time() - t0, 1)}
