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


_SALTOS_RAROS = re.compile("[\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029]")   # otros saltos de línea: duda
_NOMBRA_ORQUESTAR = re.compile(r"""orquestar["']?\s*:""", re.I)
# La única forma válida: en la columna 0, sin nada detrás o con espacios y valor, y si acaso espacios y #comentario.
_ORQUESTAR = re.compile(r"""orquestar:(?: +("[^"\\]*"|'[^']*'|[^\s#"']+))?(?: +#.*)? *""")
# Una línea de la columna 0 que empieza así no es una clave corriente de YAML (o abre algo que cambia cómo se lee): duda.
_RARA_EN_COLUMNA_0 = re.compile(r"""[?:*&!"'{\[%@`|>\-.]|<<""")


def _nombra_orquestar(linea: str) -> bool:
    """¿La línea lleva «orquestar» seguido de «:», en cualquier posición, y no es un comentario entero?"""
    return not linea.lstrip().startswith("#") and bool(_NOMBRA_ORQUESTAR.search(linea))


def _es_texto(linea: str) -> bool:
    """¿Lleva algo que no sea espacio ni un comentario entero?"""
    return bool(linea.strip()) and not linea.lstrip().startswith("#")


_CLAVE_YAML = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*:")
_SIGNOS = "-?:,[]{}#&*!|>'\"%@`"
# Lo que YAML no admite en un documento (lo rechaza entero) y los valores sueltos que lee como un número o una fecha, pero
# no puede construir: con ellos YAML no carga la cabecera, así que no se sabe qué diría. Duda.
_NO_IMPRIMIBLE = re.compile("[^\t\n\r\x20-\x7e\x85\xa0-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]")
_NUMERO_YAML = re.compile(r"[-+]?(?:0b[0-1_]+|0x[0-9a-fA-F_]+|0[0-7_]+|[0-9][0-9_]*(?:\.[0-9_]*)?(?:[eE][-+][0-9]+)?"
                          r"|\.[0-9_]+(?:[eE][-+][0-9]+)?)")
_FECHA_YAML = re.compile(r"([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})(?:(?:[Tt]|[ \t]+)[0-9]{1,2}:[0-9]{2}:[0-9]{2}.*)?")


def _plano_construible(valor: str) -> bool:
    """¿YAML puede construir este valor suelto? No si es «=» o «<<», un número sin cifras (0x_, 0b_, ._) o una fecha
    imposible (2026-02-30)."""
    if valor in ("=", "<<"):
        return False
    if _NUMERO_YAML.fullmatch(valor):
        v = valor.replace("_", "").lstrip("+-").lower()
        if v.startswith(("0x", "0b")):
            return len(v) > 2
        if v.startswith("0") and v.isdigit():
            return True
        try:
            float(v)
        except ValueError:
            return False
        return True
    m = _FECHA_YAML.fullmatch(valor)
    if m:
        try:
            datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return False
    return True


def _valor_simple(resto: str) -> bool | None:
    """Lo que va después de «clave:»: True si lleva un valor de forma simple, False si va vacío, None si no es simple."""
    if resto.strip(" ") == "":
        return False
    if not resto.startswith(" "):
        return None
    r = resto.lstrip(" ")
    if r.startswith("#"):
        return False
    if r[0] in "\"'":
        fin = r.find(r[0], 1)
        if fin < 0 or (r[0] == '"' and "\\" in r[1:fin]):
            return None
        detras = r[fin + 1:]
    elif r.startswith(("[]", "{}")):
        detras = r[2:]
    else:
        valor = r.split(" #", 1)[0].rstrip(" ")
        if valor[0] in _SIGNOS or ": " in valor or valor.endswith(":") or not _plano_construible(valor):
            return None
        return True
    return True if (detras.strip(" ") == "" or re.fullmatch(r" +#.*", detras)) else None


def _cabecera_simple(lineas: list) -> bool:
    """¿La cabecera es un mapa de YAML de forma tan simple que se lee seguro, con cada clave en su sitio? Claves y
    valores simples, listas con «- », sangrías solo con espacios y coherentes. Si no, no se sabe cómo la lee YAML."""
    return _linea_no_simple(lineas) == 0


def _linea_no_simple(lineas: list) -> int:
    """La primera línea (desde 1) de la cabecera que no es de la forma simple, o 0 si toda lo es (ver _cabecera_simple)."""
    pila, hijo_de = [(0, "mapa")], None      # colecciones abiertas (sangría, tipo); la clave que espera un bloque
    for i, linea in enumerate(lineas, 1):
        if "\t" in linea or _NO_IMPRIMIBLE.search(linea):
            return i
        if not _es_texto(linea):
            continue
        n = len(linea) - len(linea.lstrip(" "))
        c = linea[n:]
        if c.startswith("- "):
            if hijo_de is not None and (n > hijo_de or (n == hijo_de and pila[-1] == (n, "mapa"))):
                pila.append((n, "lista"))
            else:
                while pila[-1][0] > n:
                    pila.pop()
                if pila[-1] != (n, "lista"):
                    return i
            c, n, hijo_de = c[2:], n + 2, None
            if c[:1] == " " or not c.strip(" "):
                return i
            m = _CLAVE_YAML.match(c)
            if not m:
                if _valor_simple(" " + c) is not True:
                    return i
                continue
            pila.append((n, "mapa"))
        else:
            m = _CLAVE_YAML.match(c)
            if not m:
                return i
            if hijo_de is not None and n > hijo_de:
                pila.append((n, "mapa"))
            else:
                while pila[-1][0] > n or (pila[-1][0] == n and pila[-1][1] == "lista" and len(pila) > 1):
                    pila.pop()
                if pila[-1] != (n, "mapa"):
                    return i
        v = _valor_simple(c[m.end():])
        if v is None:
            return i
        hijo_de = n if v is False else None
    return 0


def leer_interruptor(texto_objetivos: str | None) -> tuple[str | None, str]:
    """(valor, motivo). El interruptor de la cabecera `---` de objetivos.md, cerrado ante la duda: valor None (no se
    enseña la vista) si el texto no se pudo leer, lleva saltos de línea raros, la cabecera no se cierra con `---` en la
    columna 0, `orquestar:` va dos veces, alguna línea lo nombra sin la única forma válida (`orquestar: valor`, en la
    columna 0), lo sigue una línea sangrada, alguna línea de la columna 0 empieza por un signo que cambia cómo se lee el
    YAML, o su valor no vale. Sin el campo, vale auto. El criterio es el de YAML: si da un valor y la cabecera carga,
    YAML lee lo mismo."""
    if texto_objetivos is None:
        return None, "tu objetivos.md no se puede leer (no es un archivo, o no está en UTF-8)"
    if _SALTOS_RAROS.search(texto_objetivos):
        return None, "tu objetivos.md lleva saltos de línea raros: guárdalo con saltos de línea normales"
    lineas = re.split(r"\r\n|\r|\n", texto_objetivos.lstrip("\ufeff"))
    if not lineas or lineas[0].rstrip(" ") != "---":
        if any(_nombra_orquestar(l) for l in lineas):
            return None, "tu objetivos.md nombra `orquestar:`, pero no tiene la cabecera `---` de siempre"
        return "auto", ""
    valores, esperando_siguiente = [], False
    for i, linea in enumerate(lineas[1:], 1):
        if linea.rstrip(" ") == "---":
            cabecera = lineas[1:i]
            if not valores:
                # Sin el campo, auto; salvo que YAML pudiera formar la clave de otra manera (con escapes, o con una
                # clave compleja): entonces, solo si la cabecera es de la forma simple.
                dudosa = any("orquestar" in l.lower() or "\\" in l for l in cabecera)
                n = _linea_no_simple(cabecera) if dudosa else 0
                if n:
                    return None, f"la cabecera de tu objetivos.md tiene una forma que no sé leer con seguridad (línea {n + 1})"
                return "auto", ""
            n = _linea_no_simple(cabecera)
            if n:
                return None, f"la cabecera de tu objetivos.md tiene una forma que no sé leer con seguridad (línea {n + 1})"
            if len(valores) > 1:
                return None, "`orquestar:` va dos veces en tu objetivos.md"
            valor = normalizar(valores[0])
            return (valor, "") if valor else (None, "`orquestar:` no vale auto, encendido ni apagado")
        if esperando_siguiente and _es_texto(linea):
            if linea[:1] in (" ", "\t"):
                return None, (f"a `orquestar:` lo sigue una línea sangrada (línea {i + 1}): escríbelo como "
                              "orquestar: valor, en una línea")
            esperando_siguiente = False
        if _es_texto(linea) and linea[:1] not in (" ", "\t") and _RARA_EN_COLUMNA_0.match(linea):
            return None, f"la línea {i + 1} de tu objetivos.md empieza por un signo que cambia cómo se lee"
        m = _ORQUESTAR.fullmatch(linea)
        if m:
            valores.append(m.group(1))
            esperando_siguiente = True
        elif _nombra_orquestar(linea):
            return None, f"la línea {i + 1} de tu objetivos.md nombra `orquestar:` sin la forma de siempre (orquestar: valor)"
    return None, "la cabecera de tu objetivos.md no se cierra con `---`"


def orquestar(texto_objetivos: str | None) -> str | None:
    """El valor del interruptor (auto, encendido o apagado), o None si no vale: ver leer_interruptor()."""
    return leer_interruptor(texto_objetivos)[0]


def leer_objetivos(ruta) -> tuple[str | None, str]:
    """(texto, nota). Un archivo que no existe vale auto y la nota lo dice; uno que no se puede leer en UTF-8, None."""
    p = Path(ruta) if ruta is not None and str(ruta).strip() else None
    if p is None or not p.exists():
        return "", f"no encuentro {_CONTROL.sub('?', str(ruta or 'objetivos.md'))}: vale auto"
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
    items, candidatos, vistos, hay_no_visible = [], [], set(), False
    for orden, sitio in enumerate(sitios):
        nombre, filas, es_firmado = (tuple(sitio) + (True,))[:3]
        if nombre in vistos:
            continue
        vistos.add(nombre)
        if filas is None:
            lineas.append(f"- {nombre}: no visible desde aquí")
            hay_no_visible = True
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
    if hay_no_visible and (curso or es_firmado):
        porque = "de lo que se ve desde aquí, " + porque
    return "\n".join(lineas + ["", f"Te recomiendo ir a {sitio}: {porque}. Allí lo lleva su agente."])


_CONTROL = re.compile("[\x00-\x1f\x7f-\x9f\u2028\u2029\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")


def argumentos(argv: list, otras: tuple = ()) -> tuple[list, list, list]:
    """(firmados, adoptados, avisos) de `--sitio NOMBRE=BANDEJA ...` y `--existente NOMBRE=BANDEJA ...`, cada opción
    una o varias veces. Lo que no entiende va a avisos, nunca se deja caer ni se toma por un sitio: una opción que no
    conoce (también `--existente=…`), una opción sin nada detrás, un valor sin NOMBRE=, un nombre o una ruta con
    caracteres de control o de formato, o un nombre repetido con otra bandeja. Después de algo que no entiende, deja de
    asignar hasta la opción siguiente, y el nombre de lo que dejó fuera queda reservado: si vuelve, tampoco se toma. Un nombre que va en --sitio y en --existente se avisa y se queda donde salió primero.
    `otras`: opciones sin valor que se aceptan."""
    firmados, adoptados, avisos = [], [], []
    actual, opcion, contados, vistos, reservados = None, None, 0, {}, set()
    forma = "va como --sitio NOMBRE=BANDEJA o --existente NOMBRE=BANDEJA"

    def cerrar():
        if opcion is not None and contados == 0:
            avisos.append(f"«{opcion}» va sin ningún sitio detrás")

    for a in argv:
        if a in OPCIONES or a in otras or a.startswith("-"):
            cerrar()
            opcion, contados = (a, 0) if a in OPCIONES else (None, 0)
            actual = firmados if a == "--sitio" else adoptados if a == "--existente" else None
            if a not in OPCIONES and a not in otras:
                avisos.append(f"no conozco «{_CONTROL.sub('?', a)}»: {forma}")
            continue
        if _CONTROL.search(a):
            avisos.append(f"un sitio lleva caracteres de control: lo dejo fuera ({forma})")
            reservados.add(_CONTROL.sub("", a.split("=", 1)[0]).strip())
            actual, opcion = None, None
            continue
        if actual is None or "=" not in a or not a.split("=", 1)[0].strip():
            avisos.append(f"no entiendo «{a}»: {forma}")
            if "=" in a:
                reservados.add(a.split("=", 1)[0].strip())
            actual, opcion = None, None
            continue
        nombre, ruta = a.split("=", 1)
        nombre = nombre.strip()
        contados += 1
        if nombre in reservados:
            avisos.append(f"«{nombre}» ya salió en algo que dejé fuera: tampoco lo tomo ahora; corrígelo")
            continue
        if nombre in vistos:
            if vistos[nombre] != ruta:
                avisos.append(f"«{nombre}» va dos veces con bandejas distintas: uso la primera")
            elif (actual is firmados) != ((nombre, ruta) in firmados):
                avisos.append(f"«{nombre}» va en --sitio y en --existente: lo dejo donde salió primero; corrígelo")
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
