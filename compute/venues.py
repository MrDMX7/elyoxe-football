"""Place a match at a stadium (stadiums.yaml) and measure distances to each emirate capital.

Resolution order: FotMob venue name (match detail) -> uaepl.ae stadium name (official, en or ar) ->
the home team's home_of entry. A match outside the UAE (Gulf Cup in Jeddah) resolves only through its
FotMob venue coordinates, carried as an ad-hoc stadium with in_uae=false.
"""
import math, re

import config

UAE_BBOX = (22.5, 26.3, 51.5, 56.5)   # lat_min, lat_max, lon_min, lon_max


def _key(s):
    return re.sub(r"\s+", " ", (s or "").replace("‎", "").replace("‏", "")).strip().lower()


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def in_uae(lat, lon):
    return lat is not None and UAE_BBOX[0] <= lat <= UAE_BBOX[1] and UAE_BBOX[2] <= lon <= UAE_BBOX[3]


class Venues:
    def __init__(self, stadiums=None, emirates=None):
        self.stadiums = stadiums if stadiums is not None else config.stadiums()
        self.emirates = emirates if emirates is not None else config._load("stadiums.yaml").get("emirates", [])
        self.by_name, self.by_home = {}, {}
        for s in self.stadiums:
            for n in [s.get("name_en"), s.get("name_ar"), s.get("fotmob_name")] + list(s.get("aliases") or []):
                if n:
                    self.by_name[_key(n)] = s
            for t in s.get("home_of") or []:
                self.by_home.setdefault(int(t), s)

    def resolve(self, match, fotmob_venue=None, uaepl_name=None):
        """-> stadium dict {id, name_en, name_ar, city, emirate, lat, lon, in_uae} or None."""
        for n in (fotmob_venue or {}).get("name"), uaepl_name, match.get("venue_name"), match.get("venue_name_ar"):
            s = self.by_name.get(_key(n)) if n else None
            if s:
                return self._out(s)
        v = fotmob_venue or {}
        if v.get("lat") is not None and v.get("lon") is not None:
            return {"id": None, "name_en": v.get("name"), "name_ar": None, "city": v.get("city"), "emirate": None,
                    "lat": float(v["lat"]), "lon": float(v["lon"]), "in_uae": in_uae(float(v["lat"]), float(v["lon"])),
                    "source": "fotmob"}
        s = self.by_home.get((match.get("home") or {}).get("id"))
        return self._out(s, guessed=True) if s else None

    def _out(self, s, guessed=False):
        return {"id": s["id"], "name_en": s.get("name_en"), "name_ar": s.get("name_ar") or None, "city": s.get("city"),
                "emirate": s.get("emirate"), "lat": s["lat"], "lon": s["lon"], "in_uae": in_uae(s["lat"], s["lon"]),
                "source": "home-team default" if guessed else "stadiums.yaml"}

    def distances(self, stadium):
        """{emirate id: km, straight line} from the stadium to each emirate point."""
        if not stadium or stadium.get("lat") is None:
            return None
        return {e["id"]: round(haversine_km(e["lat"], e["lon"], stadium["lat"], stadium["lon"]), 1) for e in self.emirates}
