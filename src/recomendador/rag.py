"""Recuperación de pasajes de las fuentes profesionales (RAG local) para el recomendador.

- El índice `privado/rag/indice.json` lo genera `tools/rag_ingestar.py` desde los PDF públicos
  versionados en `RAG/`. Solo el índice con texto extraído permanece ignorado en `privado/`.
- Búsqueda híbrida: coseno con Titan v2 (si el índice tiene embeddings y hay Bedrock) + léxico.
  En modo mock, en la CI o sin índice: solo léxico, o nada, con un aviso por stderr.
- La consulta la arma el código, en español y en inglés (la OMS y el CDC están en inglés y la
  salida es en español). El LLM nunca elige qué buscar.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from .. import config

AQUI = Path(__file__).resolve().parent
RUTA_MANIFIESTO = AQUI / "fuentes.json"
DIR_PRIVADO = config.RAIZ / "privado" / "rag"
DIR_FUENTES = config.RAIZ / "RAG"
RUTA_INDICE = DIR_PRIVADO / "indice.json"

ALFA = 0.6                      # peso del componente semántico (igual que src/matcher.py)
SEM_LO, SEM_HI = 0.15, 0.55     # rango empírico del coseno de Titan v2 (src/matcher.py)
MAX_POR_FUENTE = 2              # diversidad: no más de 2 pasajes del mismo documento
MAX_EXTRACTO = 300              # largo máximo de un fragmento publicado (licencias: solo citas cortas)

_STOP = {
    # español
    "de", "la", "el", "los", "las", "un", "una", "unos", "unas", "que", "con", "por", "para", "en", "al",
    "del", "se", "su", "sus", "lo", "es", "como", "mas", "cuando", "donde", "sin", "sobre", "entre", "desde",
    "le", "les", "nos", "esta", "este", "esto", "ese", "esa", "son", "ser", "hay", "muy", "ya", "asi", "otro",
    "otra", "puede", "pueden", "tambien", "nino", "nina", "ninos", "ninas",
    # inglés
    "the", "and", "for", "with", "that", "this", "from", "are", "was", "were", "has", "have", "his", "her",
    "your", "you", "can", "will", "not", "but", "all", "any", "its", "who", "what", "when", "which", "into",
    "than", "then", "them", "they", "their", "there", "these", "those", "also", "such", "may", "more", "most",
    "baby", "babies", "child", "children",
}


def _aviso(mensaje: str) -> None:
    print(f"[rag] {mensaje}", file=sys.stderr, flush=True)


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes ni puntuación (para comparar términos)."""
    texto = unicodedata.normalize("NFKD", (texto or "").lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def tokens(texto: str) -> set[str]:
    """Raíces de 5 letras de las palabras con contenido (sentado/sentarse, crawl/crawling)."""
    return {t[:5] for t in normalizar(texto).split() if len(t) > 2 and t not in _STOP}


def _cos(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb + 1e-9)


# --------------------------------------------------------------------------- manifiesto de fuentes
def cargar_manifiesto(ruta: Path | None = None) -> dict:
    return json.loads((ruta or RUTA_MANIFIESTO).read_text(encoding="utf-8"))


def sha256_manifiesto(ruta: Path | None = None) -> str:
    """SHA-256 del manifiesto con fin de línea LF (igual en Windows con autocrlf y en Linux)."""
    texto = (ruta or RUTA_MANIFIESTO).read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def fuentes_por_id(manifiesto: dict) -> dict[str, dict]:
    return {f["id"]: f for f in manifiesto.get("fuentes", [])}


def _tipos(fuente: dict) -> set[str]:
    tipo = fuente.get("tipo") or []
    return {tipo} if isinstance(tipo, str) else set(tipo)


# --------------------------------------------------------------------------- índice y búsqueda
class Pasaje(BaseModel):
    """Un fragmento recuperado, con todo lo necesario para citarlo."""
    id: str                     # P1..Pk: lo que cita el redactor
    fragmento_id: str
    fuente_id: str
    titulo: str
    organizacion: str
    anio: int | None = None
    pagina: int                 # página del PDF (1 = primera), no el número impreso
    url: str
    idioma: str
    texto: str
    score: float


class Indice:
    def __init__(self, fragmentos: list[dict], fuentes: dict[str, dict],
                 modelo_embeddings: str | None = None, manifiesto_sha256: str | None = None) -> None:
        self.fragmentos = fragmentos
        self.fuentes = fuentes
        self.modelo_embeddings = modelo_embeddings
        self.manifiesto_sha256 = manifiesto_sha256
        self._tok = [tokens(f["texto"]) for f in fragmentos]

    @property
    def con_embeddings(self) -> bool:
        return bool(self.modelo_embeddings) and all(f.get("emb") for f in self.fragmentos)

    def buscar(self, consulta_es: str, consulta_en: str = "", tipo: str | None = None, k: int = 5,
               embedder=None, fuentes: set[str] | None = None,
               max_por_fuente: int = MAX_POR_FUENTE) -> list[Pasaje]:
        """Pasajes más pertinentes. `tipo` filtra por el tipo de la fuente (norma u orientacion)."""
        q_tok = tokens(consulta_es) | tokens(consulta_en)
        q_embs: list[list[float]] = []
        if embedder is not None and self.con_embeddings:
            for consulta in (consulta_es, consulta_en):
                if consulta.strip():
                    vector = embedder.embed(consulta)
                    if vector:
                        q_embs.append(vector)
        puntajes: list[tuple[float, int]] = []
        for i, frag in enumerate(self.fragmentos):
            fuente = self.fuentes.get(frag["fuente_id"])
            if fuente is None or (tipo and tipo not in _tipos(fuente)):
                continue
            if fuentes and frag["fuente_id"] not in fuentes:
                continue
            lexico = len(q_tok & self._tok[i]) / len(q_tok) if q_tok else 0.0
            if q_embs:
                sem = max(_cos(q, frag["emb"]) for q in q_embs)
                sem_r = min(1.0, max(0.0, (sem - SEM_LO) / (SEM_HI - SEM_LO)))
                puntaje = ALFA * sem_r + (1 - ALFA) * lexico
            else:
                puntaje = lexico
            if puntaje > 0:
                puntajes.append((puntaje, i))
        puntajes.sort(key=lambda x: (-x[0], self.fragmentos[x[1]]["id"]))   # empate: orden estable por id
        salida: list[Pasaje] = []
        por_fuente: dict[str, int] = {}
        for puntaje, i in puntajes:
            frag = self.fragmentos[i]
            if por_fuente.get(frag["fuente_id"], 0) >= max_por_fuente:
                continue
            por_fuente[frag["fuente_id"]] = por_fuente.get(frag["fuente_id"], 0) + 1
            fuente = self.fuentes[frag["fuente_id"]]
            salida.append(Pasaje(
                id=f"P{len(salida) + 1}", fragmento_id=frag["id"], fuente_id=frag["fuente_id"],
                titulo=fuente.get("titulo", ""), organizacion=fuente.get("organizacion", ""),
                anio=fuente.get("anio"), pagina=int(frag["pagina"]), url=fuente.get("url", ""),
                idioma=fuente.get("idioma", ""), texto=frag["texto"], score=round(puntaje, 4)))
            if len(salida) >= k:
                break
        return salida


def cargar_indice(ruta: Path | None = None, manifiesto: dict | None = None) -> Indice | None:
    """Lee el índice. Sin índice devuelve None (el recomendador sigue, pero sin pasajes)."""
    ruta = ruta or RUTA_INDICE
    if not ruta.exists():
        _aviso(f"no hay índice en {ruta.name}: sin pasajes (genéralo con tools/rag_ingestar.py indexar)")
        return None
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    if manifiesto is None:
        manifiesto = cargar_manifiesto()
        if datos.get("manifiesto_sha256") != sha256_manifiesto():
            _aviso("el índice se generó con otra versión de fuentes.json: conviene regenerarlo")
    return Indice(datos.get("fragmentos", []), fuentes_por_id(manifiesto),
                  datos.get("modelo_embeddings"), datos.get("manifiesto_sha256"))


@lru_cache(maxsize=1)
def indice_por_defecto() -> Indice | None:
    return cargar_indice()


def embedder_por_defecto():
    """Titan v2 (src/matcher.py) si hay Bedrock; None en modo mock o si no está disponible."""
    if config.usar_mock():
        return None
    try:
        from ..matcher import Embedder
        embedder = Embedder()
        return embedder if embedder.disponible else None
    except Exception:  # noqa: BLE001
        return None


def buscar(consulta_es: str, consulta_en: str = "", tipo: str | None = None, k: int = 5,
           indice: Indice | None = None, embedder=None) -> list[Pasaje]:
    """Búsqueda con el índice y el embedder por defecto (o los que se pasen, en tests)."""
    indice = indice or indice_por_defecto()
    if indice is None:
        return []
    if embedder is None and indice.con_embeddings:
        embedder = embedder_por_defecto()
    return indice.buscar(consulta_es, consulta_en, tipo=tipo, k=k, embedder=embedder)


def extracto(texto: str, consulta: str, max_len: int = MAX_EXTRACTO) -> str:
    """Fragmento LITERAL de `texto` (una subcadena), de hasta `max_len` caracteres, en la oración
    que más términos comparte con la consulta. Corta en límites de palabra."""
    q = tokens(consulta)
    mejor: tuple[int, int, int] | None = None
    for m in re.finditer(r"[^.\n•]+[.\n]?", texto):
        segmento = m.group(0)
        if len(segmento.strip()) < 15:
            continue
        puntaje = len(q & tokens(segmento))
        if mejor is None or puntaje > mejor[0]:
            mejor = (puntaje, m.start(), m.end())
    inicio, fin = (mejor[1], mejor[2]) if mejor else (0, len(texto))
    # se extiende a la oración siguiente si cabe (da contexto), sin pasar de max_len
    while fin < len(texto) and fin - inicio < max_len // 2:
        siguiente = re.match(r"[^.\n•]+[.\n]?", texto[fin:])
        if not siguiente or fin + len(siguiente.group(0)) - inicio > max_len:
            break
        fin += len(siguiente.group(0))
    segmento = texto[inicio:fin]
    if len(segmento.strip()) > max_len:
        corte = segmento.rfind(" ", 0, max_len)
        segmento = segmento[:corte if corte > max_len // 2 else max_len]
    return segmento.strip()


def _main(argv: list[str]) -> None:
    """python -m src.recomendador.rag <hito_id> [k]  → los mejores pasajes para un hito."""
    from . import normas
    if not argv:
        sys.exit(__doc__)
    hito = normas.hito(argv[0])
    k = int(argv[1]) if len(argv) > 1 else 5
    consulta_es, consulta_en = normas.consultas_hito(hito.id)
    print(f"consulta es: {consulta_es}\nconsulta en: {consulta_en}\n")
    for p in buscar(consulta_es, consulta_en, k=k):
        print(f"{p.id} [{p.score:.3f}] {p.organizacion} {p.anio} · {p.titulo[:70]} · p. {p.pagina} (PDF)")
        print("    «" + extracto(p.texto, consulta_es + " " + consulta_en).replace("\n", " ") + "»\n")


if __name__ == "__main__":
    _main(sys.argv[1:])
