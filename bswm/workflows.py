# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Capa de sistema de archivos sobre la *raíz de workflows*.

Es el equivalente a `models.py` del model-manager, pero para archivos de workflow (.json) bajo una
carpeta raíz configurable (por defecto la de ComfyUI, `<user>/default/workflows`). Toda ruta que
llega de la red se valida con `safe_join` / `normalize_rel` contra la raíz: nunca se escapa de ella.

Las operaciones son puramente de FS. La capa de Proyectos (projects.py) se apoya en estas funciones
cuando un proyecto tiene una carpeta vinculada.
"""
import os
import shutil

from . import config
from .util import (
    ensure_json_ext,
    is_workflow_file,
    normalize_rel,
    safe_join,
)


def get_root(create=True):
    return config.get_workflows_root(create=create)


def abs_path(rel, root=None):
    """Ruta absoluta segura de `rel` dentro de la raíz (o de `root` si se indica)."""
    root = root or get_root()
    parts = [p for p in normalize_rel(rel).split("/") if p]
    return safe_join(root, *parts)


def _folder_of(rel):
    rel = normalize_rel(rel)
    return rel.rsplit("/", 1)[0] if "/" in rel else ""


def list_tree(root=None):
    """Escanea la raíz y devuelve los workflows y las carpetas existentes.

    Estructura:
      {
        "root": <ruta absoluta>,
        "folders": ["", "clientes", "clientes/pepe", ...]  (incluye la raíz como ""),
        "workflows": [{"rel", "name", "folder", "size", "mtime"}, ...],
      }
    """
    root = root or get_root()
    folders = {""}
    workflows = []
    for dirpath, dirnames, filenames in os.walk(root):
        # No descender en directorios ocultos ni en nuestra propia carpeta de datos.
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != config.DATA_SUBDIR]
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        if rel_dir == ".":
            rel_dir = ""
        if rel_dir:
            folders.add(rel_dir)
        for fn in filenames:
            if not is_workflow_file(fn):
                continue
            full = os.path.join(dirpath, fn)
            rel = (f"{rel_dir}/{fn}" if rel_dir else fn)
            try:
                st = os.stat(full)
                size, mtime = st.st_size, st.st_mtime
            except OSError:
                size, mtime = 0, 0
            workflows.append({
                "rel": rel,
                "name": fn,
                "folder": rel_dir,
                "size": size,
                "mtime": mtime,
            })
    workflows.sort(key=lambda w: w["rel"].lower())
    return {
        "root": root,
        "folders": sorted(folders, key=str.lower),
        "workflows": workflows,
    }


def exists(rel, root=None):
    try:
        return os.path.isfile(abs_path(rel, root))
    except ValueError:
        return False


def read_bytes(rel, root=None):
    path = abs_path(rel, root)
    if not os.path.isfile(path):
        raise ValueError(f"El workflow no existe: {rel}")
    with open(path, "rb") as fh:
        return fh.read()


def mkdir(folder, root=None):
    """Crea una subcarpeta (recursiva) bajo la raíz. Devuelve su ruta relativa."""
    root = root or get_root()
    folder = normalize_rel(folder)
    if not folder:
        raise ValueError("Nombre de carpeta vacío.")
    os.makedirs(abs_path(folder, root), exist_ok=True)
    return folder


def write(rel, data, overwrite=False, root=None):
    """Crea/escribe un workflow (.json). `data` puede ser bytes o str. Devuelve su rel."""
    root = root or get_root()
    rel = normalize_rel(rel)
    folder = _folder_of(rel)
    name = ensure_json_ext(os.path.basename(rel))
    rel = f"{folder}/{name}" if folder else name
    dest = abs_path(rel, root)
    if os.path.exists(dest) and not overwrite:
        raise ValueError(f"Ya existe un workflow con ese nombre: {rel}")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if isinstance(data, str):
        data = data.encode("utf-8")
    with open(dest, "wb") as fh:
        fh.write(data)
    return rel


def rename(rel, new_name, root=None):
    """Renombra un workflow dentro de su misma carpeta. Devuelve la nueva rel."""
    root = root or get_root()
    src = abs_path(rel, root)
    if not os.path.isfile(src):
        raise ValueError(f"El workflow no existe: {rel}")
    folder = _folder_of(rel)
    new_name = ensure_json_ext(new_name)
    new_rel = f"{folder}/{new_name}" if folder else new_name
    dst = abs_path(new_rel, root)
    if os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(dst)):
        return new_rel
    if os.path.exists(dst):
        raise ValueError(f"Ya existe un workflow con ese nombre: {new_rel}")
    os.rename(src, dst)
    return new_rel


def move(rel, dest_folder, root=None):
    """Mueve un workflow a otra carpeta (dest_folder='' = raíz). Devuelve la nueva rel."""
    root = root or get_root()
    src = abs_path(rel, root)
    if not os.path.isfile(src):
        raise ValueError(f"El workflow no existe: {rel}")
    dest_folder = normalize_rel(dest_folder)
    name = os.path.basename(rel)
    new_rel = f"{dest_folder}/{name}" if dest_folder else name
    dst = abs_path(new_rel, root)
    if os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(dst)):
        return new_rel
    if os.path.exists(dst):
        raise ValueError(f"Ya existe un workflow en el destino: {new_rel}")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.move(src, dst)
    return new_rel


def _unique_name(folder, name, root):
    """Devuelve un nombre que no colisione en `folder` (añade ' copy', ' copy 2', ...)."""
    base, ext = os.path.splitext(name)
    candidate = name
    n = 1
    while os.path.exists(abs_path(f"{folder}/{candidate}" if folder else candidate, root)):
        suffix = " copy" if n == 1 else f" copy {n}"
        candidate = f"{base}{suffix}{ext}"
        n += 1
    return candidate


def duplicate(rel, dest_folder=None, new_name=None, root=None):
    """Duplica un workflow. Sin destino → misma carpeta con sufijo ' copy'. Devuelve la nueva rel."""
    root = root or get_root()
    src = abs_path(rel, root)
    if not os.path.isfile(src):
        raise ValueError(f"El workflow no existe: {rel}")
    folder = normalize_rel(dest_folder) if dest_folder is not None else _folder_of(rel)
    name = ensure_json_ext(new_name) if new_name else os.path.basename(rel)
    name = _unique_name(folder, name, root)
    new_rel = f"{folder}/{name}" if folder else name
    dst = abs_path(new_rel, root)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return new_rel


def delete(rel, root=None):
    """Borra un workflow. Devuelve la ruta absoluta borrada."""
    root = root or get_root()
    path = abs_path(rel, root)
    if not os.path.isfile(path):
        raise ValueError(f"El workflow no existe: {rel}")
    os.remove(path)
    return path


def rename_folder(folder, new_name, root=None):
    """Renombra una subcarpeta (cambia solo su último componente). Devuelve la nueva ruta relativa."""
    root = root or get_root()
    folder = normalize_rel(folder)
    if not folder:
        raise ValueError("No se puede renombrar la raíz.")
    src = abs_path(folder, root)
    if not os.path.isdir(src):
        raise ValueError(f"La carpeta no existe: {folder}")
    parent = folder.rsplit("/", 1)[0] if "/" in folder else ""
    clean = normalize_rel(new_name)
    if not clean or "/" in clean:
        raise ValueError("Nombre de carpeta no válido.")
    new_folder = f"{parent}/{clean}" if parent else clean
    dst = abs_path(new_folder, root)
    if os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(dst)):
        return new_folder
    if os.path.exists(dst):
        raise ValueError(f"Ya existe una carpeta con ese nombre: {new_folder}")
    os.rename(src, dst)
    return new_folder


def transfer_from(src_root, refs, dest_folder="", move=False, root=None):
    """Copia (o mueve) workflows desde `src_root` (p.ej. la carpeta de ComfyUI) a nuestra raíz.

    Conserva la subruta relativa de cada workflow bajo `dest_folder`. Devuelve
    {"copied": [...refs...], "skipped": [{ref, reason}]} (se omiten los que ya existen).
    """
    root = root or get_root()
    if os.path.normcase(os.path.abspath(src_root)) == os.path.normcase(os.path.abspath(root)):
        raise ValueError("El origen y el destino son la misma carpeta.")
    copied, skipped = [], []
    for rel in refs:
        rel = normalize_rel(rel)
        try:
            src = safe_join(src_root, *rel.split("/"))
        except ValueError:
            skipped.append({"ref": rel, "reason": "ruta no válida"})
            continue
        if not os.path.isfile(src):
            skipped.append({"ref": rel, "reason": "no existe"})
            continue
        dest_rel = normalize_rel(f"{dest_folder}/{rel}" if dest_folder else rel)
        dst = abs_path(dest_rel, root)
        if os.path.exists(dst):
            skipped.append({"ref": dest_rel, "reason": "ya existe"})
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if move:
            shutil.move(src, dst)
        else:
            shutil.copy2(src, dst)
        copied.append(dest_rel)
    return {"copied": copied, "skipped": skipped}


def delete_folder(folder, root=None):
    """Borra una subcarpeta y su contenido. Devuelve la ruta absoluta borrada."""
    root = root or get_root()
    folder = normalize_rel(folder)
    if not folder:
        raise ValueError("No se puede borrar la raíz.")
    path = abs_path(folder, root)
    if not os.path.isdir(path):
        raise ValueError(f"La carpeta no existe: {folder}")
    shutil.rmtree(path)
    return path
