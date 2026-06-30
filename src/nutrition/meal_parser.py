import re

_GRAMS = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*g\s+(.*)$", re.I)
_UNIT = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s+(.*)$")


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def _macros(per100: dict, grams: float) -> dict:
    f = grams / 100.0
    return {k: per100[k] * f for k in ("kcal", "p", "c", "g")}


def _from_portion(hit: dict, qty: float) -> dict:
    pp = hit["per_portion"]
    return {k: pp[k] * qty for k in ("kcal", "p", "c", "g")}


def _parse_item(raw: str, db) -> dict:
    raw = raw.strip()
    m = _GRAMS.match(raw)
    if m:
        grams, name = _num(m.group(1)), m.group(2)
        hit = db.match(name)
        if hit and "per100" in hit:
            return {"raw": raw, "food": hit["name"], "grams": grams,
                    "recognized": True, **_macros(hit["per100"], grams)}
        if hit and "per_portion" in hit:
            qty = grams / hit["portion_g"]
            return {"raw": raw, "food": hit["name"], "grams": grams,
                    "recognized": True, **_from_portion(hit, qty)}
        return {"raw": raw, "name": name, "recognized": False}
    u = _UNIT.match(raw)
    if u:
        qty, name = _num(u.group(1)), u.group(2)
        # "2 scoops whey soldier" -> remove unidade de medida solta antes do nome custom
        name_clean = re.sub(r"^(scoops?|colheres?|unidades?|fatias?)\s+", "", name, flags=re.I)
        hit = db.match(name_clean)
        if hit and "per_portion" in hit:
            return {"raw": raw, "food": hit["name"], "grams": qty * hit["portion_g"],
                    "recognized": True, **_from_portion(hit, qty)}
        pg = db.portion_grams(name)
        hit2 = db.match(name)
        if pg and hit2 and "per100" in hit2:
            grams = qty * pg
            return {"raw": raw, "food": hit2["name"], "grams": grams,
                    "recognized": True, **_macros(hit2["per100"], grams)}
        return {"raw": raw, "name": name, "recognized": False}
    return {"raw": raw, "recognized": False}


def parse_meal(text: str, db) -> dict:
    text = (text or "").strip()
    meal = None
    if ":" in text:
        head, rest = text.split(":", 1)
        if len(head.split()) <= 2:        # "almoço", "café da manhã" curto
            meal, text = head.strip(), rest.strip()
    parts = [p for p in re.split(r"[,\n]", text) if p.strip()]
    items = [_parse_item(p, db) for p in parts] or [{"raw": text, "recognized": False}]
    return {"meal": meal, "items": items}
