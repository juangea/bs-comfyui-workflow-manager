# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Proyectos: la capa de organización sobre la carpeta de workflows de ComfyUI.

Todo workflow tiene UNA ruta canónica (`path`) relativa a la carpeta nativa de ComfyUI: es la que
usan sus pestañas y su Guardar. Un proyecto los agrupa de dos maneras:

  - Sin carpeta propia: son *etiquetas*. La tabla `links` guarda proyecto + subcarpeta lógica; el
    archivo no se mueve. Por defecto pertenece a un solo proyecto; compartirlo es opt-in.

  - Con carpeta propia (`folder`): sus archivos están en `<comfy>/<prefix>/<ref>` Y en
    `<folder>/<ref>`, que es un espejo actualizado en cada guardado. Si la carpeta cuelga de la de
    ComfyUI, no hay espejo: es el mismo archivo.

La BD es un único JSON por usuario, exportable/importable tal cual.
"""
import copy
import json
import logging
import ntpath
import os
import posixpath
import time
import unicodedata
import uuid

from . import config, workflows
from .util import (
    UserError,
    check_new_folder,
    copy_atomic,
    ensure_json_ext,
    fold_case,
    is_local_abs,
    is_within,
    looks_like_workflow,
    join_rel,
    normalize_rel,
    reaches,
    safe_component,
    same_path,
    save_json,
    split_rel,
)

DB_VERSION = 2
DEFAULT_COLOR = "#AC1F23"

MTIME_SLACK = 2.0          # los discos de red redondean las fechas: no es un cambio real
log = logging.getLogger("BS_Workflow_Manager")
_legacy_failed = set()     # raíces antiguas que no se han podido migrar en esta sesión


# ----------------------------- BD -----------------------------
def _now():
    return time.time()


def _gen_id(prefix):
    return prefix + uuid.uuid4().hex[:12]


def _empty_db():
    return {"version": DB_VERSION, "projects": [], "links": [], "settings": {}}


def _read_db():
    """Lee la BD. Una BD estropeada se aparta, nunca se sobrescribe; una ilegible da error."""
    path = config.get_db_path()
    try:
        with open(path, encoding="utf-8") as fh:
            db = json.load(fh)
        if isinstance(db, dict):
            return db
    except FileNotFoundError:
        return _empty_db()
    except ValueError:
        pass
    backup = f"{path}.corrupt-{int(_now())}"
    os.replace(path, backup)
    log.error("Projects database is damaged: kept as %s", backup)
    return _empty_db()


def load_db():
    db = _read_db()
    db.setdefault("projects", [])
    db.setdefault("links", [])
    db.setdefault("settings", {})
    migrated = _migrate_legacy_root(db)
    changed = migrated
    if db.get("version") != DB_VERSION:
        _repair_folders(db)
        changed = True
    for p in db["projects"]:
        changed = _normalize_project(db, p) or changed
    changed = _drop_unusable_links(db) or changed
    if changed:
        save_db(db)
    if migrated:
        config.forget_legacy_root()
    return db


def _repair_folders(db):
    """Quita las carpetas que hoy no se aceptarían, de una versión anterior o de una BD importada.

    Como la que contiene toda la de ComfyUI, o dos proyectos en la misma: borrar uno borraría
    archivos de otro. El proyecto pasa a no tener carpeta; ningún archivo se toca. Primero las inservibles:
    un proyecto no debe perder la suya por solaparse con una que tampoco se va a quedar.
    """
    for check in (lambda p, folder: _check_folder(folder), lambda p, folder: _check_folder_overlap(db, p, folder)):
        for p in db["projects"]:
            folder = p.get("folder")
            if not is_local_abs(folder):
                continue
            try:
                check(p, folder)
            except UserError as exc:
                log.warning("Project %s no longer uses its folder: %s", p.get("name"), exc)
                p["folder"] = None
                p["prefix"] = None


def _drop_unusable_links(db):
    """Solo los proyectos sin carpeta usan vínculos. Otros harían invisible el archivo en el árbol:
    se ocultaría de Workflows sin aparecer en ningún proyecto."""
    tags = [p["id"] for p in db["projects"] if not p.get("folder")]
    kept = [l for l in db["links"] if isinstance(l, dict) and l.get("project_id") in tags and _usable_ref(l)]
    if len(kept) == len(db["links"]):
        return False
    db["links"] = kept
    return True


def _usable_ref(link):
    """Un nombre válido en el sistema donde se creó la BD puede no serlo aquí, como `a:b.json` en Windows."""
    try:
        return bool(normalize_rel(link.get("workflow_ref"))) and bool(workflows.abs_path(link["workflow_ref"]))
    except UserError:
        return False


def save_db(db):
    db["version"] = DB_VERSION
    save_json(config.get_db_path(), db)
    return db


def export_db():
    """Devuelve la BD tal cual (para descargar)."""
    return load_db()


def _validate_import(data):
    if not isinstance(data, dict) or not isinstance(data.get("projects"), list) \
            or not isinstance(data.get("links"), list):
        raise UserError("bad_db")
    is_text = lambda value: isinstance(value, str) and value   # noqa: E731
    for p in data["projects"]:
        if not isinstance(p, dict) or not is_text(p.get("id")) or not is_text(p.get("name")):
            raise UserError("bad_db")
        for key in ("color", "notes", "folder", "prefix"):
            if p.get(key) is not None and not isinstance(p[key], str):
                raise UserError("bad_db")
        subs = p.get("subfolders", [])
        if not isinstance(subs, list) or not all(isinstance(s, str) for s in subs):
            raise UserError("bad_db")
        for s in subs:
            normalize_rel(s)
        # Una carpeta que ya no se admite no impide restaurar una copia: `_repair_folders` se la quita.
        folder = str(p.get("folder") or "")
        if folder and not (is_local_abs(folder) or ntpath.isabs(folder) or posixpath.isabs(folder)):
            raise UserError("folder_absolute", path=folder)
    for l in data["links"]:
        if not isinstance(l, dict) or not is_text(l.get("id")) or not is_text(l.get("project_id")) \
                or not is_text(l.get("workflow_ref")) or not isinstance(l.get("subfolder") or "", str):
            raise UserError("bad_db")
        normalize_rel(l["workflow_ref"])


def _forget_foreign_prefixes(data, merge=False):
    """Un prefijo traído de otra BD no puede apropiarse de una carpeta que ya existe aquí.

    Los archivos de esa carpeta no son del proyecto: se mezclarían con los suyos, y borrarlo los borraría.
    Se le asignará uno libre. Se conserva si ya era suyo en este equipo, o si todo lo que hay allí es igual
    a su carpeta propia (restaurar una copia de la BD tras perder la original). Al fusionar, tampoco puede
    solaparse con el de un proyecto que se queda: lo dejaría a él sin sus archivos.
    """
    current = {p.get("id"): p.get("prefix") for p in _read_db().get("projects", []) if isinstance(p, dict)}
    for p in data["projects"]:
        prefix = p.get("prefix")
        if not prefix or current.get(p["id"]) == prefix:
            continue
        if merge and any(pid != p["id"] and other and _overlaps(other, prefix) for pid, other in current.items()):
            p["prefix"] = None
            continue
        try:
            if os.path.exists(workflows.abs_path(prefix)) and not _matches_own_folder(p, prefix):
                p["prefix"] = None
        except UserError:
            p["prefix"] = None


def _matches_own_folder(p, prefix):
    folder = p.get("folder")
    if not is_local_abs(folder) or not os.path.isdir(folder):
        return False
    for rel in _refs_under(prefix):
        mirror = workflows.abs_path(rel, folder)
        if not os.path.isfile(mirror) or not _same_bytes(workflows.file_path(join_rel(prefix, rel)), mirror):
            return False
    return True


def import_db(data, merge=False):
    """Reemplaza (o fusiona) la BD con `data`, tras validar su estructura."""
    _validate_import(data)
    _forget_foreign_prefixes(data, merge)
    if not merge:
        data.setdefault("settings", {})
        _repair_folders(data)
        return save_db(data)
    db = load_db()
    by_id = {p["id"]: p for p in db["projects"]}
    for p in data["projects"]:
        by_id[p["id"]] = p
    db["projects"] = list(by_id.values())
    link_ids = {l["id"] for l in db["links"]}
    db["links"].extend(l for l in data["links"] if l["id"] not in link_ids)
    _repair_folders(db)
    return save_db(db)


def _get(db, pid):
    for p in db["projects"]:
        if p["id"] == pid:
            return p
    raise UserError("project_unknown")


# ----------------------------- carpeta propia y prefijo -----------------------------
def _check_folder(raw):
    """Valida una carpeta de proyecto (siempre una ruta del servidor) y devuelve su ruta absoluta."""
    raw = str(raw or "").strip()
    if not raw:
        raise UserError("empty_name")
    if not is_local_abs(raw):
        raise UserError("folder_absolute", path=raw)
    folder = os.path.abspath(raw)
    # Ni la raíz del disco ni una carpeta que contenga a la de ComfyUI: el espejo no tendría sentido.
    data, root = config.data_dir(), workflows.get_root()
    if os.path.dirname(folder) == folder or reaches(folder, root) or reaches(folder, data) or reaches(data, folder):
        raise UserError("folder_forbidden", path=folder)
    # Dentro de la de ComfyUI es válida, pero por su ruta normal: con otra no se sabría que es el mismo archivo.
    if reaches(root, folder) and not is_within(root, folder):
        raise UserError("folder_forbidden", path=folder)
    return folder


def _prepare_folder(raw):
    folder = _check_folder(raw)
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError as exc:
        raise UserError("folder_unusable", detail=exc)
    return folder


def _check_folder_overlap(db, p, folder):
    """Dos proyectos no pueden compartir carpeta, ni estar uno dentro de otro: mezclarían sus archivos."""
    for o in db["projects"]:
        other = o.get("folder")
        if o is p or not is_local_abs(other):
            continue
        if reaches(other, folder) or reaches(folder, other):
            raise UserError("folder_in_use", path=folder, project=o["name"])


def _in_comfy(folder):
    return is_within(workflows.get_root(), folder)


def _has_mirror(p):
    """True si el proyecto mantiene una copia fuera de la carpeta de ComfyUI.

    Una ruta de otro sistema (BD traída de Windows a Linux) no vale aquí: usarla crearía carpetas
    con ese nombre en el directorio actual. El proyecto sigue funcionando sin copia.
    """
    return is_local_abs(p.get("folder")) and not _in_comfy(p["folder"])


def _mirror_ready(p):
    return _has_mirror(p) and os.path.isdir(p["folder"])


def _require_mirror(p):
    """Un disco desmontado no debe recrearse como carpeta local vacía, ni dar el guardado por bueno."""
    if not _mirror_ready(p):
        raise UserError("folder_not_found", path=p["folder"])


def _overlaps(a, b):
    """True si dos rutas relativas son la misma o una contiene a la otra."""
    a, b = fold_case(a), fold_case(b)
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def _prefix_conflict(db, p, prefix):
    """Un prefijo no puede ser toda la carpeta de ComfyUI ni solaparse con el de otro proyecto."""
    if not prefix or prefix == ".":
        return True
    return any(o is not p and o.get("prefix") and _overlaps(o["prefix"], prefix) for o in db["projects"])


def _valid_prefix(db, p, prefix):
    try:
        return bool(prefix) and normalize_rel(prefix) == prefix and not _prefix_conflict(db, p, prefix)
    except UserError:
        return False


def _assign_prefix(db, p):
    """Elige la subcarpeta de ComfyUI donde viven los archivos de un proyecto con carpeta."""
    if _in_comfy(p["folder"]):
        try:
            prefix = os.path.relpath(os.path.realpath(p["folder"]), os.path.realpath(workflows.get_root()))
        except ValueError:      # otra unidad: la misma carpeta, a la que se ha llegado por otra ruta
            raise UserError("folder_forbidden", path=p["folder"])
        prefix = prefix.replace(os.sep, "/")
        if prefix.startswith("../") or _prefix_conflict(db, p, prefix):
            raise UserError("folder_forbidden", path=p["folder"])
        return prefix
    base = safe_component(p.get("name"), "project")
    candidate, n = base, 1
    root = workflows.get_root()
    while _prefix_conflict(db, p, candidate) or os.path.exists(os.path.join(root, candidate)):
        n += 1
        candidate = f"{base} ({n})"
    return candidate


def _normalize_project(db, p):
    """Completa campos de proyectos creados con versiones anteriores. True si ha cambiado algo."""
    before = json.dumps(p, sort_keys=True, default=str)
    p.setdefault("color", DEFAULT_COLOR)
    p.setdefault("notes", "")
    p.setdefault("subfolders", [])
    git = p.get("git") if isinstance(p.get("git"), dict) else {}
    p["git"] = {"remote_url": git.get("remote_url") or ""}
    p.pop("storage", None)
    if p.get("folder"):
        if not _valid_prefix(db, p, p.get("prefix")):
            p["prefix"] = None
            try:
                p["prefix"] = _assign_prefix(db, p)
            except UserError:
                # Carpeta inservible de una versión anterior o de una BD importada, como toda la de
                # ComfyUI: el proyecto pasa a no tener carpeta y no se toca ningún archivo.
                p["folder"] = None
    else:
        p["folder"] = None
        p["prefix"] = None
    return before != json.dumps(p, sort_keys=True, default=str)


def _migrate_legacy_root(db):
    """Convierte la «raíz personalizada» de versiones < 1.1 en un proyecto con carpeta propia.

    Solo copia: no borra ni mueve nada de la carpeta original. True si ya no queda nada por migrar.
    Si la carpeta no está disponible o algo falla, se reintenta en el siguiente arranque.
    """
    legacy = config.legacy_root()
    if not legacy or legacy in _legacy_failed:
        return False
    if same_path(legacy, workflows.get_root()):
        return True
    backup = copy.deepcopy(db)
    try:
        if not os.path.isdir(legacy):
            raise OSError(f"folder not available: {legacy}")
        _check_folder(legacy)
        project = next((p for p in db["projects"]
                        if p.get("folder") and same_path(p["folder"], legacy)), None)
        if not project:
            project = _new_project(safe_component(os.path.basename(os.path.normpath(legacy)), "Library"),
                                   folder=os.path.abspath(legacy))
            db["projects"].append(project)
        if not project.get("prefix"):
            project["prefix"] = _assign_prefix(db, project)
        # Los vínculos apuntaban a archivos de la raíz antigua: traerlos a la de ComfyUI.
        root = workflows.get_root()
        for l in db["links"]:
            ref = normalize_rel(l["workflow_ref"])
            src = os.path.join(legacy, *ref.split("/"))
            if os.path.isfile(src):
                new_ref = join_rel(project["prefix"], ref)
                dst = os.path.join(root, *new_ref.split("/"))
                if not os.path.exists(dst):
                    copy_atomic(src, dst)
                l["workflow_ref"] = new_ref
        _nested_projects_to_links(db, project, legacy)
        return True
    except (OSError, UserError) as exc:
        log.warning("Custom workflows root not migrated yet: %s", exc)
        _legacy_failed.add(legacy)
        db.clear()
        db.update(backup)
        return False


def _nested_projects_to_links(db, parent, legacy):
    """Un proyecto dentro de la raíz antigua no puede conservar su carpeta: se solaparía con el de la raíz.

    Sigue mostrando sus workflows, como vínculos a los de la raíz, en vez de quedarse vacío.
    """
    root = workflows.get_root()
    for p in db["projects"]:
        folder = p.get("folder")
        if p is parent or not is_local_abs(folder) or not os.path.isdir(folder) or not is_within(legacy, folder):
            continue
        base = os.path.relpath(os.path.realpath(folder), os.path.realpath(legacy)).replace(os.sep, "/")
        base = "" if base == "." else base
        for w in workflows.list_tree(root=folder)["workflows"]:
            ref = join_rel(parent["prefix"], join_rel(base, w["rel"]))
            dst = os.path.join(root, *ref.split("/"))
            if not os.path.exists(dst):
                copy_atomic(os.path.join(folder, *w["rel"].split("/")), dst)
            if not any(l["project_id"] == p["id"] for l in _ref_links(db, ref)):
                db["links"].append(_new_link(p["id"], ref, w["folder"]))
        p["folder"] = None
        p["prefix"] = None


def _new_project(name, color=DEFAULT_COLOR, folder=None, notes="", subfolders=None, remote_url=""):
    return {
        "id": _gen_id("p_"),
        "name": name,
        "color": color or DEFAULT_COLOR,
        "folder": folder,
        "prefix": None,
        "subfolders": [normalize_rel(s) for s in (subfolders or []) if s],
        "git": {"remote_url": remote_url},
        "notes": notes or "",
        "created": _now(),
        "modified": _now(),
    }


def _owner_by_path(db, path):
    """Proyecto con carpeta cuyo prefijo contiene `path` (o None) y su ref dentro de él."""
    for p in db["projects"]:
        prefix = p.get("prefix")
        if prefix and fold_case(path).startswith(fold_case(prefix) + "/"):
            return p, path[len(prefix) + 1:]
    return None, None


def _mirror_file(p, ref):
    return workflows.file_path(ref, root=p["folder"])


# ----------------------------- proyectos -----------------------------
def _check_texts(*values):
    """Un valor de otro tipo se guardaría, y la propia copia de la BD dejaría de poder importarse."""
    if any(v is not None and not isinstance(v, str) for v in values):
        raise UserError("bad_name", name=next(v for v in values if v is not None and not isinstance(v, str)))


def create_project(name, color=DEFAULT_COLOR, folder=None, notes="", subfolders=None):
    _check_texts(name, color, folder, notes)
    name = (name or "").strip()
    if not name:
        raise UserError("project_name_required")
    db = load_db()
    if any(p["name"].lower() == name.lower() for p in db["projects"]):
        raise UserError("project_exists", name=name)
    if (folder or "").strip():
        _check_folder_overlap(db, None, _check_folder(folder))
    folder = _prepare_folder(folder) if (folder or "").strip() else None
    project = _new_project(name, color, folder, notes, subfolders)
    db["projects"].append(project)
    if folder:
        project["prefix"] = _assign_prefix(db, project)
    save_db(db)
    return project


def update_project(pid, name=None, color=None, notes=None, folder=None):
    """Actualiza un proyecto. `folder`: None = no tocar; "" = quitar la carpeta propia."""
    _check_texts(name, color, notes, folder)
    db = load_db()
    p = _get(db, pid)
    if name is not None:
        name = name.strip()
        if not name:
            raise UserError("project_name_required")
        # Una BD antigua o importada puede repetir nombres: no debe impedir cambiar otras cosas.
        if name.lower() != p["name"].lower() and any(o["id"] != pid and o["name"].lower() == name.lower() for o in db["projects"]):
            raise UserError("project_exists", name=name)
        p["name"] = name
    if color:
        p["color"] = color
    if notes is not None:
        p["notes"] = notes
    if folder is not None:
        _change_folder(db, p, folder.strip())
    p["modified"] = _now()
    save_db(db)
    return p


def _change_folder(db, p, new_folder):
    old_folder = p.get("folder")
    if new_folder == old_folder:
        return                  # sin comprobar nada: puede estar sin montar o ser de otro sistema
    if not new_folder:
        if old_folder:
            _folder_to_links(db, p)
        return
    _check_folder_overlap(db, p, _check_folder(new_folder))
    new_folder = _prepare_folder(new_folder)
    if old_folder and is_local_abs(old_folder) and same_path(old_folder, new_folder):
        return
    if old_folder:
        # Cambio de ubicación: los archivos de ComfyUI se conservan y se copian a la nueva carpeta.
        for item in _project_items(db, p):
            _pull_newest(p, item["ref"])
        old_prefix = p["prefix"]
        p["folder"] = new_folder
        if _in_comfy(new_folder):
            p["prefix"] = None
            p["prefix"] = _assign_prefix(db, p)
        refs = _refs_under(old_prefix)
        moved = _move_prefix(db, old_prefix, p["prefix"], refs) if p["prefix"] != old_prefix else []
        try:
            if _has_mirror(p):
                for rel in refs:
                    _check_mirror_free(p, rel, workflows.file_path(join_rel(p["prefix"], rel)))
                for rel in refs:
                    copy_atomic(workflows.file_path(join_rel(p["prefix"], rel)), _mirror_file(p, rel))
        except (OSError, UserError):
            _undo_relocations(moved)
            raise
        return
    _links_to_folder(db, p, new_folder)


def _refs_under(prefix):
    """Refs de los archivos que hay bajo un prefijo en la carpeta de ComfyUI."""
    base = workflows.abs_path(prefix)
    if not os.path.isdir(base):
        return []
    return [w["rel"] for w in workflows.list_tree(root=base)["workflows"]]


def _move_prefix(db, old_prefix, new_prefix, refs):
    """Lleva los archivos de un proyecto a su nuevo prefijo, sin pisar nada. O todos, o ninguno."""
    for rel in refs:
        if workflows.exists(join_rel(new_prefix, rel)):
            raise UserError("exists", path=join_rel(new_prefix, rel))
    done = []
    try:
        for rel in refs:
            old, new = join_rel(old_prefix, rel), join_rel(new_prefix, rel)
            workflows.relocate(old, new)
            done.append((old, new))
            _rewrite_links(db, old, new)
    except (OSError, UserError):
        _undo_relocations(done)
        raise
    return done


def _undo_relocations(done):
    for old, new in reversed(done):
        try:
            workflows.relocate(new, old)
        except (OSError, UserError) as exc:
            log.error("Could not move %s back to %s: %s", new, old, exc)


def _same_bytes(a, b):
    with open(a, "rb") as fa, open(b, "rb") as fb:
        return fa.read() == fb.read()


def _check_mirror_free(p, ref, source):
    """Evita pisar un archivo distinto que ya estuviera en la carpeta del proyecto."""
    mirror = _mirror_file(p, ref)
    if os.path.exists(mirror) and not (os.path.isfile(mirror) and _same_bytes(source, mirror)):
        raise UserError("exists", path=mirror)


def _links_to_folder(db, p, new_folder):
    """Da carpeta propia a un proyecto de etiquetas: sus archivos pasan a su prefijo y a la carpeta."""
    p["folder"] = new_folder
    p["prefix"] = None
    p["prefix"] = _assign_prefix(db, p)
    mine = [l for l in db["links"] if l["project_id"] == p["id"]]
    moves = []
    planned = set()
    for l in mine:
        old = normalize_rel(l["workflow_ref"])
        new = join_rel(p["prefix"], join_rel(l.get("subfolder") or "", os.path.basename(old)))
        # Se comprueba todo antes de mover nada, para no quedarse a medias.
        if (workflows.exists(new) and new != old) or fold_case(new) in planned:
            raise UserError("exists", path=new)
        planned.add(fold_case(new))
        if _has_mirror(p) and workflows.exists(old):
            _check_mirror_free(p, new[len(p["prefix"]) + 1:], workflows.file_path(old))
        moves.append((l, old, new))
    moved, created = [], []
    try:
        for l, old, new in moves:
            mirror = _mirror_file(p, new[len(p["prefix"]) + 1:]) if _has_mirror(p) else None
            owner = _owner_by_path(db, old)[0]
            if owner and owner is not p:
                # El archivo es de otro proyecto con carpeta: ese proyecto lo conserva.
                if workflows.exists(old):
                    workflows.write(new, _copy_bytes(db, old))
                    created.append(workflows.file_path(new))
                    if mirror:
                        if not os.path.exists(mirror):
                            created.append(mirror)
                        copy_atomic(workflows.file_path(new), mirror)
                db["links"].remove(l)
                continue
            if workflows.exists(old):
                workflows.relocate(old, new)
                moved.append((old, new))
                if mirror:
                    if not os.path.exists(mirror):      # uno igual ya estaba allí: no es nuestro para borrarlo
                        created.append(mirror)
                    copy_atomic(workflows.file_path(new), mirror)
            _rewrite_links(db, old, new)
            db["links"].remove(l)
    except (OSError, UserError):
        # La BD no se guarda: los archivos deben volver a donde dice.
        _undo_relocations(moved)
        for path in created:
            try:
                os.remove(path)
            except OSError:
                pass
        raise


def _folder_to_links(db, p):
    """Quita la carpeta propia: se conservan los archivos y el proyecto pasa a ser de etiquetas."""
    for item in _project_items(db, p):
        _pull_newest(p, item["ref"])
        db["links"].append(_new_link(p["id"], item["path"], item["folder"]))
    p["folder"] = None
    p["prefix"] = None


def delete_project(pid, delete_files=False):
    """Borra el proyecto. Con `delete_files` borra además sus workflows (nunca otros archivos)."""
    db = load_db()
    p = _get(db, pid)
    if delete_files:
        try:
            _delete_project_files(db, p)
        except OSError:
            save_db(db)     # lo ya borrado no debe seguir vinculado
            raise
    db["projects"] = [x for x in db["projects"] if x["id"] != pid]
    db["links"] = [l for l in db["links"] if l["project_id"] != pid]
    save_db(db)


def _delete_folder_files(db, folder):
    """Borra los workflows de una carpeta de ComfyUI y sus vínculos, también si falla a medias."""
    try:
        removed, gone = workflows.delete_workflows_in(folder)
    except OSError as exc:
        for rel in getattr(exc, "removed", []):
            _drop_links(db, rel)
        raise
    for rel in removed:
        _drop_links(db, rel)
    if gone:
        _drop_links_under(db, folder)
    return removed, gone


def _delete_project_files(db, p):
    pid = p["id"]
    if _has_mirror(p):
        _require_mirror(p)
    if p.get("prefix"):
        _delete_folder_files(db, p["prefix"])
    if _has_mirror(p):
        for w in workflows.list_tree(root=p["folder"], follow_links=False)["workflows"]:
            if not looks_like_workflow(workflows.abs_path(w["rel"], p["folder"])):
                continue
            workflows.remove_file(w["rel"], root=p["folder"])
            workflows.prune_empty_dirs(os.path.dirname(workflows.abs_path(w["rel"], p["folder"])), p["folder"])
    for l in [l for l in db["links"] if l["project_id"] == pid]:
        ref = normalize_rel(l["workflow_ref"])
        # Lo que también usa otro proyecto se conserva: el archivo sigue siendo suyo.
        if _owner_by_path(db, ref)[0] or any(o["project_id"] != pid for o in _ref_links(db, ref)):
            continue
        if workflows.exists(l["workflow_ref"]):
            workflows.remove_file(l["workflow_ref"])
        _drop_links(db, l["workflow_ref"])


# ----------------------------- subcarpetas -----------------------------
def add_subfolder(pid, name):
    db = load_db()
    p = _get(db, pid)
    name = normalize_rel(name)
    if not name:
        raise UserError("empty_name")
    check_new_folder(name)
    if name not in p["subfolders"]:
        p["subfolders"].append(name)
        p["subfolders"].sort(key=str.lower)
    if _mirror_ready(p) or (is_local_abs(p.get("folder")) and _in_comfy(p["folder"])):
        workflows.mkdir(name, root=p["folder"])
    p["modified"] = _now()
    save_db(db)
    return name


def _replace_prefix(value, old, new):
    if value == old:
        return new
    if value.startswith(old + "/"):
        return join_rel(new, value[len(old) + 1:])
    return value


def _move_project_folders(p, old, new):
    """Mueve una subcarpeta en las dos copias de un proyecto: o en ambas, o en ninguna."""
    if _has_mirror(p):
        _require_mirror(p)
    moves = []
    if _has_mirror(p) and os.path.isdir(workflows.abs_path(old, p["folder"])):
        moves.append((old, new, p["folder"]))
    general = join_rel(p["prefix"], old)
    if os.path.isdir(workflows.abs_path(general)):
        moves.append((general, join_rel(p["prefix"], new), None))
    for source, target, root in moves:
        workflows.check_folder_move(source, target, root)
    # También contra la otra copia: la siguiente apertura mezclaría los archivos y uno pisaría al otro.
    if fold_case(old) != fold_case(new):
        targets = [(join_rel(p["prefix"], new), None)] + ([(new, p["folder"])] if _has_mirror(p) else [])
        if any(os.path.exists(workflows.abs_path(target, root)) for target, root in targets):
            raise UserError("exists", path=new)
    done = []
    try:
        for move in moves:
            workflows.move_folder(*move)
            done.append(move)
    except OSError:
        for source, target, root in reversed(done):
            workflows.move_folder(target, source, root)
        raise


def rename_subfolder(pid, old, new):
    """Renombra/mueve una subcarpeta de un proyecto (también en disco si tiene carpeta propia)."""
    db = load_db()
    p = _get(db, pid)
    old, new = normalize_rel(old), normalize_rel(new)
    if not old or not new:
        raise UserError("root_forbidden")
    check_new_folder(new)
    if not p.get("folder") and old.lower() != new.lower():
        # Se mezclarían con lo que ya hay allí, y deshacerlo se lo llevaría todo.
        taken = {*(p["subfolders"]), *(l.get("subfolder") or "" for l in db["links"] if l["project_id"] == pid)}
        if any(_overlaps(new, s) and len(s) >= len(new) for s in taken if s):
            raise UserError("exists", path=new)
    if p.get("folder"):
        general = join_rel(p["prefix"], old)
        _move_project_folders(p, old, new)
        for l in db["links"]:
            l["workflow_ref"] = _replace_prefix(normalize_rel(l["workflow_ref"]), general, join_rel(p["prefix"], new))
    for l in db["links"]:
        if l["project_id"] == pid:
            l["subfolder"] = _replace_prefix(l.get("subfolder") or "", old, new)
    p["subfolders"] = sorted({_replace_prefix(s, old, new) for s in p["subfolders"]}, key=str.lower)
    p["modified"] = _now()
    save_db(db)
    return new


def remove_subfolder(pid, name):
    """Quita una subcarpeta. Sin carpeta propia, sus workflows pasan a la raíz del proyecto."""
    db = load_db()
    p = _get(db, pid)
    name = normalize_rel(name)
    if not name:
        raise UserError("root_forbidden")
    if p.get("folder"):
        if _has_mirror(p):
            _require_mirror(p)
        try:
            _delete_folder_files(db, join_rel(p["prefix"], name))
            if _has_mirror(p):
                workflows.delete_workflows_in(name, root=p["folder"])
        except OSError:
            save_db(db)     # lo ya borrado no debe seguir vinculado
            raise
    for l in db["links"]:
        if l["project_id"] == pid and _replace_prefix(l.get("subfolder") or "", name, "\0") != (l.get("subfolder") or ""):
            l["subfolder"] = ""
    p["subfolders"] = [s for s in p["subfolders"] if _replace_prefix(s, name, "\0") == s]
    p["modified"] = _now()
    save_db(db)


# ----------------------------- vínculos -----------------------------
def _new_link(pid, ref, subfolder=""):
    return {"id": _gen_id("l_"), "project_id": pid, "subfolder": normalize_rel(subfolder),
            "workflow_ref": ref, "alias": "", "created": _now()}


def _ref_links(db, ref):
    return [l for l in db["links"] if normalize_rel(l["workflow_ref"]) == ref]


def _rewrite_links(db, old, new):
    for l in db["links"]:
        if normalize_rel(l["workflow_ref"]) == old:
            l["workflow_ref"] = new


def _drop_links(db, ref, pid=None):
    ref = normalize_rel(ref)
    db["links"] = [l for l in db["links"]
                   if normalize_rel(l["workflow_ref"]) != ref or (pid and l["project_id"] != pid)]


def _links_snapshot(db, path):
    """Vínculos actuales de un archivo, para poder deshacer un movimiento."""
    return [{"project_id": l["project_id"], "subfolder": l.get("subfolder") or ""} for l in _ref_links(db, path)]


def _drop_links_under(db, folder):
    db["links"] = [l for l in db["links"] if not normalize_rel(l["workflow_ref"]).startswith(folder + "/")]


def link_workflow(pid, path, subfolder="", allow_multi=False):
    """Vincula un workflow a un proyecto sin carpeta propia. Exclusivo salvo `allow_multi`."""
    db = load_db()
    _link(db, _get(db, pid), normalize_rel(path), normalize_rel(subfolder), allow_multi)
    save_db(db)


def _link(db, p, path, subfolder, allow_multi):
    if not workflows.exists(path):
        raise UserError("not_found", path=path)
    existing = _ref_links(db, path)
    for l in existing:
        if l["project_id"] == p["id"]:
            l["subfolder"] = subfolder
            return
    if existing and not allow_multi:
        raise UserError("already_linked", file=os.path.basename(path),
                        project=_get(db, existing[0]["project_id"])["name"])
    db["links"].append(_new_link(p["id"], path, subfolder))


def unlink(pid, path):
    """Quita un workflow de un proyecto de etiquetas (el archivo se conserva)."""
    db = load_db()
    path = normalize_rel(path)
    if not any(l["project_id"] == pid for l in _ref_links(db, path)):
        raise UserError("not_linked")
    _drop_links(db, path, pid)
    save_db(db)


# ----------------------------- vista -----------------------------
def _stat(path):
    try:
        st = os.stat(path)
        return st.st_size, st.st_mtime
    except OSError:
        return None


def _project_items(db, p):
    items = []
    if p.get("folder"):
        prefix = p["prefix"]
        refs = {}
        base = workflows.abs_path(prefix)
        if os.path.isdir(base):
            for w in workflows.list_tree(root=base)["workflows"]:
                refs[fold_case(w["rel"])] = w
        if _has_mirror(p) and os.path.isdir(p["folder"]):
            for w in workflows.list_tree(root=p["folder"])["workflows"]:
                # `Foo.json` y `foo.json` son un solo archivo en Windows: manda el nombre de la copia de ComfyUI.
                known = refs.get(fold_case(w["rel"]))
                if not known:
                    refs[fold_case(w["rel"])] = w
                elif w["mtime"] > known["mtime"]:
                    refs[fold_case(w["rel"])] = {**w, "rel": known["rel"], "name": known["name"], "folder": known["folder"]}
        for w in refs.values():
            ref = w["rel"]
            items.append({"path": join_rel(prefix, ref), "ref": ref, "name": w["name"], "folder": w["folder"],
                          "exists": True, "size": w["size"], "mtime": w["mtime"],
                          "shared": bool(_ref_links(db, join_rel(prefix, ref)))})
    else:
        for l in db["links"]:
            if l["project_id"] != p["id"]:
                continue
            ref = normalize_rel(l["workflow_ref"])
            stat = _stat(workflows.abs_path(ref))
            items.append({"path": ref, "ref": ref, "name": os.path.basename(ref),
                          "folder": l.get("subfolder") or "", "exists": stat is not None,
                          "size": stat[0] if stat else 0, "mtime": stat[1] if stat else 0,
                          "shared": len(_ref_links(db, ref)) > 1 or bool(_owner_by_path(db, ref)[0])})
    items.sort(key=lambda i: i["path"].lower())
    return items


def _project_subfolders(p, items):
    subs = set(p.get("subfolders") or [])
    if p.get("folder"):
        for root in ([p["folder"]] if _has_mirror(p) and os.path.isdir(p["folder"]) else []):
            subs.update(workflows.list_tree(root=root)["folders"])
        base = workflows.abs_path(p["prefix"])
        if os.path.isdir(base):
            subs.update(workflows.list_tree(root=base)["folders"])
    for item in items:
        if item["folder"]:
            subs.add(item["folder"])
    # Incluir los antecesores: el árbol necesita "a" aunque solo exista "a/b".
    for s in list(subs):
        while "/" in s:
            s = s.rsplit("/", 1)[0]
            subs.add(s)
    return sorted(subs, key=str.lower)


def tree():
    """Estado completo para la UI: proyectos y workflows en un mismo árbol."""
    db = load_db()
    general = workflows.list_tree()
    prefixes = [p["prefix"] for p in db["projects"] if p.get("prefix")]

    def under_project(rel):
        return any(_overlaps(pre, rel) and len(rel) >= len(pre) for pre in prefixes)

    owners = {}
    for l in db["links"]:
        owners.setdefault(normalize_rel(l["workflow_ref"]), []).append(l["project_id"])
    files = []
    for w in general["workflows"]:
        if under_project(w["rel"]):
            continue
        files.append({**w, "path": w["rel"], "projects": owners.get(w["rel"], [])})

    projects = []
    for p in db["projects"]:
        items = _project_items(db, p)
        projects.append({
            "id": p["id"], "name": p["name"], "color": p["color"], "notes": p["notes"],
            "folder": p.get("folder"), "prefix": p.get("prefix"), "mirror": _has_mirror(p),
            "folder_ok": bool(p.get("folder")) and os.path.isdir(p["folder"]),
            "remote_url": p["git"].get("remote_url", ""),
            "subfolders": _project_subfolders(p, items), "items": items,
        })
    projects.sort(key=lambda p: p["name"].lower())
    return {
        "comfy_root": general["root"],
        "folders": [f for f in general["folders"] if not under_project(f)],
        "workflows": files,
        "projects": projects,
    }


# ----------------------------- espejo con la carpeta del proyecto -----------------------------
def _pull_newest(p, ref):
    """Iguala la copia de ComfyUI y la del proyecto: gana el archivo más reciente."""
    if not _mirror_ready(p) or _case_clash(p, ref):
        return
    general = workflows.file_path(join_rel(p["prefix"], ref))
    mirror = _mirror_file(p, ref)
    g, m = _stat(general), _stat(mirror)
    if g and not m:
        copy_atomic(general, mirror)
    elif m and not g:
        copy_atomic(mirror, general)
    elif g and m and (g[0] != m[0] or abs(g[1] - m[1]) > MTIME_SLACK):
        if g[1] > m[1]:
            copy_atomic(general, mirror)
        else:
            copy_atomic(mirror, general)


def _case_clash(p, ref):
    """True si la copia del proyecto de `ref` es en realidad la de otro workflow.

    Linux distingue `Foo.json` y `foo.json`, pero un disco de red puede que no: en él serían un solo archivo.
    """
    mirror = _mirror_file(p, ref)
    if not os.path.exists(mirror):      # un disco que sí las distingue: tienen cada uno su archivo
        return False
    folder, name = os.path.split(mirror)
    try:
        names = os.listdir(folder)
    except OSError:
        return False
    wanted = unicodedata.normalize("NFC", name)
    if any(unicodedata.normalize("NFC", n) == wanted for n in names):
        return False
    general = workflows.file_path(join_rel(p["prefix"], ref))
    for n in names:
        if unicodedata.normalize("NFC", n).lower() == wanted.lower():
            other = os.path.join(os.path.dirname(general), n)
            if os.path.isfile(other) and not _same_file(other, general):
                return True
    return False


def _keep_foreign_mirror(p, ref, source):
    """Conserva, con otro nombre, el archivo que ya hubiera en la carpeta del proyecto y sea distinto.

    Desde ComfyUI solo se ve su propia carpeta: guardar o renombrar con un nombre libre allí puede coincidir
    con uno que solo está en la del proyecto, como lo traído por un `git pull` y aún sin abrir. Devuelve el
    nombre con el que se ha conservado, o None si no había nada que conservar.
    """
    if not _mirror_ready(p):
        return None
    mirror = _mirror_file(p, ref)
    if not os.path.isfile(mirror) or _same_bytes(source, mirror):
        return None
    base, ext = os.path.splitext(mirror)
    candidate, n = f"{base} (conflict){ext}", 1
    while os.path.exists(candidate):
        n += 1
        candidate = f"{base} (conflict {n}){ext}"
    os.replace(mirror, candidate)
    return os.path.basename(candidate)


def _mirror_changed_since(p, ref, previous, base=None):
    """True si la copia del proyecto es posterior a la versión que conocía la pestaña que se ha guardado.

    Es lo que pasa tras un `git pull` con la pestaña abierta. `previous` es la fecha del archivo según
    ComfyUI, en segundos o en milisegundos según su versión. `base` es su contenido según la pestaña: si la
    copia dice lo mismo, solo ha cambiado la fecha (cambiar de rama y volver, un disco de red con otro reloj).
    """
    if isinstance(previous, bool) or not isinstance(previous, (int, float)) or previous <= 0:
        return False
    mirror = _mirror_file(p, ref)
    stat = _stat(mirror)
    if not stat or stat[1] <= (previous / 1000 if previous > 1e11 else previous) + MTIME_SLACK:
        return False
    if isinstance(base, str):
        with open(mirror, "rb") as fh:
            return fh.read().decode("utf-8-sig", "replace") != base
    return True


def prepare_open(path):
    """Deja el archivo listo en la carpeta de ComfyUI antes de abrirlo en una pestaña."""
    db = load_db()
    path = normalize_rel(path)
    p, ref = _owner_by_path(db, path)
    if p:
        _pull_newest(p, ref)
    workflows.existing_file(path)
    return path


def mirror_saved(path, created=False, previous=None, base=None):
    """ComfyUI acaba de guardar `path`: actualiza la copia en la carpeta del proyecto.

    `created`: no existía en ComfyUI antes de este guardado. `previous` y `base`: fecha y contenido del
    archivo que conocía la pestaña. Devuelve (proyecto o None, nombre con el que se ha conservado otra
    versión o None).
    """
    db = load_db()
    path = normalize_rel(path)
    p, ref = _owner_by_path(db, path)
    if not p or not _has_mirror(p):
        return None, None
    _require_mirror(p)
    if _case_clash(p, ref):
        raise UserError("exists", path=_mirror_file(p, ref))
    source = workflows.existing_file(path)
    conflict = None
    if created or _mirror_changed_since(p, ref, previous, base):
        conflict = _keep_foreign_mirror(p, ref, source)
    copy_atomic(source, _mirror_file(p, ref))
    return p["name"], conflict


def on_saved(path, created=False, previous=None):
    return mirror_saved(path, created, previous)[0]


def on_renamed(old, new):
    """ComfyUI acaba de renombrar/mover un archivo: reconcilia vínculos y copias de proyecto."""
    db = load_db()
    old, new = normalize_rel(old), normalize_rel(new)
    if not old or not new:
        raise UserError("missing_field", field="new" if old else "old")
    # Si no está en el destino, no se ha movido: quitar la copia y los vínculos del origen los perdería.
    if not workflows.exists(new):
        raise UserError("not_found", path=new)
    # ComfyUI ya ha movido el archivo: aunque falle la copia del proyecto, los vínculos deben seguirlo.
    try:
        dst_p, dst_ref = _owner_by_path(db, new)
        src_p, src_ref = _owner_by_path(db, old)
        if dst_p and _has_mirror(dst_p) and workflows.exists(new) and not (
                src_p and _has_mirror(src_p) and _same_file(_mirror_file(src_p, src_ref), _mirror_file(dst_p, dst_ref))):
            _keep_foreign_mirror(dst_p, dst_ref, workflows.file_path(new))
        _sync_mirrors_after_move(db, old, new)
    finally:
        _rewrite_links(db, old, new)
        save_db(db)


def on_deleted(path):
    """ComfyUI acaba de borrar un archivo: quita sus vínculos (la copia del proyecto se conserva).

    Al sobrescribir con "Guardar como", ComfyUI borra el archivo y lo vuelve a crear: en ese caso sigue
    existiendo y conserva sus vínculos.
    """
    path = normalize_rel(path)
    if workflows.exists(path):
        return
    db = load_db()
    _drop_links(db, path)
    save_db(db)


def _sync_mirrors_after_move(db, old, new):
    src_p, src_ref = _owner_by_path(db, old)
    dst_p, dst_ref = _owner_by_path(db, new)
    src_mirror = _mirror_file(src_p, src_ref) if src_p and _has_mirror(src_p) else None
    dst_mirror = _mirror_file(dst_p, dst_ref) if dst_p and _has_mirror(dst_p) else None
    if src_mirror and dst_mirror and _same_file(src_mirror, dst_mirror):
        # Solo cambian mayúsculas en un disco que no las distingue: borrar el "antiguo" lo perdería.
        os.replace(src_mirror, dst_mirror)
        src_mirror = None
    created = False
    if dst_mirror and workflows.exists(new):
        _require_mirror(dst_p)
        if _case_clash(dst_p, dst_ref):
            raise UserError("exists", path=dst_mirror)
        created = not os.path.exists(dst_mirror)
        copy_atomic(workflows.file_path(new), dst_mirror)
    # Una pestaña abierta se mueve sin mirar la carpeta del proyecto: lo llegado allí después no se tira.
    if src_mirror and workflows.exists(new) and not (dst_mirror and _same_file(src_mirror, dst_mirror)):
        general, mirror = _stat(workflows.file_path(new)), _stat(src_mirror)
        if mirror and mirror[1] > general[1] + MTIME_SLACK:
            _keep_foreign_mirror(src_p, src_ref, workflows.file_path(new))
    # Renombrar solo mayúsculas sin copia previa: ahora son el mismo archivo y no hay nada que quitar.
    if src_mirror and os.path.isfile(src_mirror) and not (dst_mirror and _same_file(src_mirror, dst_mirror)):
        try:
            os.remove(src_mirror)
        except OSError:
            if created:
                os.remove(dst_mirror)
            raise
        workflows.prune_empty_dirs(os.path.dirname(src_mirror), src_p["folder"])


def _same_file(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def _move_file(db, old, new, general_moved):
    """Mueve un workflow y sus copias de proyecto. Si la carpeta del proyecto falla, lo deja como estaba."""
    if general_moved and not workflows.exists(new):
        raise UserError("not_found", path=new)
    if not general_moved:
        _ensure_general(db, old)
        workflows.relocate(old, new)
    try:
        _sync_mirrors_after_move(db, old, new)
    except (OSError, UserError):
        if not general_moved:
            workflows.relocate(new, old)
        raise


# ----------------------------- operaciones sobre workflows -----------------------------
def _is_mirrored(db, path):
    p, ref = _owner_by_path(db, path)
    return (p, ref) if p else (None, None)


def _ensure_general(db, path):
    """Asegura que el archivo está en la carpeta de ComfyUI (puede estar solo en el espejo)."""
    p, ref = _is_mirrored(db, path)
    if p:
        _pull_newest(p, ref)


def _foreign_file(db, path, src, tgt):
    """True si se saca un vínculo cuyo archivo vive en la carpeta de otro proyecto, que lo conserva."""
    owner = _owner_by_path(db, path)[0]
    return bool(src and not src.get("folder") and owner and owner is not tgt)


def plan_move(db, path, src_pid, tgt_pid, tgt_folder):
    """Calcula la ruta canónica que tendrá un workflow al moverlo a un destino."""
    name = os.path.basename(path)
    src = _get(db, src_pid) if src_pid else None
    tgt = _get(db, tgt_pid) if tgt_pid else None
    if _foreign_file(db, path, src, tgt):
        return path
    if tgt and tgt.get("folder"):
        return join_rel(tgt["prefix"], join_rel(tgt_folder, name))
    if tgt:  # proyecto de etiquetas: el archivo no se mueve, salvo que salga de un proyecto con carpeta
        return name if src and src.get("folder") else path
    if src and not src.get("folder") and not tgt_folder:
        return path  # sacar de un proyecto de etiquetas a "Workflows" = solo desvincular
    return join_rel(tgt_folder, name)


def _check_target_free(db, new, general_moved=False):
    """Evita pisar un archivo existente en el destino, en ComfyUI o en la carpeta del proyecto."""
    if not general_moved and workflows.exists(new):
        raise UserError("exists", path=new)
    owner, ref = _is_mirrored(db, new)
    if owner and _has_mirror(owner):
        _require_mirror(owner)
        if os.path.isfile(_mirror_file(owner, ref)):
            raise UserError("exists", path=new)


def check_free(path):
    """Error si no se puede crear un workflow en esa ruta, también por la carpeta del proyecto."""
    _check_target_free(load_db(), normalize_rel(path))


def _check_move(db, old, new, general_moved=False):
    """Comprueba origen y destino. Sacar un archivo de una carpeta desmontada dejaría allí una copia
    que volvería a aparecer al montarla."""
    owner = _is_mirrored(db, old)[0]
    if owner and _has_mirror(owner):
        _require_mirror(owner)
    _check_target_free(db, new, general_moved)


def move_item(path, src_pid=None, tgt_pid=None, tgt_folder="", dry_run=False, general_moved=False,
              exclusive=False):
    """Mueve un workflow entre carpetas/proyectos. Devuelve {old, new}.

    `general_moved`: una pestaña abierta ya ha movido el archivo con la API de ComfyUI, así que aquí
    solo quedan por reconciliar las copias de proyecto y los vínculos.
    `exclusive`: además lo saca de cualquier otro proyecto sin carpeta en el que estuviera.
    """
    db = load_db()
    path = normalize_rel(path)
    tgt_folder = normalize_rel(tgt_folder)
    # En un proyecto sin carpeta solo es una etiqueta: puede venir de una versión anterior.
    if not tgt_pid or _get(db, tgt_pid).get("folder"):
        check_new_folder(tgt_folder)
    new = plan_move(db, path, src_pid, tgt_pid, tgt_folder)
    if dry_run:
        # moveWithTabs mueve la pestaña tras el ensayo: si no se puede completar, debe fallar aquí.
        if new != path:
            _check_move(db, path, new)
        return {"old": path, "new": new}

    src = _get(db, src_pid) if src_pid else None
    tgt = _get(db, tgt_pid) if tgt_pid else None
    links = _links_snapshot(db, path)
    if tgt and tgt.get("folder") and _foreign_file(db, path, src, tgt):
        # El archivo sigue en su proyecto; el destino, con carpeta propia, necesita su propia copia.
        copy = duplicate_item(path, tgt_pid, tgt_folder)
        db = load_db()
        _drop_links(db, path, src["id"])
        save_db(db)
        return _copy_result(path, links, copy)
    if new != path:
        _check_move(db, path, new, general_moved)
        _move_file(db, path, new, general_moved)
        _rewrite_links(db, path, new)
    elif not workflows.exists(path):
        raise UserError("not_found", path=path)

    if src and not src.get("folder"):
        _drop_links(db, new, src["id"])
    if exclusive:
        _drop_links(db, new)
    if tgt and not tgt.get("folder"):
        _drop_links(db, new, tgt["id"])
        db["links"].append(_new_link(tgt["id"], new, tgt_folder))
    save_db(db)
    return {"old": path, "new": new, "links": links}


def _copy_result(path, links, copy):
    """Resultado de una operación que ha creado una copia: el archivo original no cambia de sitio."""
    return {"old": path, "new": path, "links": links, "copied": copy,
            "copied_mtime": os.path.getmtime(workflows.file_path(copy))}


def undo_move(old, new, links=None, copied=None, copied_mtime=None, dry_run=False, general_moved=False):
    """Revierte un movimiento a partir de lo que devolvió: de `new` a `old`, con sus vínculos de entonces."""
    old, new = normalize_rel(old), normalize_rel(new)
    db = load_db()
    copied = normalize_rel(copied) if copied else None
    if copied and workflows.exists(copied):
        # No se borra una copia en la que ya se ha trabajado.
        if copied_mtime is None or abs(os.path.getmtime(workflows.file_path(copied)) - float(copied_mtime)) > 0.001:
            raise UserError("copy_changed", path=copied)
    if dry_run:
        if new != old:
            _check_move(db, new, old)
        return {"old": new, "new": old}
    if copied and workflows.exists(copied):
        delete_item(copied)
        db = load_db()
    if new != old:
        _check_move(db, new, old, general_moved)
        _move_file(db, new, old, general_moved)
        _rewrite_links(db, new, old)
    if isinstance(links, list):
        known = {p["id"] for p in db["projects"]}
        _drop_links(db, old)
        for l in links:
            if isinstance(l, dict) and l.get("project_id") in known:
                db["links"].append(_new_link(l["project_id"], old, l.get("subfolder") or ""))
    save_db(db)
    return {"old": new, "new": old}


def add_to_project(path, pid, subfolder="", allow_multi=False, dry_run=False, general_moved=False):
    """Añade un workflow a un proyecto: vínculo (sin carpeta) o traslado a su carpeta propia.

    Si el archivo ya vive en la carpeta de otro proyecto, el destino con carpeta recibe una copia.
    """
    db = load_db()
    p = _get(db, pid)
    path = normalize_rel(path)
    if p.get("folder"):
        owner = _owner_by_path(db, path)[0]
        if owner and owner is not p:
            if dry_run:
                return {"old": path, "new": path}
            return _copy_result(path, _links_snapshot(db, path), duplicate_item(path, pid, subfolder))
        return move_item(path, None, pid, subfolder, dry_run=dry_run, general_moved=general_moved)
    if dry_run:
        return {"old": path, "new": path}
    links = _links_snapshot(db, path)
    # Si ya vive en la carpeta de otro proyecto, sería compartirlo: como con los vínculos, se pregunta antes.
    owner = _owner_by_path(db, path)[0]
    if owner and not allow_multi and not any(l["project_id"] == pid for l in _ref_links(db, path)):
        raise UserError("already_linked", file=os.path.basename(path), project=owner["name"])
    _link(db, p, path, normalize_rel(subfolder), allow_multi)
    save_db(db)
    return {"old": path, "new": path, "links": links}


def rename_item(path, new_name, dry_run=False, general_moved=False):
    db = load_db()
    path = normalize_rel(path)
    folder, _ = split_rel(path)
    new = join_rel(folder, ensure_json_ext(new_name))
    if new == path:
        return {"old": path, "new": new}
    if fold_case(new) != fold_case(path):
        _check_move(db, path, new, general_moved and not dry_run)
    else:
        _check_case_rename(db, path, new)
    if dry_run:
        return {"old": path, "new": new}
    _move_file(db, path, new, general_moved)
    _rewrite_links(db, path, new)
    save_db(db)
    return {"old": path, "new": new}


def _check_case_rename(db, old, new):
    """Solo cambian mayúsculas: es el mismo archivo, salvo en una carpeta que sí las distingue."""
    def distinct(a, b):
        return os.path.isfile(a) and os.path.isfile(b) and not _same_file(a, b)

    if distinct(workflows.file_path(old), workflows.file_path(new)):
        raise UserError("exists", path=new)
    src_p, src_ref = _owner_by_path(db, old)
    dst_p, dst_ref = _owner_by_path(db, new)
    if src_p and dst_p and _has_mirror(src_p) and _has_mirror(dst_p) \
            and distinct(_mirror_file(src_p, src_ref), _mirror_file(dst_p, dst_ref)):
        raise UserError("exists", path=new)


def import_workflow(name, content, pid=None, folder=""):
    """Crea un workflow a partir de un archivo externo, sin pisar nada. Devuelve su ruta."""
    db = load_db()
    folder = normalize_rel(folder)
    name = ensure_json_ext(name)
    try:
        json.loads(content)
    except ValueError:
        raise UserError("bad_json", name=name)
    target = _get(db, pid) if pid else None
    if target and target.get("folder"):
        dest = join_rel(target["prefix"], folder)
    else:
        dest = "" if target else folder
    rel = join_rel(dest, name)
    _check_target_free(db, rel)
    # Un vínculo de otro proyecto a un archivo desaparecido: se comprueba antes de crear nada.
    if target and not target.get("folder"):
        others = [l for l in _ref_links(db, rel) if l["project_id"] != target["id"]]
        if others:
            raise UserError("already_linked", file=name, project=_get(db, others[0]["project_id"])["name"])
    workflows.write(rel, content)
    on_saved(rel)
    if target and not target.get("folder"):
        link_workflow(pid, rel, folder)
    return rel


def _free_name(db, folder, name):
    """Nombre libre en una carpeta de ComfyUI, teniendo en cuenta también el espejo del proyecto."""
    base, ext = os.path.splitext(name)
    candidate, n = name, 1
    while True:
        rel = join_rel(folder, candidate)
        owner, ref = _is_mirrored(db, rel)
        taken = workflows.exists(rel) or bool(owner and _has_mirror(owner) and os.path.isfile(_mirror_file(owner, ref)))
        if not taken:
            return candidate
        candidate = f"{base} copy{ext}" if n == 1 else f"{base} copy {n}{ext}"
        n += 1


def _newest_file(db, path):
    """Archivo más reciente de un workflow. Solo lee: el archivo puede tener una pestaña abierta."""
    p, ref = _is_mirrored(db, path)
    if p and _has_mirror(p):
        general, mirror = _stat(workflows.file_path(path)), _stat(_mirror_file(p, ref))
        if mirror and (not general or mirror[1] > general[1]):
            return _mirror_file(p, ref)
    return workflows.existing_file(path)


def _copy_bytes(db, path):
    """Contenido de un workflow para una copia: ComfyUI los identifica por su id, necesita uno propio."""
    with open(_newest_file(db, path), "rb") as fh:
        data = fh.read()
    try:
        state = json.loads(data.decode("utf-8"))
        if isinstance(state, dict) and "id" in state:
            state["id"] = str(uuid.uuid4())
            data = json.dumps(state, ensure_ascii=False).encode("utf-8")
    except ValueError:
        pass
    return data


def duplicate_item(path, tgt_pid=None, tgt_folder=None, new_name=None):
    """Copia independiente de un workflow, opcionalmente en otro proyecto. Devuelve su ruta."""
    db = load_db()
    path = normalize_rel(path)
    data = _copy_bytes(db, path)
    src_folder, src_name = split_rel(path)
    name = ensure_json_ext(new_name) if new_name else src_name
    tgt = _get(db, tgt_pid) if tgt_pid else None
    folder = normalize_rel(tgt_folder) if tgt_folder is not None else None
    if tgt and tgt.get("folder"):
        dest_dir = join_rel(tgt["prefix"], folder or "")
    elif tgt:
        dest_dir = "" if _is_mirrored(db, path)[0] else src_folder
    else:
        dest_dir = folder if folder is not None else src_folder
    new = join_rel(dest_dir, _free_name(db, dest_dir, name))
    owner, ref = _is_mirrored(db, new)
    if owner and _has_mirror(owner):
        _require_mirror(owner)
    workflows.write(new, data)
    if owner and _has_mirror(owner):
        copy_atomic(workflows.file_path(new), _mirror_file(owner, ref))
    if tgt and not tgt.get("folder"):
        db["links"].append(_new_link(tgt["id"], new, folder or ""))
        save_db(db)
    return new


def delete_item(path):
    """Borra un workflow de la carpeta de ComfyUI, de la del proyecto y de todos los vínculos."""
    db = load_db()
    path = normalize_rel(path)
    p, ref = _is_mirrored(db, path)
    if p and _has_mirror(p):
        _require_mirror(p)
    found = False
    if workflows.exists(path):
        workflows.remove_file(path)
        # La carpeta propia de un proyecto se conserva aunque se quede vacía.
        stop = workflows.abs_path(p["prefix"]) if p else workflows.get_root()
        workflows.prune_empty_dirs(os.path.dirname(workflows.abs_path(path)), stop)
        found = True
    if p and _has_mirror(p):
        mirror = _mirror_file(p, ref)
        if os.path.isfile(mirror):
            os.remove(mirror)
            workflows.prune_empty_dirs(os.path.dirname(mirror), p["folder"])
            found = True
    if not found and not _ref_links(db, path):
        raise UserError("not_found", path=path)
    _drop_links(db, path)
    save_db(db)


def source_file(path):
    """Archivo más reciente de un workflow (para exportar)."""
    db = load_db()
    return _newest_file(db, normalize_rel(path))


def project_export_files(pid, subfolder=None):
    """Lista (abs_path, arcname) de los workflows de un proyecto y su nombre."""
    db = load_db()
    p = _get(db, pid)
    files = []
    for item in _project_items(db, p):
        if not item["exists"]:
            continue
        if subfolder and item["folder"] != subfolder and not item["folder"].startswith(subfolder + "/"):
            continue
        files.append((source_file(item["path"]), f"{p['name']}/{join_rel(item['folder'], item['name'])}"))
    return p["name"], files


# ----------------------------- operaciones sobre carpetas de ComfyUI -----------------------------
def _check_no_project_in(db, *folders):
    """Las carpetas de "Workflows" no pueden tocar los archivos de un proyecto con carpeta."""
    for folder in folders:
        for p in db["projects"]:
            if folder and p.get("prefix") and _overlaps(p["prefix"], folder):
                raise UserError("folder_has_project", project=p["name"])


def create_general_folder(folder):
    db = load_db()
    folder = normalize_rel(folder)
    _check_no_project_in(db, folder)
    return workflows.mkdir(folder)


def rename_general_folder(folder, new_folder):
    """Mueve/renombra una carpeta de "Workflows" y actualiza los vínculos de lo que contiene."""
    db = load_db()
    folder, new_folder = normalize_rel(folder), normalize_rel(new_folder)
    check_new_folder(new_folder)
    _check_no_project_in(db, folder, new_folder)
    result = workflows.move_folder(folder, new_folder)
    for l in db["links"]:
        l["workflow_ref"] = _replace_prefix(normalize_rel(l["workflow_ref"]), folder, new_folder)
    save_db(db)
    return result


def delete_general_folder(folder):
    db = load_db()
    folder = normalize_rel(folder)
    if not folder:
        raise UserError("root_forbidden")
    _check_no_project_in(db, folder)
    try:
        removed, gone = _delete_folder_files(db, folder)
    except OSError:
        save_db(db)     # lo ya borrado no debe seguir vinculado
        raise
    save_db(db)
    return {"removed": len(removed), "gone": gone}


def git_folder(pid):
    """Carpeta sobre la que opera Git para un proyecto."""
    db = load_db()
    p = _get(db, pid)
    if not p.get("folder"):
        raise UserError("git_no_folder")
    return p["folder"]


def set_remote(pid, url):
    db = load_db()
    _get(db, pid)["git"]["remote_url"] = url
    save_db(db)
