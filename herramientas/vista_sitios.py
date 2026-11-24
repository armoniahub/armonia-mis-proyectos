#!/usr/bin/env python3
"""vista_sitios.py — lo pendiente de varios sitios en una sola vista (la guía del agente, sección 8).

    python -I herramientas/vista_sitios.py OBJETIVOS --sitio NOMBRE=BANDEJA ... [--existente NOMBRE=BANDEJA ...]

  OBJETIVOS   su objetivos.md (de ahí sale el interruptor `orquestar:`; si no existe, vale auto, y lo dice)
  --sitio     los sitios de su última firma del rumbo, en su orden: cuentan para encenderla en auto
  --existente los proyectos que pidió adoptar: salen en la vista, pero no cuentan para encenderla
  (cada opción puede ir una vez con varios sitios detrás, o repetida; lo que no entiende lo dice, no lo deja caer)

De cada archivo .md de la raíz de cada bandeja (sin el README) lee SOLO tres campos de su cabecera: `jira:`, `fecha:` y
`estado:`, y solo si tienen la forma de siempre. Nunca el nombre del archivo, el título, el texto ni ningún otro campo.
No escribe nada: la vista sale por pantalla y no se guarda. Solo usa la biblioteca estándar de Python.
"""
from __future__ import annotations

import datetime
import os
import re
import sys
from pathlib import Path

# --- bloque común: desde aquí ---
ORQUESTAR = ("auto", "encendido", "apagado")
MIN_SITIOS_AUTO = 2
TOPE_VISTA = 7                                  # como la cola de una persona
CLAVE = re.compile(r"[A-Z][A-Z0-9]{1,9}-[0-9]{1,6}")      # solo cifras ASCII
FECHA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
ESTADOS = ("pendiente", "todo", "por-hacer", "en-curso", "doing", "bloqueado", "esperando", "hecho", "cerrado", "done")
EN_CURSO = ("en-curso", "doing")
CERRADOS = ("hecho", "cerrado", "done")         # no cuentan como pendiente
LEER_HASTA = 8192                               # de cada ítem, solo el principio: la cabecera
OPCIONES = ("--sitio", "--existente")


def _cabecera(texto: str) -> dict | None:
    """Los tres campos de la cabecera `---` de un MD, sin interpretar nada más. None si no tiene cabecera."""
    lineas = texto.lstrip("﻿").replace("\r\n", "\n").split("\n")
    if not lineas or lineas[0].strip() != "---":
        return None
    campos = {}
    for linea in lineas[1:]:
        if linea.strip() == "---":
            return campos
        m = re.fullmatch(r"(jira|fecha|estado):[ \t]*(.*?)[ \t]*(#.*)?", linea)
        if m and m.group(1) not in campos:
            campos[m.group(1)] = m.group(2).strip("\"'")
    return None            # sin cierre: no es una cabecera


def _fecha_iso(v: str) -> str | None:
    if not FECHA.fullmatch(v or ""):
        return None
    try:
        return datetime.date.fromisoformat(v).isoformat()
    except ValueError:
        return None


def _lleva_fuera(p: Path) -> bool:
    """¿Es un enlace (simbólico o, en Windows, una junction u otro punto de análisis) que puede llevar fuera?
    Con cualquier Python: si no se puede saber, cuenta como que sí."""
    if p.is_symlink():
        return True
    es_junction = getattr(p, "is_junction", None)          # Python 3.12 o más
    if es_junction is not None and es_junction():
        return True
    try:
        atributos = getattr(os.lstat(p), "st_file_attributes", 0)   # solo existe en Windows
    except OSError:
        return True
    return bool(atributos & 0x400)                          # FILE_ATTRIBUTE_REPARSE_POINT


def leer_bandeja(carpeta) -> list[dict] | None:
    """Lo pendiente de una bandeja: de cada ítem, solo clave, fecha y estado (lo hecho, cerrado o done no cuenta).
    None si no se ve desde aquí: una ruta vacía, una carpeta que no está o es un enlace, o sin ningún .md con cabecera
    legible (por ejemplo, solo su README, o una cola que vive en JIRA)."""
    if carpeta is None or not str(carpeta).strip():
        return None
    carpeta = Path(carpeta)
    try:
        if not carpeta.is_dir() or _lleva_fuera(carpeta):
            return None
        archivos = sorted(carpeta.glob("*.md"))
    except OSError:
        return None
    filas, legibles = [], 0
    for f in archivos:
        try:
            if f.name.lower() == "readme.md" or _lleva_fuera(f) or not f.is_file():
                continue
            with f.open(encoding="utf-8", errors="replace") as h:
                cab = _cabecera(h.read(LEER_HASTA))
        except (OSError, ValueError):
            cab = None
        if cab is None:
            continue
        legibles += 1
        clave, fecha = cab.get("jira", ""), _fecha_iso(cab.get("fecha", ""))
        estado = (cab.get("estado") or "pendiente").lower()
        estado = estado if estado in ESTADOS else "otro"
        if estado in CERRADOS:
            continue
        filas.append({"clave": clave if CLAVE.fullmatch(clave) else "sin clave",
                      "fecha": fecha or "sin fecha", "estado": estado})
    return filas if legibles else None


def normalizar(v) -> str | None:
    """auto, encendido o apagado (sin comillas ni mayúsculas); vacío o ausente es auto; None si no vale."""
    v = "" if v is None else str(v).strip().strip("\"'").strip().lower()
    return "auto" if v == "" else (v if v in ORQUESTAR else None)


_NOMBRA_ORQUESTAR = re.compile(r"""\s*["']?orquestar["']?\s*:""", re.I)
_ORQUESTAR = re.compile(r"""orquestar:[ \t]*("[^"]*"|'[^']*'|[^#]*?)[ \t]*(#.*)?""")


def leer_interruptor(texto_objetivos: str | None) -> tuple[str | None, str]:
    """(valor, motivo). El interruptor de la cabecera `---` de objetivos.md, cerrado ante la duda: valor None (no se
    enseña la vista) si el texto no se pudo leer, la cabecera no se cierra, `orquestar:` va dos veces, alguna línea lo
    nombra sin la forma de siempre, o su valor no vale. Sin el campo, vale auto."""
    if texto_objetivos is None:
        return None, "tu objetivos.md no se puede leer (tiene que estar en UTF-8)"
    lineas = re.split(r"\r\n|\r|\n", texto_objetivos.lstrip("\ufeff"))
    if not lineas or lineas[0].strip() != "---":
        if any(_NOMBRA_ORQUESTAR.match(l) for l in lineas):
            return None, "tu objetivos.md nombra `orquestar:`, pero no tiene la cabecera `---` de siempre"
        return "auto", ""
    valores = []
    for linea in lineas[1:]:
        if linea.strip() == "---":
            if not valores:
                return "auto", ""
            if len(valores) > 1:
                return None, "`orquestar:` va dos veces en tu objetivos.md"
            valor = normalizar(valores[0])
            return (valor, "") if valor else (None, "`orquestar:` no vale auto, encendido ni apagado")
        m = _ORQUESTAR.fullmatch(linea)
        if m:
            valores.append(m.group(1))
        elif _NOMBRA_ORQUESTAR.match(linea):
            return None, "una línea de tu objetivos.md nombra `orquestar:` sin la forma de siempre (orquestar: valor)"
    return None, "la cabecera de tu objetivos.md no se cierra con `---`"


def orquestar(texto_objetivos: str | None) -> str | None:
    """El valor del interruptor (auto, encendido o apagado), o None si no vale: ver leer_interruptor()."""
    return leer_interruptor(texto_objetivos)[0]


def leer_objetivos(ruta) -> tuple[str | None, str]:
    """(texto, nota). Un archivo que no existe vale auto y la nota lo dice; uno que no se puede leer en UTF-8, None."""
    p = Path(ruta) if ruta is not None and str(ruta).strip() else None
    if p is None or not p.exists():
        return "", f"no encuentro {ruta or 'objetivos.md'}: vale auto"
    try:
        return p.read_bytes().decode("utf-8"), ""
    except (OSError, UnicodeError):
        return None, ""


def orquestacion(valor: str | None, n_firmados: int, motivo: str = "") -> tuple[bool, str]:
    """¿Está encendida?, y por qué. Solo cuentan los sitios de su firma."""
    if valor is None:
        return False, f"sin vista: {motivo or '`orquestar:` no se entiende (vale auto, encendido o apagado)'}"
    if valor == "apagado":
        return False, "apagada: la apagaste tú"
    if valor == "encendido":
        return True, "encendida: la pediste tú"
    if n_firmados >= MIN_SITIOS_AUTO:
        return True, f"encendida sola: cuelgan {n_firmados} sitios de tu rumbo"
    s = "" if n_firmados == 1 else "s"
    pedirla = "; si la quieres igual, pídela con `orquestar: encendido`" if n_firmados else ""
    return False, (f"apagada: cuelga{'n' if s else ''} {n_firmados} sitio{s} de tu rumbo (se enciende sola con "
                   f"{MIN_SITIOS_AUTO}){pedirla}")


def _orden_clave(clave: str) -> tuple:
    """Por su prefijo y su número (el 9 antes que el 10); «sin clave» al final."""
    m = re.fullmatch(r"([A-Z][A-Z0-9]*)-([0-9]+)", clave)
    return (0, m.group(1), int(m.group(2))) if m else (1, "", 0)


def vista_sitios(sitios: list, ahora: datetime.datetime | None = None) -> str:
    """`sitios`: [(nombre, filas o None[, firmado])], los firmados en su orden y detrás los adoptados (firmado=False).
    Cada nombre, una sola vez. Orden: lo en curso primero, luego el orden de los sitios, dentro de
    cada uno lo más antiguo (lo sin fecha al final) y, a igualdad, por clave."""
    ahora = ahora or datetime.datetime.now()
    lineas = [f"Lo pendiente de tus sitios · leído a las {ahora:%H:%M}"]
    items, candidatos, vistos = [], [], set()
    for orden, sitio in enumerate(sitios):
        nombre, filas, es_firmado = (tuple(sitio) + (True,))[:3]
        if nombre in vistos:
            continue
        vistos.add(nombre)
        if filas is None:
            lineas.append(f"- {nombre}: no visible desde aquí")
            continue
        curso = sum(1 for f in filas if f["estado"] in EN_CURSO)
        lineas.append(f"- {nombre}: {len(filas)} pendiente{'' if len(filas) == 1 else 's'}"
                      + (f", {curso} en curso" if curso else ""))
        if filas:
            candidatos.append((-curso, orden, nombre, curso, bool(es_firmado)))
        for f in filas:
            items.append((0 if f["estado"] in EN_CURSO else 1, orden, f["fecha"] == "sin fecha", f["fecha"], _orden_clave(f["clave"]),
                          nombre, f))
    items.sort(key=lambda t: t[:5])
    if not items:
        return "\n".join(lineas + ["", "Nada pendiente que se vea desde aquí."])
    lineas.append("")
    for *_, nombre, f in items[:TOPE_VISTA]:
        lineas.append(f"  {nombre} · {f['clave']} · {f['fecha']} · {f['estado']}")
    if len(items) > TOPE_VISTA:
        lineas.append(f"  y {len(items) - TOPE_VISTA} más, fuera de la vista (el tope es {TOPE_VISTA})")
    _, _, sitio, curso, es_firmado = min(candidatos)
    if curso:
        empate = sum(1 for c in candidatos if c[3] == curso) > 1
        desempate = ("" if not empate else ", y el primero que firmaste de los que empatan" if es_firmado
                     else ", y el primero de los que empatan")
        adoptado = "" if es_firmado else " (es un proyecto que pediste adoptar)"
        porque = (f"es el que más tiene en curso ({curso}){desempate}{adoptado}: lo empezado se termina antes de abrir "
                  "otra cosa")
    elif es_firmado:
        porque = "nada está en curso, y es el primero de tus sitios, en el orden que firmaste, con algo pendiente"
    else:
        porque = ("nada está en curso, y ninguno de los sitios que firmaste tiene algo pendiente que se vea desde aquí: "
                  "es el primero de los proyectos que pediste adoptar")
    return "\n".join(lineas + ["", f"Te recomiendo ir a {sitio}: {porque}. Allí lo lleva su agente."])


def argumentos(argv: list, otras: tuple = ()) -> tuple[list, list, list]:
    """(firmados, adoptados, avisos) de `--sitio NOMBRE=BANDEJA ...` y `--existente NOMBRE=BANDEJA ...`, cada opción
    una o varias veces. Lo que no entiende va a avisos, nunca se deja caer ni se toma por un sitio: una opción que no
    conoce (también `--existente=…`), una opción sin nada detrás, un valor sin NOMBRE=, o un nombre repetido con otra
    bandeja. `otras`: opciones sin valor que se aceptan."""
    firmados, adoptados, avisos = [], [], []
    actual, opcion, contados, vistos = None, None, 0, {}

    def cerrar():
        if opcion is not None and contados == 0:
            avisos.append(f"«{opcion}» va sin ningún sitio detrás")

    for a in argv:
        if a in OPCIONES or a in otras or a.startswith("-"):
            cerrar()
            opcion, contados = (a, 0) if a in OPCIONES else (None, 0)
            actual = firmados if a == "--sitio" else adoptados if a == "--existente" else None
            if a not in OPCIONES and a not in otras:
                avisos.append(f"no conozco «{a}»: va como --sitio NOMBRE=BANDEJA o --existente NOMBRE=BANDEJA")
            continue
        if actual is None or "=" not in a or not a.split("=", 1)[0].strip():
            avisos.append(f"no entiendo «{a}»: va como --sitio NOMBRE=BANDEJA o --existente NOMBRE=BANDEJA")
            continue
        nombre, ruta = a.split("=", 1)
        nombre = nombre.strip()
        contados += 1
        if nombre in vistos and vistos[nombre] != ruta:
            avisos.append(f"«{nombre}» va dos veces con bandejas distintas: uso la primera")
            continue
        if nombre in vistos:
            continue
        vistos[nombre] = ruta
        actual.append((nombre, ruta))
    cerrar()
    return firmados, adoptados, avisos
# --- bloque común: hasta aquí ---


def main(argv: list) -> int:
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        return 2
    firmados, adoptados, avisos = argumentos(argv[1:])
    for aviso in avisos:
        print(f"Aviso: {aviso}")
    texto, nota = leer_objetivos(argv[0])
    valor, motivo = leer_interruptor(texto)
    encendida, porque = orquestacion(valor, len({n for n, _ in firmados}), motivo)
    print(f"Varios sitios a la vez: {porque}." + (f" ({nota})" if nota else ""))
    if valor is None:
        print("Corrígelo con ella y vuelve a mirar; hasta entonces, no enseño la vista.")
        return 1
    if encendida:
        print(vista_sitios([(n, leer_bandeja(c), True) for n, c in firmados]
                           + [(n, leer_bandeja(c), False) for n, c in adoptados]))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.exit(main(sys.argv[1:]))
