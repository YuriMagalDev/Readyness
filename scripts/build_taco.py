"""Transforma a TACO oficial (formatados/alimentos.csv do repo machine-learning-mocha/taco,
derivado da Tabela TACO 4a ed., NEPA/UNICAMP) no schema enxuto de src/nutrition/data/taco.csv.

Fonte: https://github.com/machine-learning-mocha/taco (formatados/alimentos.csv)
Schema de saída (por 100 g): nome,kcal,proteina,carboidrato,gordura

Uso: python scripts/build_taco.py <entrada_alimentos.csv> <saida_taco.csv>
Valores ausentes na fonte ("NA") ou traço ("Tr"/"*") viram 0.0; alimentos sem energia
numérica são descartados (não dá pra confiar no item).
"""
import csv
import sys


def _num(v):
    """Macro: NA/Tr/ausente vira 0.0; número parseia; lixo vira None."""
    if v is None:
        return None
    s = str(v).strip().strip('"')
    if s in ("", "NA", "Tr", "tr", "*", "**"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return None


def _energy(v):
    """Energia: NA/ausente vira None (descarta o alimento — não dá pra quantificar)."""
    if v is None:
        return None
    s = str(v).strip().strip('"')
    if s in ("", "NA", "Tr", "tr", "*", "**"):
        return None
    try:
        val = float(s)
    except ValueError:
        return None
    return val if val > 0 else None


def build(src_path: str, out_path: str) -> int:
    rows = []
    with open(src_path, encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            nome = (r.get("Descrição dos alimentos") or "").strip().strip('"')
            kcal = _energy(r.get("Energia..kcal."))
            prot = _num(r.get("Proteína..g."))
            carb = _num(r.get("Carboidrato..g."))
            gord = _num(r.get("Lipídeos..g."))
            if not nome or kcal is None:
                continue  # sem nome ou energia confiável: descarta
            rows.append((nome, kcal, prot or 0.0, carb or 0.0, gord or 0.0))

    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["nome", "kcal", "proteina", "carboidrato", "gordura"])
        for nome, kcal, prot, carb, gord in rows:
            w.writerow([nome, kcal, prot, carb, gord])
    return len(rows)


if __name__ == "__main__":
    n = build(sys.argv[1], sys.argv[2])
    print(f"escreveu {n} alimentos em {sys.argv[2]}")
