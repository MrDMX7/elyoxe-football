"""graph/load/schochastics.py unfold(): the dataset folded some clubs into another's name (24 Nov 2026: «Lens» is RC Lens and
RC Paris in every season both were in the division; before Lens came up it is RC Paris alone; «Nantes» of the 1930s is FC
Antibes). graph/sch_split/ says whose each row is."""
import datetime
import os

from graph.load.schochastics import SPLIT, unfold

D = datetime.date


def row(d, h, a, gh, ga):
    return (d, h, a, gh, ga, "france", "national", h.rsplit(" (", 1)[0], a.rsplit(" (", 1)[0], "FR")


def files(tmp_path, whole="", france=""):
    (tmp_path / "whole.csv").write_text("competition,ident,from,to,new\n" + whole, encoding="utf-8")
    (tmp_path / "france.csv").write_text("competition,date,home_ident,away_ident,gh,ga,new_home,new_away,kind\n" + france, encoding="utf-8")
    return str(tmp_path)


def test_a_row_of_the_folded_club_takes_its_own_name_and_the_dropped_derby_comes_back(tmp_path):
    folder = files(tmp_path, france="france,1938-09-04,Lens (France),FC Metz (France),3,2,RC Paris (France),FC Metz (France),move\n"
                                    "france,1938-12-11,Lens (France),Lens (France),1,1,Lens (France),RC Paris (France),add\n")
    rows = [row(D(1938, 9, 4), "Lens (France)", "FC Metz (France)", 3, 2), row(D(1938, 9, 11), "Lens (France)", "FC Metz (France)", 2, 1)]
    out, n = unfold(rows, folder)
    assert [(str(r[0]), r[1], r[2], r[7], r[8]) for r in out] == [
        ("1938-09-04", "RC Paris (France)", "FC Metz (France)", "RC Paris", "FC Metz"),
        ("1938-09-11", "Lens (France)", "FC Metz (France)", "Lens", "FC Metz"),
        ("1938-12-11", "Lens (France)", "RC Paris (France)", "Lens", "RC Paris")]
    assert n["moved"] == 1 and n["added"] == 1 and n["move_without_row"] == 0
    assert out[2][5:7] == ("france", "national") and out[2][9] == "FR"


def test_a_name_is_wholly_the_other_club_between_two_dates(tmp_path):
    folder = files(tmp_path, whole="france,Nantes (France),1933-07-01,1939-06-30,FC Antibes (France)\n"
                                   "france,Lens (France),1933-07-01,1937-06-30,RC Paris (France)\n",
                   france="france,1937-07-01,Lens (France),Nantes (France),1,2,RC Paris (France),Nantes (France),move\n")
    rows = [row(D(1936, 7, 1), "Lens (France)", "Nantes (France)", 2, 0), row(D(1937, 7, 1), "Lens (France)", "Nantes (France)", 1, 2),
            row(D(1937, 7, 1), "Lens (France)", "Nantes (France)", 2, 4), row(D(1963, 9, 1), "Nantes (France)", "Lens (France)", 1, 0)]
    out, n = unfold(rows, folder)
    assert [(str(r[0]), r[1], r[2]) for r in out] == [
        ("1936-07-01", "RC Paris (France)", "FC Antibes (France)"),
        ("1937-07-01", "Lens (France)", "FC Antibes (France)"),
        ("1937-07-01", "RC Paris (France)", "FC Antibes (France)"),
        ("1963-09-01", "Nantes (France)", "Lens (France)")]
    assert out[0][7:9] == ("RC Paris", "FC Antibes")


def test_a_line_that_names_no_row_is_counted(tmp_path):
    folder = files(tmp_path, france="france,1950-01-01,Lens (France),FC Metz (France),9,9,RC Paris (France),FC Metz (France),move\n")
    out, n = unfold([row(D(1950, 1, 1), "Lens (France)", "FC Metz (France)", 1, 0)], folder)
    assert n["move_without_row"] == 1 and out[0][1] == "Lens (France)"


def test_no_folder_no_change(tmp_path):
    rows = [row(D(1950, 1, 1), "Lens (France)", "FC Metz (France)", 1, 0)]
    assert unfold(rows, str(tmp_path / "none")) == (rows, {})


def test_the_curated_lines_are_whole():
    import csv
    for f in os.listdir(SPLIT):
        with open(os.path.join(SPLIT, f), encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                if f == "whole.csv":
                    assert r["from"] <= r["to"] and r["ident"] != r["new"] and r["new"].endswith(")"), r
                else:
                    assert r["kind"] in ("move", "add") and r["new_home"] != r["new_away"] and int(r["gh"]) >= 0 and int(r["ga"]) >= 0, r
                    assert r["competition"] == f[:-4] and datetime.date.fromisoformat(r["date"]), r
