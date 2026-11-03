# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Capa de sistema de archivos para workflows (.json) bajo una raíz.

La raíz por defecto es la carpeta nativa de ComfyUI; la capa de Proyectos reutiliza estas funciones
con la carpeta propia de cada proyecto. Toda ruta que llega de la red se valida contra la raíz con
`safe_join` / `normalize_rel`, y solo se opera sobre archivos de workflow: nunca sobre otros archivos.
"""
import os

from . import config
from .util import (
    UserError,
    check_new_folder,
    ensure_json_ext,
    fold_case,
    is_link,
    is_workflow_file,
    join_rel,
    looks_like_workflow,
    move_file,
    move_tree,
    normalize_rel,
    safe_join,
    same_entry,
    split_rel,
    usable_name,
    write_atomic,
)


def get_root(create=True):
    return config.comfy_workflows_root(create=create)


def abs_path(rel, root=None):
    """Ruta absoluta segura de `rel` dentro de la raíz."""
    root = root or get_root()
    parts = [p for p in normalize_rel(rel).split("/") if p]
    if not all(usable_name(p) for p in parts):
        raise UserError("bad_path", path=rel)
    return safe_join(root, *parts)


def file_path(rel, root=None):
    """Como `abs_path`, pero exige que `rel` sea un archivo de workflow (exista o no)."""
    path = abs_path(rel, root)
    if not is_workflow_file(path):
        raise UserError("not_workflow", path=rel)
    return path


def existing_file(rel, root=None):
    path = file_path(rel, root)
    if not os.path.isfile(path):
        raise UserError("not_found", path=rel)
    return path


def list_tree(root=None, follow_links=True):
    """Escanea la raíz: {"root", "folders": [...], "workflows": [{rel,name,folder,size,mtime}]}.

    Sigue los enlaces simbólicos a carpetas, como ComfyUI: también muestra sus workflows. Con
    `follow_links=False` no entra en ellos: para operaciones que borran.
    """
    root = root or get_root()
    folders = set()
    out = []
    visited = set()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=follow_links):
        real = os.path.realpath(dirpath)
        if real in visited:         # un enlace que apunta a una carpeta superior no debe dar vueltas
            dirnames[:] = []
            continue
        visited.add(real)
        # No descender en directorios ocultos (.git, ...).
        dirnames[:] = [d for d in dirnames if not d.startswith(".")
                       and (follow_links or not is_link(os.path.join(dirpath, d)))]
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        if rel_dir == ".":
            rel_dir = ""
        if rel_dir:
            folders.add(rel_dir)
        for fn in filenames:
            if not is_workflow_file(fn):
                continue
            try:
                st = os.stat(os.path.join(dirpath, fn))
                size, mtime = st.st_size, st.st_mtime
            except OSError:
                size, mtime = 0, 0
            out.append({"rel": join_rel(rel_dir, fn), "name": fn, "folder": rel_dir,
                        "size": size, "mtime": mtime})
    out.sort(key=lambda w: w["rel"].lower())
    return {"root": root, "folders": sorted(folders, key=str.lower), "workflows": out}


def exists(rel, root=None):
    try:
        return os.path.isfile(file_path(rel, root))
    except ValueError:
        return False


def read_bytes(rel, root=None):
    with open(existing_file(rel, root), "rb") as fh:
        return fh.read()


def mkdir(folder, root=None):
    """Crea una subcarpeta (recursiva) bajo la raíz. Devuelve su ruta relativa."""
    folder = normalize_rel(folder)
    if not folder:
        raise UserError("empty_name")
    check_new_folder(folder)
    os.makedirs(abs_path(folder, root), exist_ok=True)
    return folder


def write(rel, data, overwrite=False, root=None):
    """Crea/escribe un workflow. `data` puede ser bytes o str. Devuelve su rel."""
    folder, name = split_rel(normalize_rel(rel))
    if not name.lower().endswith(".json"):
        rel = join_rel(folder, ensure_json_ext(name))
    else:
        rel = join_rel(folder, name)
    dest = file_path(rel, root)
    if os.path.lexists(dest) and not overwrite:     # un enlace roto escribiría fuera de la raíz
        raise UserError("exists", path=rel)
    if isinstance(data, str):
        data = data.encode("utf-8")
    write_atomic(dest, data)
    return rel


def relocate(old, new, root=None):
    """Mueve/renombra un workflow dentro de la raíz, sin pisar nada."""
    src = existing_file(old, root)
    dst = file_path(new, root)
    if os.path.abspath(src) == os.path.abspath(dst):
        return
    # En sistemas de archivos sin distinción de mayúsculas, renombrar solo mayúsculas es válido.
    if os.path.exists(dst) and not same_entry(src, dst):
        raise UserError("exists", path=new)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    move_file(src, dst)


def remove_file(rel, root=None):
    os.remove(existing_file(rel, root))


def prune_empty_dirs(start, stop):
    """Borra `start` y sus padres mientras estén vacíos, sin llegar nunca a `stop`."""
    path = os.path.abspath(start)
    stop = os.path.abspath(stop)
    while path != stop and path.startswith(stop) and os.path.isdir(path) and not is_link(path):
        try:
            os.rmdir(path)
        except OSError:
            return
        path = os.path.dirname(path)


def delete_workflows_in(folder, root=None):
    """Borra los workflows de una carpeta y las carpetas que queden vacías.

    Nunca borra otros archivos (un proyecto puede tener `.git`, imágenes, etc.), ni entra en carpetas
    enlazadas: lo que hay en ellas no es de aquí. Devuelve (lista de rels borrados, True si la carpeta ha
    desaparecido). Si un archivo no se puede borrar, el error lleva en `removed` los que ya se han borrado.
    """
    root = os.path.abspath(root or get_root())
    folder = normalize_rel(folder)
    if not folder:
        raise UserError("root_forbidden")
    base = abs_path(folder, root)
    if not os.path.isdir(base):
        return [], True
    if is_link(base):
        # Lo enlazado no es de esta carpeta: se quita el enlace y su destino queda intacto.
        try:
            os.unlink(base)
        except OSError:
            os.rmdir(base)      # uniones de Windows
        return [], True
    removed = []
    visited = []
    try:
        for dirpath, dirnames, filenames in os.walk(base):
            # followlinks=False no siempre reconoce las uniones de Windows.
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and not is_link(os.path.join(dirpath, d))]
            visited.append(dirpath)
            rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
            rel_dir = "" if rel_dir == "." else rel_dir
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                if is_workflow_file(fn) and looks_like_workflow(full):
                    os.remove(full)
                    removed.append(join_rel(rel_dir, fn))
    except OSError as exc:
        exc.removed = removed
        raise
    for dirpath in reversed(visited):
        try:
            os.rmdir(dirpath)
        except OSError:
            pass
    return removed, not os.path.isdir(base)


def check_folder_move(folder, new_folder, root=None):
    """Comprueba que se puede mover una carpeta. Devuelve (origen, destino) en absoluto."""
    root = root or get_root()
    folder = normalize_rel(folder)
    new_folder = normalize_rel(new_folder)
    if not folder or not new_folder:
        raise UserError("root_forbidden")
    src = abs_path(folder, root)
    dst = abs_path(new_folder, root)
    if not os.path.isdir(src):
        raise UserError("folder_not_found", path=folder)
    if os.path.abspath(src) == os.path.abspath(dst):
        return src, dst
    if fold_case(new_folder).startswith(fold_case(folder) + "/"):
        raise UserError("same_folder")
    if os.path.exists(dst) and not same_entry(src, dst):
        raise UserError("exists", path=new_folder)
    return src, dst


def move_folder(folder, new_folder, root=None):
    """Mueve/renombra una subcarpeta completa. Devuelve la nueva ruta relativa."""
    new_folder = normalize_rel(new_folder)
    src, dst = check_folder_move(folder, new_folder, root)
    if os.path.abspath(src) == os.path.abspath(dst):
        return new_folder
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    move_tree(src, dst)
    return new_folder
