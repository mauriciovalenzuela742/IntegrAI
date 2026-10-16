#!/usr/bin/env python3
"""Genera data/recomendaciones.json para la demo estática, siempre validado por Pydantic."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.recomendador.lote import SALIDA, escribir, generar  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max", type=int, dest="max_items")
    parser.add_argument("--cursos", help="lista id_jardin:sala separada por comas")
    parser.add_argument("--fecha-ref")
    parser.add_argument("--salida", type=Path, default=SALIDA)
    args = parser.parse_args()
    cursos = set(args.cursos.split(",")) if args.cursos else None
    lote = generar(fecha_ref=args.fecha_ref, max_items=args.max_items, cursos=cursos)
    escribir(lote, args.salida)
    print(f"ok: {len(lote.items)} recomendaciones validadas -> {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
