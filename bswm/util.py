# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Utilidades comunes: seguridad de rutas, formato, slug y JSON atómico.

Sin dependencias externas (solo stdlib). `safe_join` / `is_within` son las mismas defensas
anti path-traversal que usa el model-manager: toda ruta que venga de la red pasa por aquí.
"""
import json
import os
import re
import tempfile

# Extensión canónica de los workflows de ComfyUI. Aceptamos .json (y .png con workflow embebido
# se trata como adjunto exportable, no editable: ver workflows.py).
WORKFLOW_EXTENSIONS = {".json"}

# Nombres que nunca mostramos/operamos como workflow (índices internos de ComfyUI y dotfiles).
IGNORED_BASENAMES = {".index.json"}


def human_size(num):
    """Convierte un número de bytes a texto legible (1.2 GB, 350 MB, ...)."""
    try:
        num = float(num or 0)
    except (TypeError, ValueError):
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(num) < 1024.0:
            if unit == "B":
                return f"{int(num)} {unit}"
            return f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} EB"


def is_workflow_file(path):
    """True si el archivo parece un workflow editable (.json y no un índice interno)."""
    base = os.path.basename(path)
    if base in IGNORED_BASENAMES or base.startswith("."):
        return False
    return os.path.splitext(path)[1].lower() in WORKFLOW_EXTENSIONS


def safe_join(root, *parts):
    """Une `root` con `parts` garantizando que el resultado queda DENTRO de `root`.

    Protege los endpoints HTTP (servir estáticos, leer, escribir, borrar, mover) frente a
    path-traversal (`..`), rutas absolutas y saltos de unidad en Windows.

    Lanza ValueError si el resultado se saldría de `root`.
    """
    root_abs = os.path.abspath(root)

    # Ninguna parte puede ser absoluta ni traer unidad propia (C:\, \\server\...).
    for part in parts:
        if part is None:
            continue
        if os.path.isabs(part) or os.path.splitdrive(str(part))[0]:
            raise ValueError(f"Componente de ruta no permitido: {part!r}")

    final = os.path.abspath(os.path.join(root_abs, *[str(p) for p in parts if p is not None]))

    root_n = os.path.normcase(root_abs)
    final_n = os.path.normcase(final)
    try:
        common = os.path.commonpath([root_n, final_n])
    except ValueError:
        # Unidades distintas en Windows -> commonpath lanza ValueError.
        raise ValueError(f"Ruta fuera del directorio permitido: {final}")
    if common != root_n:
        raise ValueError(f"Ruta fuera del directorio permitido: {final}")
    return final


def is_within(root, candidate):
    """True si `candidate` está dentro de `root` (ambas rutas ya absolutas o relativas)."""
    try:
        root_n = os.path.normcase(os.path.abspath(root))
        cand_n = os.path.normcase(os.path.abspath(candidate))
        return os.path.commonpath([root_n, cand_n]) == root_n
    except ValueError:
        return False


def rel_within(root, candidate):
    """Ruta relativa (con '/') de `candidate` dentro de `root`, o None si está fuera."""
    if not is_within(root, candidate):
        return None
    rel = os.path.relpath(os.path.abspath(candidate), os.path.abspath(root))
    return rel.replace(os.sep, "/")


def normalize_rel(rel):
    """Normaliza una ruta relativa que llega de la red a componentes seguros con '/'.

    Acepta separadores '\\' o '/', colapsa vacíos y rechaza '..' y rutas absolutas.
    Devuelve la ruta normalizada con '/'. Lanza ValueError si es insegura.
    """
    rel = str(rel or "").replace("\\", "/").strip()
    parts = [p for p in rel.split("/") if p not in ("", ".")]
    for p in parts:
        if p == ".." or os.path.isabs(p) or os.path.splitdrive(p)[0]:
            raise ValueError(f"Ruta relativa no permitida: {rel!r}")
    return "/".join(parts)


_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")


def slugify(name, fallback="item"):
    """Convierte un nombre arbitrario en un componente de carpeta/archivo seguro."""
    name = _SLUG_RE.sub("-", str(name or "").strip()).strip("-._")
    return name or fallback


def ensure_json_ext(name):
    """Garantiza que `name` termina en .json (para guardar/duplicar/renombrar workflows)."""
    name = str(name or "").strip()
    if not name:
        raise ValueError("Nombre vacío.")
    if "/" in name or "\\" in name:
        raise ValueError(f"El nombre no puede contener separadores de ruta: {name!r}")
    if not name.lower().endswith(".json"):
        name += ".json"
    return name


def load_json(path, default=None):
    """Lee un JSON; devuelve `default` si no existe o está corrupto."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    """Escribe un JSON de forma atómica (tmp + rename) creando el directorio si hace falta."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    dir_name = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
