#!/usr/bin/env python3
"""Ingesta del corpus del recomendador: PDF públicos de RAG/ -> privado/rag/indice.json.

uso:
    python tools/rag_ingestar.py hashes                       # SHA-256 y tamaño de cada PDF (para el manifiesto)
    python tools/rag_ingestar.py verificar                    # SHA-256 de cada fuente contra src/recomendador/fuentes.json
    python tools/rag_ingestar.py texto <fuente_id|archivo> [pagina]   # texto extraído, para revisión humana
    python tools/rag_ingestar.py indexar [--sin-embeddings]   # fragmentos + embeddings Titan v2 -> privado/rag/indice.json

Requiere requirements-rag.txt (pypdf, fonttools). `indexar` sin `--sin-embeddings` necesita Bedrock
(Titan v2): si un embedding falla, no se escribe un índice a medias.

Los PDF públicos viven en RAG/. El índice con texto extraído vive en privado/ (.gitignore) y no se publica.
Los checklists del CDC (2021) usan fuentes Arial sin tabla ToUnicode: el código de cada carácter es
el número de glifo de Arial. Se decodifican con la tabla `_GLIFOS_ARIAL`, verificada contra el cmap
de arial.ttf (4503 glifos) el 15-oct-2026.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

TAM_FRAGMENTO = 900
TRASLAPE = 150

# Arial (Monotype) en orden de glifos: 3..97 = ASCII 0x20..0x7E (glifo + 29). El resto, verificado.
_GLIFOS_ARIAL = {171: "…", 177: "–", 178: "—", 179: "“", 180: "”", 181: "‘", 182: "’",
                 191: "fi", 192: "fl", 4231: "ff"}
# Familias con fuentes Type0 Identity-H sin ToUnicode: (desplazamiento ASCII, glifos especiales).
# Minion y Syntax: artículo de la OMS en Food and Nutrition Bulletin (2004), código + 32 = ASCII.
_FAMILIAS = {"Arial": (29, _GLIFOS_ARIAL), "Minion": (32, {}), "Syntax": (32, {})}


class ErrorIngesta(RuntimeError):
    pass


# --------------------------------------------------------------------------- texto de los PDF
def _tipo_mapa(font) -> str | None:
    """Familia a decodificar ('Arial', 'Minion', 'Syntax') o 'simbolo' para fuentes Type0 Identity-H
    sin ToUnicode; None si pypdf ya decodifica bien."""
    if font is None:
        return None
    try:
        font = font.get_object()
    except AttributeError:
        pass
    if font.get("/Subtype") != "/Type0" or "/ToUnicode" in font:
        return None
    nombre = str(font.get("/BaseFont", "")).lstrip("/").split("+")[-1]
    if nombre.startswith("Wingdings") or nombre.startswith("Symbol"):
        return "simbolo"
    for familia in _FAMILIAS:
        if nombre.startswith(familia):
            return familia
    return None


def decodificar(texto: str, familia: str = "Arial") -> str:
    """Código de glifo -> carácter. Los saltos y espacios que inserta pypdf entre operaciones se conservan."""
    desplazamiento, especiales = _FAMILIAS[familia]
    salida = []
    for c in texto:
        o = ord(c)
        if c in "\n\r ":
            salida.append(c)
        elif 0x20 <= o + desplazamiento <= 0x7E:
            salida.append(chr(o + desplazamiento))
        else:
            salida.append(especiales.get(o, ""))
    return "".join(salida)


def decodificar_arial(texto: str) -> str:
    return decodificar(texto, "Arial")


def limpiar(texto: str) -> str:
    texto = texto.replace("\u00a0", " ").replace("\r", "")
    texto = re.sub(r"(\w)-\n(\w)", r"\1\2", texto)          # palabra cortada al final de la línea
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = "\n".join(linea.strip() for linea in texto.split("\n"))
    texto = re.sub(r"(•\s*)+", "• ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def extraer_paginas(ruta: Path) -> list[str]:
    """Texto limpio de cada página (índice 0 = página 1 del PDF)."""
    import pypdf  # solo para la ingesta (requirements-rag.txt)
    lector = pypdf.PdfReader(str(ruta))
    paginas = []
    for pagina in lector.pages:
        partes: list[str] = []

        def visitante(texto, cm, tm, font, size, _partes=partes):
            tipo = _tipo_mapa(font)
            if tipo in _FAMILIAS:
                _partes.append(decodificar(texto, tipo))
            elif tipo == "simbolo":     # casillas y viñetas de los checklists
                _partes.append("".join("\n" if c == "\n" else "• " for c in texto if c.strip() or c == "\n"))
            else:
                _partes.append(texto)

        pagina.extract_text(visitor_text=visitante)
        paginas.append(limpiar("".join(partes)))
    return paginas


def fragmentar(texto: str, tam: int = TAM_FRAGMENTO, traslape: int = TRASLAPE) -> list[str]:
    """Fragmentos de ~`tam` caracteres con `traslape`, cortados en fin de línea, de oración o de palabra."""
    texto = texto.strip()
    if not texto:
        return []
    if len(texto) <= tam:
        return [texto]
    fragmentos: list[str] = []
    inicio = 0
    while inicio < len(texto):
        fin = min(len(texto), inicio + tam)
        if fin < len(texto):
            minimo = inicio + tam // 2
            corte = max(texto.rfind("\n", minimo, fin), texto.rfind(". ", minimo, fin))
            if corte <= inicio:
                corte = texto.rfind(" ", minimo, fin)
            if corte > inicio:
                fin = corte + 1
        fragmento = texto[inicio:fin].strip()
        if fragmento:
            fragmentos.append(fragmento)
        if fin >= len(texto):
            break
        siguiente = max(fin - traslape, inicio + 1)
        espacio = texto.find(" ", siguiente, fin)
        inicio = espacio + 1 if espacio != -1 else siguiente
    return fragmentos


# --------------------------------------------------------------------------- manifiesto y hashes
def sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def verificar_hashes(manifiesto: dict, dir_fuentes: Path) -> list[str]:
    """Problemas encontrados (vacío = todo calza). Las fuentes sin `archivo` son futuras y se omiten."""
    problemas = []
    for f in manifiesto.get("fuentes", []):
        if not f.get("archivo"):
            continue
        ruta = dir_fuentes / f["archivo"]
        if not ruta.exists():
            problemas.append(f"{f['id']}: falta el archivo {f['archivo']}")
        elif sha256_archivo(ruta) != f.get("sha256"):
            problemas.append(f"{f['id']}: el SHA-256 no calza con el manifiesto ({f['archivo']})")
    return problemas


def construir_indice(manifiesto: dict, dir_fuentes: Path, embedder=None,
                     manifiesto_sha256: str = "", extraer=extraer_paginas) -> dict:
    """Índice completo en memoria. Lanza ErrorIngesta si un hash no calza o si falla un embedding."""
    problemas = verificar_hashes(manifiesto, dir_fuentes)
    if problemas:
        raise ErrorIngesta("; ".join(problemas))
    fragmentos = []
    for f in manifiesto.get("fuentes", []):
        if not f.get("archivo"):
            continue
        for n_pag, texto in enumerate(extraer(dir_fuentes / f["archivo"]), start=1):
            for n_frag, frag in enumerate(fragmentar(texto), start=1):
                fragmentos.append({"id": f"{f['id']}#p{n_pag}-{n_frag}", "fuente_id": f["id"],
                                   "pagina": n_pag, "texto": frag})
    if embedder is not None:
        for i, frag in enumerate(fragmentos, start=1):
            vector = embedder.embed(frag["texto"])
            if not vector:
                raise ErrorIngesta(f"falló el embedding de {frag['id']}: no se escribe un índice a medias")
            frag["emb"] = [round(x, 6) for x in vector]
            if i % 50 == 0:
                print(f"  embeddings {i}/{len(fragmentos)}", flush=True)
    return {"version": 1, "creado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "manifiesto_sha256": manifiesto_sha256,
            "modelo_embeddings": getattr(embedder, "MODEL_ID", None) if embedder is not None else None,
            "n_fragmentos": len(fragmentos), "fragmentos": fragmentos}


# --------------------------------------------------------------------------- CLI
def _main(argv: list[str]) -> int:
    from src.recomendador import rag
    if not argv:
        print(__doc__)
        return 2
    comando = argv[0]
    if comando == "hashes":
        for ruta in sorted(rag.DIR_FUENTES.glob("*.pdf")):
            print(f"{sha256_archivo(ruta)}  {ruta.stat().st_size:>9}  {ruta.name}")
        return 0
    manifiesto = rag.cargar_manifiesto()
    if comando == "verificar":
        problemas = verificar_hashes(manifiesto, rag.DIR_FUENTES)
        for p in problemas:
            print("ERROR", p)
        n = sum(1 for f in manifiesto["fuentes"] if f.get("archivo"))
        print("ok: todas las fuentes calzan" if not problemas else f"{len(problemas)} problema(s) en {n} fuentes")
        return 1 if problemas else 0
    if comando == "texto":
        if len(argv) < 2:
            print("uso: texto <fuente_id|archivo> [pagina]")
            return 2
        fuentes = rag.fuentes_por_id(manifiesto)
        archivo = fuentes[argv[1]]["archivo"] if argv[1] in fuentes else argv[1]
        paginas = extraer_paginas(rag.DIR_FUENTES / archivo)
        elegidas = [int(argv[2])] if len(argv) > 2 else range(1, len(paginas) + 1)
        for n in elegidas:
            print(f"===== {archivo} · página {n}/{len(paginas)}\n{paginas[n - 1]}\n")
        return 0
    if comando == "indexar":
        embedder = None
        if "--sin-embeddings" not in argv:
            from src import config
            from src.matcher import Embedder
            embedder = Embedder() if not config.usar_mock() else None
            if embedder is None or not embedder.disponible:
                print("ERROR: Bedrock (Titan v2) no está disponible. Revisa AWS_PROFILE o usa --sin-embeddings.")
                return 1
        try:
            indice = construir_indice(manifiesto, rag.DIR_FUENTES, embedder, rag.sha256_manifiesto())
        except ErrorIngesta as e:
            print(f"ERROR: {e}")
            return 1
        rag.RUTA_INDICE.parent.mkdir(parents=True, exist_ok=True)
        temporal = rag.RUTA_INDICE.with_suffix(".tmp")
        temporal.write_text(json.dumps(indice, ensure_ascii=False), encoding="utf-8")
        temporal.replace(rag.RUTA_INDICE)
        por_fuente: dict[str, int] = {}
        for frag in indice["fragmentos"]:
            por_fuente[frag["fuente_id"]] = por_fuente.get(frag["fuente_id"], 0) + 1
        print(f"índice: {indice['n_fragmentos']} fragmentos · embeddings: {indice['modelo_embeddings'] or 'no (solo léxico)'}")
        for fid, n in por_fuente.items():
            print(f"  {n:4d}  {fid}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
