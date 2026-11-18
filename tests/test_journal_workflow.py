"""The journal workflow (final review, finding 7): the articles and Search Console steps run after the journal's own state is
saved, each with its own short timeout, never failing the job, and only they see the API key and the service account."""
from pathlib import Path
import yaml

WF = yaml.safe_load((Path(__file__).resolve().parents[1] / ".github" / "workflows" / "tifo-journal.yml").read_text(encoding="utf-8"))
STEPS = WF["jobs"]["journal"]["steps"]
IDX = {s.get("name"): i for i, s in enumerate(STEPS)}


def step(name):
    return STEPS[IDX[name]]


def test_articles_run_after_the_journal_state_is_saved():
    assert IDX["State for the next run"] < IDX["Tifo articles"] < IDX["Usage lines for the laptop's cost report"]
    assert IDX["State for the next run"] < IDX["Articles in Google (weekly)"]


def test_the_new_steps_have_their_own_timeout_and_never_fail_the_job():
    for name in ("Tifo articles", "Articles in Google (weekly)"):
        s = step(name)
        assert s.get("continue-on-error") is True and 0 < s.get("timeout-minutes", 99) <= 10


def test_only_the_new_steps_see_the_secrets():
    assert "ANTHROPIC_API_KEY" in step("Tifo articles")["env"]
    assert "GSC_SA_JSON" in step("Articles in Google (weekly)")["env"]
    assert "env" not in step("Run the journal job")
    runner = (Path(__file__).resolve().parents[1] / "tools" / "runner.py").read_text(encoding="utf-8")
    assert "news.articles.run" not in runner and "tools.gsc_weekly" not in runner


def test_article_pages_go_up_right_after_the_articles_are_written():
    """Spec 2026-11-19 §7: within the minute, not at the next hourly build; never failing the job."""
    assert IDX["Tifo articles"] < IDX["Article pages"] < IDX["Usage lines for the laptop's cost report"]
    s = step("Article pages")
    assert s["run"] == "python -m news.articles.pages" and s.get("continue-on-error") is True and 0 < s.get("timeout-minutes", 99) <= 5
    assert any((x.get("uses") or "").startswith("actions/setup-node") for x in STEPS[:IDX["Article pages"]])
