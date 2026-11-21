"""names/verify.py: every Arabic player name checked against FotMob's own Arabic (api/translationmapping?locale=ar), a
second source by people, never a replacement: agree, consistent (FotMob's full name holds ours), differs, none."""
from names.verify import classify, report


def test_the_same_name_written_alike_agrees():
    assert classify("علي مبخوت", "علي مبخوت") == "agree"
    assert classify("عبد الكريم شحاتة", "عبد الكريم شحاته") == "agree"        # ة/ه, أ/ا, spaces are writing, not names
    assert classify("إبراهيم", "ابراهيم") == "agree"


def test_fotmobs_full_name_holding_ours_is_consistent():
    assert classify("علي طاهر", "علي طاهر إبراهيم عبد الله العلي") == "consistent"
    assert classify("زايد خميس", "زايد خميس الشيدي") == "consistent"
    assert classify("فاكوندو إنسفران", "فاكوندو إزيكييل إنسفران ليروسي") == "consistent"


def test_the_same_name_in_another_transliteration_is_spelling():
    assert classify("علي المعمري", "علي المعماري") == "spelling"             # FotMob is not always right: a person decides
    assert classify("كيفن أغوديلو", "كيفن أندريس أجوديلو أرديلا") == "spelling"
    assert classify("نسيم شاذلي", "نسيم الشاذلي") == "spelling" and classify("جواو فكتور", "جواو فيكتور") == "spelling"


def test_another_man_differs():
    assert classify("إيغور سيروتي", "إيجور إدواردو شليمبر") == "differs"
    assert classify("خليفة سبيعي", "خليفة عبد الرحمن صالح سمبيج") == "differs"


def test_no_fotmob_name_is_none():
    assert classify("ميلسون", None) == "none" and classify("ميلسون", "") == "none"


def test_the_report_counts_each_kind_and_lists_what_differs_with_both_names():
    ours = {"1": {"latin": "Ali Al Memari", "ar": "علي المعمري", "source": "generated"},
            "2": {"latin": "Ali Tahir", "ar": "علي طاهر", "source": "generated"},
            "3": {"latin": "Ali Mabkhout", "ar": "علي مبخوت", "source": "manual"},
            "4": {"latin": "Milson", "ar": "ميلسون", "source": "generated"}}
    fm = {"1": "علي المعماري", "2": "علي طاهر إبراهيم", "3": "علي مبخوت"}
    fm["5"], ours["5"] = "إيجور إدواردو شليمبر", {"latin": "Igor Serrote", "ar": "إيغور سيروتي", "source": "generated"}
    out = report(ours, fm, first={"1"})
    assert out["counts"] == {"agree": 1, "consistent": 1, "spelling": 1, "differs": 1, "none": 1}
    assert [(r["id"], r["kind"]) for r in out["review"]] == [("1", "spelling"), ("5", "differs")]   # the UAE's first
    assert out["status"] == {"1": "spelling", "2": "consistent", "3": "agree", "4": "none", "5": "differs"}


def test_abd_and_abu_written_joined_or_apart_are_one_name():
    assert classify("راشد عبدالله", "راشد عبد الله سهيل") == "consistent"
    assert classify("عبد الرحمن", "عبدالرحمن") == "agree"
