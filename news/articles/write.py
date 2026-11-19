"""One Claude API call per article (spec, «Writer»): the style guide is the system prompt, as a cached block (it is the same
for every article, so later calls read it from the prompt cache); the fact sheet is the user message; the answer is JSON in
the schema (structured output, output_config.format). Streamed and read with get_final_message() so a long answer never hits
the request timeout. The key is ANTHROPIC_API_KEY from the environment (the repo secret on GitHub)."""
import base64, json
from pathlib import Path

STYLE = Path(__file__).with_name("style.md")
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["headline", "standfirst", "sections", "facts_box", "sources_cited"],
          "properties": {"headline": {"type": "string"}, "standfirst": {"type": "string"},
                         "sections": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["subhead", "paragraphs"],
                                                                  "properties": {"subhead": {"type": "string"}, "paragraphs": {"type": "array", "items": {"type": "string"}}}}},
                         "facts_box": {"type": "array", "items": {"type": "string"}}, "sources_cited": {"type": "array", "items": {"type": "string"}}}}


# The news writer's answer when the sheet holds only a question, a guess or an opinion, no news (style.md rule 9; owner
# 2026-11-20 after «إرم نيوز تتساءل: هل يدفع سان جيرمان مليار يورو لضم يامال؟» went out as an article).
NO_NEWS = "لا خبر"


class WriteError(Exception):
    pass


class Writer:
    def __init__(self, client=None):
        self.client = client

    def _c(self):
        if self.client is None:
            import anthropic
            self.client = anthropic.Anthropic(timeout=180, max_retries=1)   # one slow call must not hold the 15-min job
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
        u = msg.usage
        usage = {"in": u.input_tokens or 0, "out": u.output_tokens or 0,
                 "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0, "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0}
        if kind == "news" and isinstance(art, dict) and str(art.get("headline") or "").strip(" «»\"") == NO_NEWS:
            return {"no_news": True}, usage
        if (not isinstance(art, dict) or any(k not in art for k in SCHEMA["required"]) or not str(art.get("headline") or "").strip()
                or not art.get("sections") or not all(isinstance(x, dict) and x.get("paragraphs") for x in art["sections"])):
            raise WriteError(f"answer is not the schema: keys {sorted(art)[:8] if isinstance(art, dict) else type(art).__name__}")
        return art, usage

    TOPICS = ("transfer", "injury", "statement", "presser", "official", "match", "other")
    STAGES = ("rumour", "talks", "agreed", "here_we_go", "official")
    LABEL_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["topic", "stage"],
                    "properties": {"topic": {"type": "string", "enum": list(TOPICS)}, "stage": {"type": "string", "enum": list(STAGES) + ["none"]}}}
    LABEL_ASK = ("Label this Arabic football news article for its page, by what the article as a whole is about, never by single words.\n"
                 "topic: transfer = a player's or coach's move, signing, loan, contract, renewal or departure; injury = an injury, a "
                 "player's fitness or return from injury; statement = mainly what someone said; presser = a press conference; official = "
                 "an official announcement by a club, league, federation or court that is not a transfer; match = a result or a "
                 "performance in a match; other = anything else (a stadium, money, the club's affairs, the fans).\n"
                 "stage, for a transfer only, else none: rumour = reports, interest or speculation; talks = an offer or negotiations; "
                 "agreed = an agreement reached, not yet announced; here_we_go = a trusted reporter says it is done; official = announced "
                 "by the club or the player, or signed.\n\n")

    def label(self, art, model="claude-haiku-5-5"):
        """-> (topic, stage or None, usage): the chip on the article's page (owner 2026-11-19: a stadium's renovation went out as
        «انتقالات · إشاعة» from the journal's keyword guess). A stage only for a transfer."""
        body = "\n".join(p for s in art.get("sections") or [] for p in s.get("paragraphs") or [])[:3000]
        text = self.LABEL_ASK + "العنوان: " + (art.get("headline") or "") + "\nالمقدمة: " + (art.get("standfirst") or "") + "\n\n" + body
        msg = self._c().messages.create(model=model, max_tokens=1024, messages=[{"role": "user", "content": text}],   # 100 left 28 of 60 empty
                                        output_config={"format": {"type": "json_schema", "schema": self.LABEL_SCHEMA}})
        raw = next((b.text for b in msg.content if b.type == "text"), "")
        try:
            ans = json.loads(raw)
            topic, stage = ans["topic"], ans["stage"]
        except (ValueError, KeyError, TypeError) as e:
            raise WriteError(f"label answer cannot be read ({msg.stop_reason}): " + repr(raw[:80])) from e
        if topic not in self.TOPICS or (stage != "none" and stage not in self.STAGES):
            raise WriteError(f"label {topic!r} / {stage!r} is not one of ours")
        u = msg.usage
        usage = {"in": u.input_tokens or 0, "out": u.output_tokens or 0,
                 "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0, "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0}
        return topic, (stage if topic == "transfer" and stage != "none" else None), usage

    PHOTO_SCHEMA = {"type": "object", "properties": {"best": {"type": "integer"}}, "required": ["best"], "additionalProperties": False}
    PHOTO_ASK = ("These are candidate photos, numbered from 0, for an Arabic football news article with the headline below. "
                 "Pick the one that best shows what the news is about: the player, the club or the event it names. A photo from a news "
                 "outlet covering this story is usually the right one; an archive photo found by name only when it clearly shows that "
                 "person playing football. Never pick: a painting, artwork or drawing; a building, city, landscape or monument; a "
                 "site's logo, a graphic or card full of text; an advert; an old team photo; or a photo of someone else. If none fits, "
                 "answer -1.\n\nHeadline: ")

    def pick_photo(self, headline, thumbs, model="claude-haiku-5-5", sources=None):
        """-> (index of the best photo or -1, usage). One small call: the thumbnails are 512 px at most. sources: where each photo
        came from (an outlet covering the story, or Wikimedia Commons: an archive photo found by name)."""
        content = []
        for i, t in enumerate(thumbs):
            src = (sources or [None] * len(thumbs))[i]
            where = "" if src is None else " (archive photo found by name)" if src == "ويكيميديا كومنز" else " (from a news outlet covering this story)"
            content += [{"type": "text", "text": f"Photo {i}{where}:"},
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(t).decode()}}]
        content.append({"type": "text", "text": self.PHOTO_ASK + headline})
        msg = self._c().messages.create(model=model, max_tokens=200, messages=[{"role": "user", "content": content}],
                                        output_config={"format": {"type": "json_schema", "schema": self.PHOTO_SCHEMA}})
        text = next((b.text for b in msg.content if b.type == "text"), "")
        try:
            best = int(json.loads(text)["best"])
        except (ValueError, KeyError, TypeError) as e:
            raise WriteError("photo answer cannot be read: " + repr(text[:80])) from e      # news_pick then keeps the widest
        if not -1 <= best < len(thumbs):
            raise WriteError(f"photo answer {best} is not one of {len(thumbs)}")
        u = msg.usage
        usage = {"in": u.input_tokens or 0, "out": u.output_tokens or 0,
                 "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0, "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0}
        return best, usage
