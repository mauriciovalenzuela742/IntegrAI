"""Normas preliminares de seis hitos motores OMS; todos los umbrales requieren revisión."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

RUTA = Path(__file__).with_name("normas.json")
ZONAS = ("esperable", "estimular", "atencion", "fuera_de_ventana")


@dataclass(frozen=True)
class Hito:
    id: str
    nombre: str
    p1: float
    p50: float
    p75: float
    p99: float
    edad_cdc: float | None
    pagina_oms: int
    fuente_oms: str
    fuente_cdc: str | None
    equivalencia_cdc: str
    consultas_es: tuple[str, ...]
    consultas_en: tuple[str, ...]
    implica: tuple[str, ...]

    @property
    def a(self) -> float:
        return self.edad_cdc if self.edad_cdc is not None else self.p75


def cargar(ruta: Path = RUTA) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


def hitos() -> tuple[Hito, ...]:
    return tuple(Hito(**{**fila, "consultas_es": tuple(fila["consultas_es"]),
                         "consultas_en": tuple(fila["consultas_en"]),
                         "implica": tuple(fila["implica"])}) for fila in cargar()["hitos"])


def hito(hito_id: str) -> Hito:
    try:
        return next(item for item in hitos() if item.id == hito_id)
    except StopIteration as exc:
        raise KeyError(f"hito desconocido: {hito_id}") from exc


def zona(hito_o_id: Hito | str, edad_meses: float) -> str:
    item = hito(hito_o_id) if isinstance(hito_o_id, str) else hito_o_id
    if edad_meses < item.p50:
        return "esperable"
    if edad_meses > item.p99:
        return "fuera_de_ventana"
    if edad_meses < item.a:
        return "estimular"
    return "atencion"


def consultas_hito(hito_id: str) -> tuple[str, str]:
    item = hito(hito_id)
    return " ".join(item.consultas_es), " ".join(item.consultas_en)


def implicados_por(hito_id: str) -> tuple[str, ...]:
    return hito(hito_id).implica


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hito", nargs="?")
    parser.add_argument("--edad", type=float)
    args = parser.parse_args()
    if args.hito:
        item = hito(args.hito)
        print(json.dumps({**item.__dict__, "A": item.a,
                          "zona": zona(item, args.edad) if args.edad is not None else None},
                         ensure_ascii=False, indent=2))
    else:
        for item in hitos():
            print(f"{item.id}: p50={item.p50}, A={item.a}, p99={item.p99}, revisado=false")


if __name__ == "__main__":
    _main()
