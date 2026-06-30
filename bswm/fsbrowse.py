# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Explorador de carpetas del SERVIDOR (la máquina donde corre ComfyUI/este backend).

Permite que el cliente (p. ej. un navegador en Windows) navegue la estructura de carpetas del
servidor (p. ej. Linux) y elija dónde vivirá la carpeta de un proyecto, sin teclear la ruta a mano.
Solo lista directorios y crea carpetas; nunca lee/borra archivos. Mismo modelo de confianza que el
resto del add-on (el usuario local de ComfyUI ya puede fijar rutas absolutas).
"""
import os
import string


def _is_writable(path):
    """Best-effort: ¿se puede escribir en `path`?"""
    try:
        return os.access(path, os.W_OK)
    except OSError:
        return False


def roots():
    """Puntos de partida del servidor: raíz '/' en POSIX o unidades en Windows, + accesos rápidos."""
    out = []
    if os.name == "nt":
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                out.append({"name": drive, "path": drive, "writable": _is_writable(drive)})
    else:
        out.append({"name": "/", "path": "/", "writable": _is_writable("/")})
    # Accesos rápidos útiles.
    seen = {os.path.normcase(d["path"]) for d in out}
    for label, p in (("~ (home)", os.path.expanduser("~")),):
        if p and os.path.isdir(p) and os.path.normcase(os.path.abspath(p)) not in seen:
            out.append({"name": label, "path": os.path.abspath(p), "writable": _is_writable(p)})
    return out


def list_dir(path):
    """Subdirectorios inmediatos de `path` (+ su `parent`). `path` vacío => lista de raíces."""
    path = (path or "").strip()
    if not path:
        return {"path": "", "parent": None, "is_root_list": True, "writable": False, "dirs": roots()}

    abspath = os.path.abspath(path)
    if not os.path.isdir(abspath):
        raise ValueError(f"No es una carpeta del servidor: {abspath}")

    dirs = []
    try:
        for name in sorted(os.listdir(abspath), key=str.lower):
            if name.startswith("."):
                continue  # ocultamos dotfolders para reducir ruido
            full = os.path.join(abspath, name)
            try:
                if os.path.isdir(full):
                    dirs.append({"name": name, "path": full, "writable": _is_writable(full)})
            except OSError:
                continue  # enlaces rotos / sin permiso: se omiten
    except PermissionError:
        raise ValueError(f"Sin permiso para listar: {abspath}")
    except OSError as exc:
        raise ValueError(f"No se pudo listar: {exc}")

    parent = os.path.dirname(abspath)
    if parent == abspath:
        parent = ""  # ya en la raíz de la unidad -> volver a la lista de raíces
    return {"path": abspath, "parent": parent, "is_root_list": False,
            "writable": _is_writable(abspath), "dirs": dirs}


def mkdir(path, name):
    """Crea una subcarpeta `name` dentro de `path` (del servidor). Devuelve la ruta absoluta."""
    path = (path or "").strip()
    name = (name or "").strip()
    base = os.path.abspath(path) if path else ""
    if not base or not os.path.isdir(base):
        raise ValueError("Carpeta base no válida.")
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        raise ValueError(f"Nombre de carpeta no válido: {name!r}")
    full = os.path.join(base, name)
    if os.path.exists(full):
        raise ValueError(f"Ya existe: {full}")
    os.makedirs(full)
    return full
