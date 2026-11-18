"""news/articles/write.py with a fake client (no network): the request carries the style guide as a cached system block, the
sheet, the schema, and on a rewrite the failures; a refusal or a cut-off answer is an error."""
import json, types
import pytest
from news.articles import write as W

ART = {"headline": "ع", "standfirst": "م", "sections": [{"subhead": "ق", "paragraphs": ["ف"]}], "facts_box": ["ح"], "sources_cited": ["بيانات تيفو"]}


class FakeStream:
    def __init__(self, msg): self.msg = msg
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def get_final_message(self): return self.msg


class FakeClient:
    def __init__(self, stop="end_turn", text=json.dumps(ART, ensure_ascii=False)):
        self.calls = []
        usage = types.SimpleNamespace(input_tokens=5000, output_tokens=2000, cache_read_input_tokens=3000, cache_creation_input_tokens=0)
        self.msg = types.SimpleNamespace(stop_reason=stop, usage=usage, content=[types.SimpleNamespace(type="text", text=text)])
        self.messages = types.SimpleNamespace(stream=self._stream)
    def _stream(self, **kw):
        self.calls.append(kw); return FakeStream(self.msg)


def test_the_request_and_the_parsed_answer():
    c = FakeClient()
    art, u = W.Writer(c).write("report", {"النوع": "تقرير مباراة"}, "claude-sonnet-5-5")
    assert art == ART and u == {"in": 5000, "out": 2000, "cache_read": 3000, "cache_write": 0}
    kw = c.calls[0]
    assert kw["model"] == "claude-sonnet-5-5"
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"} and "تيفو" in kw["system"][0]["text"]
    assert kw["output_config"]["format"]["schema"] == W.SCHEMA
    assert "تقرير مباراة" in kw["messages"][0]["content"]


def test_a_rewrite_carries_the_failures():
    c = FakeClient()
    W.Writer(c).write("report", {}, "claude-sonnet-5-5", notes=["number 7 is not in the sheet"])
    assert "number 7 is not in the sheet" in c.calls[0]["messages"][0]["content"]


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_a_refusal_or_a_cut_answer_is_an_error(stop):
    with pytest.raises(W.WriteError):
        W.Writer(FakeClient(stop=stop)).write("report", {}, "claude-sonnet-5-5")


def test_an_answer_without_the_schema_fields_is_an_error():
    # 2026-11-18 dry run: an answer with other keys (title, body…) went through and failed later at publish
    bad = json.dumps({"title": "ع", "body": "ف"}, ensure_ascii=False)
    with pytest.raises(W.WriteError):
        W.Writer(FakeClient(text=bad)).write("report", {}, "claude-sonnet-5-5")
