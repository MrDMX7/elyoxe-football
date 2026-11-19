"""Man of the match (spec §8): FotMob's «Player of the Match» is the match's highest FotMob rating, so every match with
ratings gets the player with the highest rating among those who played (ties: more goals + assists, then more minutes,
then the lower Tifo id). A match without ratings gets no pick."""


def load(G, reg, S):
    best = {}
    for mid, pid, tid, rating, ga, mins in G.c.execute("""SELECT mid, pid, tid, rating, coalesce(goals,0)+coalesce(assists,0), coalesce(minutes,0)
                                                          FROM appearance WHERE rating IS NOT NULL AND played=1"""):
        key = (rating, ga, mins, -pid)
        if mid not in best or key > best[mid][0]:
            best[mid] = (key, pid, tid, rating)
    G.c.executemany("INSERT OR REPLACE INTO match_award(mid, kind, pid, tid, value, src) VALUES(?, 'motm', ?, ?, ?, 'fotmob-rating')",
                    [(mid, pid, tid, f"{rating:g}") for mid, (_, pid, tid, rating) in sorted(best.items())])
    return {"matches": len(best)}
