# tests/test_articles_types.py
"""news/articles/types.json and style.md carry Phase 2a's decisions (spec: 60 a day, 20 minutes, Sonnet / Haiku)."""
import json
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "news" / "articles"
T = json.loads((D / "types.json").read_text(encoding="utf-8"))


def test_news_and_breaking_are_configured_and_on():
    """Switched on by the owner 2026-11-19."""
    assert T["news"] == {"on": True, "model": "claude-sonnet-5-5", "words": [250, 450], "daily": 60, "wait_minutes": 20,
                         "per_hour": 4}
    assert T["breaking"] == {"on": True, "model": "claude-haiku-5-5", "words": [80, 160]}


def test_the_style_guide_has_the_news_and_breaking_rules():
    s = (D / "style.md").read_text(encoding="utf-8")
    assert "الطول من 250 إلى 450 كلمة" in s and "«عاجل»: إذا كان «النوع» في الورقة «عاجل»" in s
