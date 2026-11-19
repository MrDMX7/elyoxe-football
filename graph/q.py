"""Read-only questions to tifo.db: python -m graph.q "select count(*) from match" """
import os, sqlite3, sys

DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "tifo.db")


def query(sql, params=(), path=None):
    c = sqlite3.connect(f"file:{(path or DEFAULT).replace(os.sep, '/')}?mode=ro", uri=True)
    try:
        return c.execute(sql, params).fetchall()
    finally:
        c.close()


if __name__ == "__main__":
    for row in query(sys.argv[1]):
        print("\t".join("" if v is None else str(v) for v in row))
