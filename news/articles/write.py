"""One Claude API call per article (spec, «Writer»): the style guide is the system prompt, as a cached block (it is the same
for every article, so later calls read it from the prompt cache); the fact sheet is the user message; the answer is JSON in
the schema (structured output, output_config.format). Streamed and read with get_final_message() so a long answer never hits
the request timeout. The key is ANTHROPIC_API_KEY from the environment (the repo secret on GitHub)."""
import json
from pathlib import Path

STYLE = Path(__file__).with_name("style.md")
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["headline", "standfirst", "sections", "facts_box", "sources_cited"],
          "properties": {"headline": {"type": "string"}, "standfirst": {"type": "string"},
                         "sections": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["subhead", "paragraphs"],
                                                                  "properties": {"subhead": {"type": "string"}, "paragraphs": {"type": "array", "items": {"type": "string"}}}}},
                         "facts_box": {"type": "array", "items": {"type": "string"}}, "sources_cited": {"type": "array", "items": {"type": "string"}}}}


class WriteError(Exception):
    pass


class Writer:
    def __init__(self, client=None):
        self.client = client

    def _c(self):
        if self.client is None:
            import anthropic
            self.client = anthropic.Anthropic()
        return self.client

    def write(self, kind, sheet, model, notes=None):
        user = "جاوب بـ JSON فقط مطابق للـ schema.\n\nورقة الحقائق:\n" + json.dumps(sheet, ensure_ascii=False, indent=1)
        if notes:
            user += "\n\nالنسخة السابقة لم تجتز الفحص لهذه الأسباب. اكتب المقال من جديد وصحّحها:\n- " + "\n- ".join(notes)
        with self._c().messages.stream(
                model=model, max_tokens=16000,
                system=[{"type": "text", "text": STYLE.read_text(encoding="utf-8"), "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user}],
                output_config={"format": {"type": "json_schema", "schema": SCHEMA}}) as s:
            msg = s.get_final_message()
        if msg.stop_reason in ("refusal", "max_tokens"):
            raise WriteError(f"stop_reason {msg.stop_reason}")
        text = next((b.text for b in msg.content if b.type == "text"), "")
        try:
            art = json.loads(text)
        except ValueError as e:
            raise WriteError(f"no JSON: {e}") from e
        if (not isinstance(art, dict) or any(k not in art for k in SCHEMA["required"]) or not str(art.get("headline") or "").strip()
                or not art.get("sections") or not all(isinstance(x, dict) and x.get("paragraphs") for x in art["sections"])):
            raise WriteError(f"answer is not the schema: keys {sorted(art)[:8] if isinstance(art, dict) else type(art).__name__}")
        u = msg.usage
        usage = {"in": u.input_tokens or 0, "out": u.output_tokens or 0,
                 "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0, "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0}
        return art, usage
