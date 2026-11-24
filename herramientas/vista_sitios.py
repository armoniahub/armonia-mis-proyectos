#!/usr/bin/env python3
"""vista_sitios.py — lo pendiente de varios sitios en una sola vista (la guía del agente, sección 8).

    python herramientas/vista_sitios.py OBJETIVOS --sitio NOMBRE=BANDEJA ... [--existente NOMBRE=BANDEJA ...]

  OBJETIVOS   su objetivos.md (de ahí sale el interruptor `orquestar:`; si no existe, vale auto)
  --sitio     los sitios de su última firma del rumbo, en su orden: cuentan para encenderla en auto
  --existente los proyectos que pidió adoptar: salen en la vista, pero no cuentan para encenderla

De cada archivo .md de la raíz de cada bandeja (sin el README) lee SOLO tres campos de su cabecera: `jira:`, `fecha:` y
`estado:`, y solo si tienen la forma de siempre. Nunca el nombre del archivo, el título, el texto ni ningún otro campo.
No escribe nada: la vista sale por pantalla y no se guarda. Solo usa la biblioteca estándar de Python.
"""
from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

ORQUESTAR = ("auto", "encendido", "apagado")
MIN_SITIOS_AUTO = 2
TOPE_VISTA = 7
CLAVE = re.compile(r"[A-Z][A-Z0-9]{1,9}-\d{1,6}")
FECHA = re.compile(r"\d{4}-\d{2}-\d{2}")
ESTADOS = ("pendiente", "todo", "por-hacer", "en-curso", "doing", "bloqueado", "esperando", "hecho", "cerrado")
EN_CURSO = ("en-curso", "doing")
CERRADOS = ("hecho", "cerrado")
LEER_HASTA = 8192          # solo el principio de cada archivo: la cabecera
CAMPOS = ("jira", "fecha", "estado")


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


def _fecha(v: str) -> str | None:
    if not FECHA.fullmatch(v or ""):
        return None
    try:
        return datetime.date.fromisoformat(v).isoformat()
    except ValueError:
        return None


def leer_bandeja(carpeta) -> list[dict] | None:
    """Lo pendiente de una bandeja: de cada ítem, solo clave, fecha y estado (lo hecho o cerrado no cuenta).
    None si no se ve desde aquí: la carpeta no está, o no tiene ningún .md con cabecera legible."""
    carpeta = Path(carpeta)
    if not carpeta.is_dir() or carpeta.is_symlink():
        return None
    filas, legibles = [], 0
    for f in sorted(carpeta.glob("*.md")):
        if f.name.lower() == "readme.md" or f.is_symlink() or not f.is_file():
            continue
        try:
            with f.open(encoding="utf-8") as h:
                cab = _cabecera(h.read(LEER_HASTA))
        except (OSError, UnicodeError, ValueError):
            cab = None
        if cab is None:
            continue
        legibles += 1
        clave, fecha, estado = cab.get("jira", ""), _fecha(cab.get("fecha", "")), cab.get("estado") or "pendiente"
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


def orquestar(texto_objetivos: str) -> str | None:
    """El interruptor de la cabecera `---` de objetivos.md (solo de la cabecera). None si trae un valor que no vale."""
    lineas = texto_objetivos.lstrip("\ufeff").replace("\r\n", "\n").split("\n")
    if not lineas or lineas[0].strip() != "---":
        return "auto"
    for linea in lineas[1:]:
        if linea.strip() == "---":
            break
        m = re.fullmatch(r"orquestar:[ \t]*(\"[^\"]*\"|'[^']*'|[^#]*?)[ \t]*(#.*)?", linea)
        if m:
            return normalizar(m.group(1))
    return "auto"


def orquestacion(valor: str, n_firmados: int) -> tuple[bool, str]:
    """¿Está encendida?, y por qué. Solo cuentan los sitios de su firma."""
    if valor == "apagado":
        return False, "apagada: la apagaste tú"
    if valor == "encendido":
        return True, "encendida: la pediste tú"
    if n_firmados >= MIN_SITIOS_AUTO:
        return True, f"encendida sola: cuelgan {n_firmados} sitios de tu rumbo"
    s = "" if n_firmados == 1 else "s"
    return False, f"apagada: cuelga{'n' if s else ''} {n_firmados} sitio{s} de tu rumbo (se enciende sola con {MIN_SITIOS_AUTO})"


def vista_sitios(sitios: list, ahora: datetime.datetime | None = None) -> str:
    """`sitios`: [(nombre, filas o None)], los firmados en su orden y detrás los adoptados. Cada nombre, una sola vez."""
    ahora = ahora or datetime.datetime.now()
    lineas = [f"Lo pendiente de tus sitios · leído a las {ahora:%H:%M}"]
    items, candidatos, vistos = [], [], set()
    for orden, (nombre, filas) in enumerate(sitios):
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
            candidatos.append((-curso, orden, nombre, curso))
        for f in filas:
            # «sin fecha» va detrás de cualquier fecha dentro de su sitio
            items.append((0 if f["estado"] in EN_CURSO else 1, orden, f["fecha"] == "sin fecha", f["fecha"], nombre, f))
    items.sort(key=lambda t: t[:4])
    if not items:
        return "\n".join(lineas + ["", "Nada pendiente que se vea desde aquí."])
    lineas.append("")
    for *_, nombre, f in items[:TOPE_VISTA]:
        lineas.append(f"  {nombre} · {f['clave']} · {f['fecha']} · {f['estado']}")
    if len(items) > TOPE_VISTA:
        lineas.append(f"  y {len(items) - TOPE_VISTA} más, fuera de la vista (el tope es {TOPE_VISTA})")
    _, _, sitio, curso = min(candidatos)
    if curso:
        empate = sum(1 for c in candidatos if c[3] == curso) > 1
        porque = (f"es el que más tiene en curso ({curso})" + (", y el primero que firmaste de los que empatan" if empate else "")
                  + ": lo empezado se termina antes de abrir otra cosa")
    else:
        porque = "nada está en curso, y es el primero de tus sitios, en el orden que firmaste, con algo pendiente"
    return "\n".join(lineas + ["", f"Te recomiendo ir a {sitio}: {porque}. Allí lo lleva su agente."])


def _pares(argv: list, opcion: str) -> list:
    if opcion not in argv:
        return []
    fuera = []
    for a in argv[argv.index(opcion) + 1:]:
        if a.startswith("--"):
            break
        if "=" in a:
            fuera.append(tuple(a.split("=", 1)))
    return fuera


def main(argv: list) -> int:
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        return 2
    try:
        texto = Path(argv[0]).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        texto = ""
    firmados, existentes = _pares(argv, "--sitio"), _pares(argv, "--existente")
    valor = orquestar(texto)
    if valor is None:
        print("Varios sitios a la vez: el campo `orquestar:` de tu objetivos.md no vale auto, encendido ni apagado. "
              "Corrígelo y vuelve a mirar; hasta entonces, no enseño la vista.")
        return 1
    encendida, porque = orquestacion(valor, len({n for n, _ in firmados}))
    print(f"Varios sitios a la vez: {porque}.")
    if encendida:
        print(vista_sitios([(n, leer_bandeja(c)) for n, c in firmados + existentes]))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.exit(main(sys.argv[1:]))
