import csv
import unicodedata


def normalize(name: str) -> str:
    """Normalize food name: lowercase, no accents, single spaces."""
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.lower().split())


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

    def lookup(self, name: str):
        """Lookup food by name (normalized); returns dict or None."""
        return self._by_name.get(normalize(name))
