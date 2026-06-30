# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Base de datos interna exportable de Proyectos.

Un proyecto agrupa workflows de dos maneras posibles (se elige al crear):

  - storage="virtual": el proyecto NO toca el disco; son *etiquetas*. La pertenencia vive en la
    tabla `links` (ref relativa a la raíz general de workflows). Por defecto un workflow pertenece a
    un único proyecto (link `primary`); "vincular a otro proyecto" añade un link extra al MISMO
    archivo (la UI avisa de que editarlo afecta a todos).

  - storage="folder": el proyecto ES una carpeta real. Sus workflows existen físicamente dentro de
    esa carpeta y sus subcarpetas son directorios reales. La pertenencia se deriva de escanear la
    carpeta (no de la tabla `links`); `links` solo guarda metadatos opcionales (alias).

`git` por proyecto: {mode: studio|dedicated|local|none, remote_url}. La ejecución la hace git_ops.

La BD es un único JSON (config.get_db_path()), exportable/importable tal cual.
"""
import os
import time
import uuid

from . import config, workflows
from .util import is_workflow_file, normalize_rel, safe_join, slugify

DB_VERSION = 1
VALID_STORAGE = ("virtual", "folder")
VALID_GIT_MODES = ("studio", "dedicated", "local", "none")


# ----------------------------- helpers BD -----------------------------
def _now():
    return time.time()


def _gen_id(prefix):
    return prefix + uuid.uuid4().hex[:12]


def _empty_db():
    return {"version": DB_VERSION, "projects": [], "links": [], "settings": {"active_project": None}}


def load_db():
    from .util import load_json
    db = load_json(config.get_db_path(), default=None)
    if not isinstance(db, dict):
        db = _empty_db()
    db.setdefault("version", DB_VERSION)
    db.setdefault("projects", [])
    db.setdefault("links", [])
    db.setdefault("settings", {})
    db["settings"].setdefault("active_project", None)
    return db


def save_db(db):
    from .util import save_json
    save_json(config.get_db_path(), db)
    return db


def export_db():
    """Devuelve la BD tal cual (para descargar)."""
    return load_db()


def import_db(data, merge=False):
    """Reemplaza (o fusiona) la BD con `data`. Valida la estructura mínima."""
    if not isinstance(data, dict) or "projects" not in data or "links" not in data:
        raise ValueError("El archivo no es una base de datos de proyectos válida.")
    if not merge:
        data.setdefault("version", DB_VERSION)
        data.setdefault("settings", {"active_project": None})
        return save_db(data)
    db = load_db()
    by_id = {p["id"]: p for p in db["projects"]}
    for p in data.get("projects", []):
        by_id[p["id"]] = p
    db["projects"] = list(by_id.values())
    link_ids = {l["id"] for l in db["links"]}
    for l in data.get("links", []):
        if l["id"] not in link_ids:
            db["links"].append(l)
    return save_db(db)


def _get(db, pid):
    for p in db["projects"]:
        if p["id"] == pid:
            return p
    raise ValueError(f"Proyecto desconocido: {pid}")


def _phys_root(project):
    """Raíz física donde viven los archivos de un proyecto."""
    if project.get("storage") == "folder" and project.get("folder"):
        return os.path.abspath(project["folder"])
    return workflows.get_root()


def _under_user_root(abs_path):
    """True si `abs_path` cuelga de la raíz de workflows de ComfyUI (apertura nativa rastreada)."""
    try:
        return os.path.normcase(os.path.abspath(abs_path)).startswith(
            os.path.normcase(config.default_workflows_root())
        )
    except Exception:
        return False


# ----------------------------- proyectos -----------------------------
def create_project(name, color="#AC1F23", storage="virtual", folder=None,
                   git=None, notes="", subfolders=None):
    name = (name or "").strip()
    if not name:
        raise ValueError("El nombre del proyecto es obligatorio.")
    if storage not in VALID_STORAGE:
        raise ValueError(f"Almacenamiento no válido: {storage}")

    git = git or {}
    mode = git.get("mode", "none")
    if mode not in VALID_GIT_MODES:
        raise ValueError(f"Modo Git no válido: {mode}")

    if storage == "folder":
        folder = (folder or "").strip()
        if not folder:
            raise ValueError("Un proyecto con carpeta vinculada necesita una ruta.")
        folder = os.path.abspath(folder)
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as exc:
            raise ValueError(f"No se pudo usar la carpeta en el servidor: {exc}")
    else:
        folder = None
        if mode == "dedicated":
            raise ValueError("El modo Git 'dedicated' requiere una carpeta vinculada.")

    db = load_db()
    if any(p["name"].lower() == name.lower() for p in db["projects"]):
        raise ValueError(f"Ya existe un proyecto llamado «{name}».")

    project = {
        "id": _gen_id("p_"),
        "name": name,
        "color": color or "#AC1F23",
        "storage": storage,
        "folder": folder,
        "subfolders": [normalize_rel(s) for s in (subfolders or []) if s],
        "git": {"mode": mode, "remote_url": (git.get("remote_url") or "").strip()},
        "notes": notes or "",
        "created": _now(),
        "modified": _now(),
    }
    db["projects"].append(project)
    save_db(db)
    return project


def update_project(pid, **fields):
    """Actualiza campos editables: name, color, notes, git, storage, folder."""
    db = load_db()
    p = _get(db, pid)
    if "name" in fields:
        name = (fields["name"] or "").strip()
        if not name:
            raise ValueError("El nombre del proyecto es obligatorio.")
        if any(o["id"] != pid and o["name"].lower() == name.lower() for o in db["projects"]):
            raise ValueError(f"Ya existe un proyecto llamado «{name}».")
        p["name"] = name
    if "color" in fields and fields["color"]:
        p["color"] = fields["color"]
    if "notes" in fields:
        p["notes"] = fields["notes"] or ""
    if "git" in fields and isinstance(fields["git"], dict):
        mode = fields["git"].get("mode", p["git"].get("mode", "none"))
        if mode not in VALID_GIT_MODES:
            raise ValueError(f"Modo Git no válido: {mode}")
        if mode == "dedicated" and p.get("storage") != "folder":
            raise ValueError("El modo Git 'dedicated' requiere una carpeta vinculada.")
        p["git"] = {"mode": mode, "remote_url": (fields["git"].get("remote_url") or "").strip()}
    if "folder" in fields:
        folder = (fields["folder"] or "").strip()
        if folder:
            folder = os.path.abspath(folder)
            try:
                os.makedirs(folder, exist_ok=True)
            except OSError as exc:
                raise ValueError(f"No se pudo usar la carpeta en el servidor: {exc}")
            p["folder"] = folder
            p["storage"] = "folder"
        else:
            p["folder"] = None
            p["storage"] = "virtual"
            if p["git"].get("mode") == "dedicated":
                p["git"]["mode"] = "none"
    p["modified"] = _now()
    save_db(db)
    return p


def delete_project(pid, delete_files=False):
    """Borra el proyecto y sus links. Con `delete_files` borra también la carpeta física."""
    db = load_db()
    p = _get(db, pid)
    if delete_files and p.get("storage") == "folder" and p.get("folder") and os.path.isdir(p["folder"]):
        import shutil
        shutil.rmtree(p["folder"])
    db["projects"] = [x for x in db["projects"] if x["id"] != pid]
    db["links"] = [l for l in db["links"] if l["project_id"] != pid]
    if db["settings"].get("active_project") == pid:
        db["settings"]["active_project"] = None
    save_db(db)
    return True


def set_active_project(pid):
    db = load_db()
    if pid is not None:
        _get(db, pid)
    db["settings"]["active_project"] = pid
    save_db(db)
    return pid


# ----------------------------- subcarpetas -----------------------------
def add_subfolder(pid, name):
    db = load_db()
    p = _get(db, pid)
    name = normalize_rel(name)
    if not name:
        raise ValueError("Nombre de subcarpeta vacío.")
    if name not in p["subfolders"]:
        p["subfolders"].append(name)
        p["subfolders"].sort(key=str.lower)
    if p.get("storage") == "folder":
        os.makedirs(safe_join(p["folder"], *name.split("/")), exist_ok=True)
    p["modified"] = _now()
    save_db(db)
    return p["subfolders"]


def remove_subfolder(pid, name):
    db = load_db()
    p = _get(db, pid)
    name = normalize_rel(name)
    p["subfolders"] = [s for s in p["subfolders"] if s != name]
    # En proyectos virtuales, los links de esa subcarpeta pasan a la raíz del proyecto.
    for l in db["links"]:
        if l["project_id"] == pid and l.get("subfolder") == name:
            l["subfolder"] = ""
    p["modified"] = _now()
    save_db(db)
    return p["subfolders"]


# ----------------------------- vínculos (virtual) -----------------------------
def _ref_links(db, ref):
    ref = normalize_rel(ref)
    return [l for l in db["links"] if normalize_rel(l["workflow_ref"]) == ref]


def link_workflow(project_id, workflow_ref, subfolder="", alias="", allow_multi=False):
    """Vincula un workflow de la raíz general a un proyecto VIRTUAL (etiqueta).

    Por defecto exige exclusividad: si el workflow ya está vinculado (primary) a otro proyecto y
    `allow_multi` es falso, lanza error. Con `allow_multi` añade un link extra (archivo compartido).
    """
    db = load_db()
    p = _get(db, project_id)
    if p.get("storage") == "folder":
        raise ValueError("Para añadir workflows a un proyecto con carpeta, muévelos o duplícalos a su carpeta.")
    workflow_ref = normalize_rel(workflow_ref)
    if not workflows.exists(workflow_ref):
        raise ValueError(f"El workflow no existe en la raíz general: {workflow_ref}")
    subfolder = normalize_rel(subfolder)

    existing = _ref_links(db, workflow_ref)
    primary = [l for l in existing if l.get("primary")]
    if primary and not allow_multi:
        other = _get(db, primary[0]["project_id"])
        raise ValueError(
            f"«{os.path.basename(workflow_ref)}» ya pertenece al proyecto «{other['name']}». "
            "Actívala vinculación múltiple para compartir el MISMO archivo, o duplícalo."
        )
    # Evitar duplicar el mismo link (mismo proyecto + ref).
    for l in existing:
        if l["project_id"] == project_id:
            l["subfolder"] = subfolder
            if alias:
                l["alias"] = alias
            save_db(db)
            return l

    link = {
        "id": _gen_id("l_"),
        "project_id": project_id,
        "subfolder": subfolder,
        "workflow_ref": workflow_ref,
        "alias": alias or "",
        "primary": not bool(existing),  # el primero es el primario
        "created": _now(),
    }
    db["links"].append(link)
    save_db(db)
    return link


def unlink(link_id):
    """Quita un vínculo (no borra el archivo). Reasigna 'primary' si hace falta."""
    db = load_db()
    link = next((l for l in db["links"] if l["id"] == link_id), None)
    if not link:
        raise ValueError("Vínculo desconocido.")
    ref = normalize_rel(link["workflow_ref"])
    was_primary = link.get("primary")
    db["links"] = [l for l in db["links"] if l["id"] != link_id]
    if was_primary:
        rest = _ref_links(db, ref)
        if rest:
            rest[0]["primary"] = True
    save_db(db)
    return True


# ----------------------------- resolución (vista) -----------------------------
def _item_from_abs(abs_path, ref, subfolder, *, storage, link=None, shared=False):
    try:
        st = os.stat(abs_path)
        size, mtime, exists = st.st_size, st.st_mtime, True
    except OSError:
        size, mtime, exists = 0, 0, False
    return {
        "ref": ref,
        "name": os.path.basename(ref),
        "alias": (link or {}).get("alias") or "",
        "subfolder": subfolder or "",
        "abs": abs_path,
        "exists": exists,
        "size": size,
        "mtime": mtime,
        "storage": storage,
        "link_id": (link or {}).get("id"),
        "shared": shared,
        "under_user_root": _under_user_root(abs_path),
    }


def _resolve_project(db, p):
    """Devuelve la lista de workflows de un proyecto (resuelta a disco)."""
    items = []
    subfolders = set(p.get("subfolders") or [])
    if p.get("storage") == "folder" and p.get("folder"):
        root = os.path.abspath(p["folder"])
        meta = {normalize_rel(l["workflow_ref"]): l
                for l in db["links"] if l["project_id"] == p["id"]}
        if os.path.isdir(root):
            tree = workflows.list_tree(root=root)
            for w in tree["workflows"]:
                ref = w["rel"]
                items.append(_item_from_abs(
                    safe_join(root, *ref.split("/")), ref, w["folder"],
                    storage="folder", link=meta.get(ref), shared=False))
            subfolders.update(f for f in tree["folders"] if f)
    else:
        root = workflows.get_root()
        for l in db["links"]:
            if l["project_id"] != p["id"]:
                continue
            ref = normalize_rel(l["workflow_ref"])
            shared = len(_ref_links(db, ref)) > 1
            try:
                abs_path = safe_join(root, *ref.split("/"))
            except ValueError:
                continue
            items.append(_item_from_abs(abs_path, ref, l.get("subfolder", ""),
                                        storage="virtual", link=l, shared=shared))
            if l.get("subfolder"):
                subfolders.add(l["subfolder"])
    items.sort(key=lambda i: ((i["subfolder"] or "").lower(), i["name"].lower()))
    return items, sorted(subfolders, key=str.lower)


def resolve():
    """Vista completa de proyectos resueltos a disco (para la UI)."""
    db = load_db()
    out = []
    for p in db["projects"]:
        items, subfolders = _resolve_project(db, p)
        out.append({
            "id": p["id"],
            "name": p["name"],
            "color": p.get("color", "#AC1F23"),
            "storage": p.get("storage", "virtual"),
            "folder": p.get("folder"),
            "git": p.get("git", {"mode": "none", "remote_url": ""}),
            "notes": p.get("notes", ""),
            "subfolders": subfolders,
            "count": len(items),
            "missing": sum(1 for i in items if not i["exists"]),
            "items": items,
        })
    out.sort(key=lambda p: p["name"].lower())
    return {
        "projects": out,
        "active_project": db["settings"].get("active_project"),
        "workflows_root": workflows.get_root(),
        "user_workflows_root": config.default_workflows_root(),
    }


# ----------------------------- operaciones de archivo (contexto proyecto) -----------------------------
def project_workflow_abs(pid, ref):
    """(abs_path, under_user_root) de un workflow dentro de un proyecto."""
    db = load_db()
    p = _get(db, pid)
    root = _phys_root(p)
    abs_path = safe_join(root, *normalize_rel(ref).split("/"))
    return abs_path, _under_user_root(abs_path)


def project_rename(pid, ref, new_name):
    """Renombra el archivo en disco y, si es virtual, actualiza la ref en todos sus links."""
    db = load_db()
    p = _get(db, pid)
    root = _phys_root(p)
    new_rel = workflows.rename(ref, new_name, root=root)
    if p.get("storage") != "folder":
        old = normalize_rel(ref)
        for l in db["links"]:
            if normalize_rel(l["workflow_ref"]) == old:
                l["workflow_ref"] = new_rel
        save_db(db)
    return new_rel


def project_duplicate(pid, ref, target_pid=None, target_subfolder="", new_name=None):
    """Duplica un workflow (copia independiente) y lo vincula al proyecto destino si procede."""
    db = load_db()
    src_p = _get(db, pid)
    src_root = _phys_root(src_p)
    target_pid = target_pid or pid
    dst_p = _get(db, target_pid)
    target_subfolder = normalize_rel(target_subfolder)

    if dst_p.get("storage") == "folder":
        # La copia vive físicamente en la carpeta destino/subcarpeta.
        data = workflows.read_bytes(ref, root=src_root)
        base = new_name or os.path.basename(ref)
        from .util import ensure_json_ext
        name = ensure_json_ext(base)
        dst_root = _phys_root(dst_p)
        # _unique_name vive en workflows con root; replicamos comportamiento simple:
        new_rel = workflows.write(f"{target_subfolder}/{name}" if target_subfolder else name,
                                  data, overwrite=False, root=dst_root)
        return {"ref": new_rel, "project_id": target_pid}

    # Proyecto destino virtual: la copia vive en la raíz general.
    if src_p.get("storage") == "folder":
        data = workflows.read_bytes(ref, root=src_root)
        from .util import ensure_json_ext
        name = ensure_json_ext(new_name or os.path.basename(ref))
        new_rel = workflows.write(name, data, overwrite=False, root=workflows.get_root())
    else:
        new_rel = workflows.duplicate(ref, dest_folder=None, new_name=new_name,
                                      root=workflows.get_root())
    link = link_workflow(target_pid, new_rel, subfolder=target_subfolder, allow_multi=True)
    return {"ref": new_rel, "project_id": target_pid, "link_id": link["id"]}


def project_move(pid, ref, target_pid, target_subfolder=""):
    """Mueve un workflow de un proyecto a otro (o a otra subcarpeta).

    - virtual → virtual: solo metadatos (cambia el link de proyecto/subcarpeta), el archivo no se mueve.
    - cualquier caso con carpeta física: mueve el archivo de verdad y reconcilia los links.
    """
    db = load_db()
    src_p = _get(db, pid)
    dst_p = _get(db, target_pid)
    target_subfolder = normalize_rel(target_subfolder)
    ref = normalize_rel(ref)

    src_virtual = src_p.get("storage") != "folder"
    dst_virtual = dst_p.get("storage") != "folder"

    if src_virtual and dst_virtual:
        # Pura metadata: localizar el link de este proyecto para esta ref.
        link = next((l for l in db["links"]
                     if l["project_id"] == pid and normalize_rel(l["workflow_ref"]) == ref), None)
        if not link:
            raise ValueError("No se encontró el vínculo a mover.")
        link["project_id"] = target_pid
        link["subfolder"] = target_subfolder
        save_db(db)
        return {"ref": ref, "project_id": target_pid, "moved_file": False}

    # Hay una carpeta física implicada: mover el archivo.
    src_root = _phys_root(src_p)
    if dst_virtual:
        # Al volver a un proyecto virtual, el archivo regresa a la raíz general (nivel superior);
        # la subcarpeta destino es solo una etiqueta lógica del link.
        new_rel = _move_cross(src_root, ref, workflows.get_root(), "")
    else:
        new_rel = _move_cross(src_root, ref, _phys_root(dst_p), target_subfolder)

    # Reconciliar links que apuntaban al archivo movido.
    if src_virtual:
        for l in db["links"]:
            if l["project_id"] == pid and normalize_rel(l["workflow_ref"]) == ref:
                db["links"].remove(l)
                break
    if dst_virtual:
        db["links"].append({
            "id": _gen_id("l_"), "project_id": target_pid, "subfolder": target_subfolder,
            "workflow_ref": new_rel, "alias": "", "primary": True, "created": _now(),
        })
    save_db(db)
    return {"ref": new_rel, "project_id": target_pid, "moved_file": True}


def _move_cross(src_root, ref, dst_root, dst_subfolder):
    """Mueve un archivo entre dos raíces distintas. Devuelve la nueva ref (relativa a dst_root)."""
    import shutil
    from .util import ensure_json_ext
    src = safe_join(src_root, *normalize_rel(ref).split("/"))
    if not os.path.isfile(src):
        raise ValueError(f"El workflow no existe: {ref}")
    name = ensure_json_ext(os.path.basename(ref))
    new_rel = f"{dst_subfolder}/{name}" if dst_subfolder else name
    dst = safe_join(dst_root, *new_rel.split("/"))
    if os.path.exists(dst):
        raise ValueError(f"Ya existe un workflow en el destino: {new_rel}")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.move(src, dst)
    return new_rel


def project_delete_file(pid, ref):
    """Borra el archivo en disco y elimina todos los links que lo referenciaban."""
    db = load_db()
    p = _get(db, pid)
    root = _phys_root(p)
    workflows.delete(ref, root=root)
    if p.get("storage") != "folder":
        old = normalize_rel(ref)
        db["links"] = [l for l in db["links"] if normalize_rel(l["workflow_ref"]) != old]
        save_db(db)
    return True


def save_canvas(pid, name, content, subfolder="", overwrite=False):
    """Guarda el grafo actual (content) en la carpeta física del proyecto.

    En proyectos virtuales escribe en la raíz general y crea/actualiza el vínculo; en proyectos con
    carpeta, escribe dentro de su carpeta. Devuelve {ref}.
    """
    from .util import ensure_json_ext
    db = load_db()
    p = _get(db, pid)
    name = ensure_json_ext(name)
    sub = normalize_rel(subfolder)
    rel = f"{sub}/{name}" if sub else name
    root = _phys_root(p)
    new_rel = workflows.write(rel, content, overwrite=overwrite, root=root)
    if p.get("storage") != "folder":
        link_workflow(pid, new_rel, subfolder=sub, allow_multi=True)
    return {"ref": new_rel}


def add_current_to_project(pid, rel, subfolder="", alias="", allow_multi=False):
    """Atajo: vincular un workflow (de la raíz general) a un proyecto, o copiarlo si es de carpeta."""
    db = load_db()
    p = _get(db, pid)
    if p.get("storage") == "folder":
        data = workflows.read_bytes(rel, root=workflows.get_root())
        from .util import ensure_json_ext
        name = ensure_json_ext(os.path.basename(rel))
        sub = normalize_rel(subfolder)
        new_rel = workflows.write(f"{sub}/{name}" if sub else name, data,
                                  overwrite=False, root=_phys_root(p))
        return {"ref": new_rel, "copied": True}
    link = link_workflow(pid, rel, subfolder=subfolder, alias=alias, allow_multi=allow_multi)
    return {"link_id": link["id"], "copied": False}
