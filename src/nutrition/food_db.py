import csv
import unicodedata

from rapidfuzz import process, fuzz


def normalize(name: str) -> str:
    """Normalize food name: lowercase, no accents, single spaces."""
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.lower().split())


ALIASES = {
    "frango": "peito de frango grelhado",
    "peito de frango": "peito de frango grelhado",
    "ovo": "ovo de galinha cozido",
    "ovos": "ovo de galinha cozido",
    "feijao": "feijao carioca cozido",
    "banana": "banana prata",
    "arroz": "arroz cozido",
}

PORTIONS = {
    "ovo": 50.0,
    "ovos": 50.0,
    "banana": 100.0,
    "fatia de pao": 25.0,
    "pao": 25.0,
}


class FoodDB:
    """Load and lookup foods from TACO CSV by normalized name."""

    def __init__(self, csv_path: str, custom=None):
        self._by_name = {}
        with open(csv_path, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                key = normalize(row["nome"])
                self._by_name[key] = {
                    "name": row["nome"],
                    "per100": {
                        "kcal": float(row["kcal"]),
                        "p": float(row["proteina"]),
                        "c": float(row["carboidrato"]),
                        "g": float(row["gordura"]),
                    },
                }
        self._custom = {}
        for key, c in (custom or {}).items():
            self._custom[normalize(key)] = c

    def lookup(self, name: str):
        """Lookup food by name (normalized); returns dict or None."""
        return self._by_name.get(normalize(name))

    def match(self, name: str, threshold: int = 85):
        """Match food by exact, alias, or fuzzy; returns dict with score or None."""
        key = normalize(name)
        if key in self._custom:
            c = self._custom[key]
            base = {"name": c["name"], "score": 100}
            if c["base_unit"] == "porcao":
                base["per_portion"] = c["macros"]
                base["portion_g"] = c["porcao_g"]
            else:
                base["per100"] = c["macros"]
            return base
        if key in self._by_name:
            item = self._by_name[key]
            return {**item, "score": 100}
        alias = ALIASES.get(key)
        if alias and normalize(alias) in self._by_name:
            item = self._by_name[normalize(alias)]
            return {**item, "score": 100}
        choices = list(self._by_name.keys())
        best = process.extractOne(key, choices, scorer=fuzz.WRatio)
        if best and best[1] >= threshold:
            item = self._by_name[best[0]]
            return {**item, "score": int(best[1])}
        return None

    def portion_grams(self, name: str):
        """Get standard portion size in grams for a food, or None."""
        key = normalize(name)
        c = self._custom.get(key)
        if c and c.get("porcao_g"):
            return c["porcao_g"]
        return PORTIONS.get(key)
