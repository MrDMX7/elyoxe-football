"""Offline tests: every source response comes from tests/fixtures/ (recorded 2026-09-26 from the live
sources, trimmed). No network."""
import json, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIX = ROOT / "tests" / "fixtures"


def load(name):
    with open(FIX / name, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def fx():
    return load
