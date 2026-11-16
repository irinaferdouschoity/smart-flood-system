"""District-name matching (handles common spellings)."""
import re

ALIASES = {
    "comilla": "cumilla", "bogra": "bogura", "jessore": "jashore",
    "chittagong": "chattogram", "barisal": "barishal", "coxbazar": "coxsbazar",
    "maulvibazar": "moulvibazar", "moulavibazar": "moulvibazar", "jhalakathi": "jhalokati",
    "jhalakati": "jhalokati", "netrakona": "netrokona", "khagrachari": "khagrachhari",
    "nawabganj": "chapainawabganj", "chapainababganj": "chapainawabganj",
    "chapainawabgonj": "chapainawabganj", "hobiganj": "habiganj", "hobigonj": "habiganj",
    "sirajgonj": "sirajganj", "kishorganj": "kishoreganj", "kishoregonj": "kishoreganj",
    "narshingdi": "narsingdi", "munshigonj": "munshiganj", "brahmanbaria": "brahmanbaria",
    "brahamanbaria": "brahmanbaria", "lakshmipur": "lakshmipur", "laksmipur": "lakshmipur",
}


def norm(name: str) -> str:
    key = re.sub(r"[^a-z]", "", str(name).lower())
    return ALIASES.get(key, key)
