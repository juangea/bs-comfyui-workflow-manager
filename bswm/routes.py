# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Rutas HTTP registradas en el PromptServer de ComfyUI (aiohttp).

Sirve la mini-app web (en `webapp/`) y expone la API JSON del gestor de workflows: vista general
(FS), proyectos (BD), exportación a .zip, integración Git e import/export de la base de datos.
Todas las rutas cuelgan del prefijo `/bs_workflow_manager`.

Nota: el módulo top-level `server` es el de ComfyUI (PromptServer). Nuestro paquete se llama `bswm`
precisamente para no ensombrecerlo.
"""
import json
import logging
import mimetypes
import os

from aiohttp import web
from server import PromptServer

# Asegura el content-type correcto al servir las fuentes (.woff2).
mimetypes.add_type("font/woff2", ".woff2")

from . import config, git_ops, projects, workflows
from .exporter import manager as export_manager
from .util import normalize_rel, safe_join

log = logging.getLogger("BS_Workflow_Manager")

PREFIX = "/bs_workflow_manager"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBAPP_DIR = os.path.join(PROJECT_ROOT, "webapp")

routes = PromptServer.instance.routes


# ----------------------------- helpers -----------------------------
def _err(message, status=400):
    return web.json_response({"error": str(message)}, status=status)


async def _body(request):
    try:
        return await request.json()
    except Exception:
        return {}


def _json_file_response(abs_path, download_name=None):
    """Sirve un workflow .json (inline para abrir, o como adjunto para descargar)."""
    if not os.path.isfile(abs_path):
        return _err("El workflow no existe.", 404)
    with open(abs_path, "rb") as fh:
        data = fh.read()
    headers = {}
    if download_name:
        headers["Content-Disposition"] = f'attachment; filename="{download_name}"'
    return web.Response(body=data, content_type="application/json", headers=headers)


def _resolve_repo(spec):
    """Convierte un 'repo spec' (studio | <project_id>) en una ruta de repo Git."""
    if not spec or spec == "studio":
        return workflows.get_root()
    db = projects.load_db()
    try:
        p = projects._get(db, spec)
    except ValueError:
        return workflows.get_root()
    if p.get("storage") == "folder" and p.get("folder"):
        return os.path.abspath(p["folder"])
    return workflows.get_root()


# ----------------------------- API: config / meta -----------------------------
@routes.get(PREFIX + "/api/config")
async def api_config(request):
    try:
        root = workflows.get_root()
        comfy_root = config.default_workflows_root()
        is_default = os.path.normcase(os.path.abspath(root)) == os.path.normcase(os.path.abspath(comfy_root))
        return web.json_response({
            "workflows_root": root,
            "user_workflows_root": comfy_root,
            "is_default_root": is_default,
            "db_path": config.get_db_path(),
            "git": git_ops.detect(),
        })
    except Exception as exc:
        log.exception("api/config")
        return _err(exc, 500)


@routes.post(PREFIX + "/api/config/root")
async def api_config_root(request):
    data = await _body(request)
    try:
        config.set_workflows_root(data.get("path"))
        return web.json_response({"ok": True, "workflows_root": workflows.get_root()})
    except ValueError as exc:
        return _err(exc, 400)


@routes.post(PREFIX + "/api/config/db")
async def api_config_db(request):
    data = await _body(request)
    config.set_db_path(data.get("path"))
    return web.json_response({"ok": True, "db_path": config.get_db_path()})


# ----------------------------- API: workflows (general) -----------------------------
@routes.get(PREFIX + "/api/workflows/list")
async def api_workflows_list(request):
    try:
        tree = workflows.list_tree()
        tree["under_user_root"] = os.path.normcase(tree["root"]).startswith(
            os.path.normcase(config.default_workflows_root()))
        return web.json_response(tree)
    except Exception as exc:
        log.exception("api/workflows/list")
        return _err(exc, 500)


@routes.get(PREFIX + "/api/workflows/content")
async def api_workflows_content(request):
    rel = request.rel_url.query.get("rel", "")
    download = request.rel_url.query.get("download", "") == "1"
    try:
        abs_path = workflows.abs_path(rel)
    except ValueError as exc:
        return _err(exc, 400)
    return _json_file_response(abs_path, os.path.basename(rel) if download else None)


@routes.get(PREFIX + "/api/workflows/inspect")
async def api_workflows_inspect(request):
    """Metadatos ligeros de un workflow: nº de nodos y modelos declarados (best-effort)."""
    rel = request.rel_url.query.get("rel", "")
    try:
        data = json.loads(workflows.read_bytes(rel).decode("utf-8"))
    except Exception as exc:
        return _err(f"No se pudo leer el workflow: {exc}", 400)
    nodes = data.get("nodes") if isinstance(data, dict) else None
    node_count = len(nodes) if isinstance(nodes, list) else 0
    models = []
    seen = set()
    if isinstance(nodes, list):
        for n in nodes:
            props = (n or {}).get("properties") or {}
            for m in (props.get("models") or []):
                key = (m.get("name"), m.get("url"))
                if m.get("name") and key not in seen:
                    seen.add(key)
                    models.append({"name": m.get("name"), "directory": m.get("directory", "")})
    return web.json_response({"nodes": node_count, "models": models})


@routes.post(PREFIX + "/api/workflows/mkdir")
async def api_workflows_mkdir(request):
    data = await _body(request)
    try:
        folder = workflows.mkdir(data.get("folder", ""))
        return web.json_response({"ok": True, "folder": folder})
    except ValueError as exc:
        return _err(exc, 400)


@routes.post(PREFIX + "/api/workflows/rename")
async def api_workflows_rename(request):
    data = await _body(request)
    try:
        rel = workflows.rename(data.get("rel"), data.get("new_name"))
        return web.json_response({"ok": True, "rel": rel})
    except ValueError as exc:
        return _err(exc, 400)


@routes.post(PREFIX + "/api/workflows/move")
async def api_workflows_move(request):
    data = await _body(request)
    try:
        rel = workflows.move(data.get("rel"), data.get("dest_folder", ""))
        return web.json_response({"ok": True, "rel": rel})
    except ValueError as exc:
        return _err(exc, 400)


@routes.post(PREFIX + "/api/workflows/duplicate")
async def api_workflows_duplicate(request):
    data = await _body(request)
    try:
        rel = workflows.duplicate(data.get("rel"), data.get("dest_folder"), data.get("new_name"))
        return web.json_response({"ok": True, "rel": rel})
    except ValueError as exc:
        return _err(exc, 400)


@routes.post(PREFIX + "/api/workflows/delete")
async def api_workflows_delete(request):
    data = await _body(request)
    try:
        workflows.delete(data.get("rel"))
        return web.json_response({"ok": True})
    except ValueError as exc:
        return _err(exc, 400)


@routes.post(PREFIX + "/api/workflows/delete-folder")
async def api_workflows_delete_folder(request):
    data = await _body(request)
    try:
        workflows.delete_folder(data.get("folder"))
        return web.json_response({"ok": True})
    except ValueError as exc:
        return _err(exc, 400)


@routes.post(PREFIX + "/api/workflows/rename-folder")
async def api_workflows_rename_folder(request):
    data = await _body(request)
    try:
        folder = workflows.rename_folder(data.get("folder"), data.get("new_name"))
        return web.json_response({"ok": True, "folder": folder})
    except ValueError as exc:
        return _err(exc, 400)


# ----------------------------- API: traspaso desde ComfyUI -----------------------------
@routes.get(PREFIX + "/api/comfy/list")
async def api_comfy_list(request):
    """Lista los workflows de usuario de la carpeta nativa de ComfyUI (para traspasar a la nuestra)."""
    comfy_root = config.default_workflows_root()
    our_root = workflows.get_root()
    same = os.path.normcase(os.path.abspath(comfy_root)) == os.path.normcase(os.path.abspath(our_root))
    try:
        tree = workflows.list_tree(root=comfy_root) if os.path.isdir(comfy_root) else {"workflows": []}
    except Exception as exc:
        log.exception("api/comfy/list")
        return _err(exc, 500)
    return web.json_response({
        "comfy_root": comfy_root,
        "same_as_root": same,
        "workflows": tree["workflows"],
    })


@routes.post(PREFIX + "/api/comfy/transfer")
async def api_comfy_transfer(request):
    data = await _body(request)
    refs = data.get("refs") or []
    if not refs:
        return _err("No se ha seleccionado ningún workflow.", 400)
    try:
        res = workflows.transfer_from(
            config.default_workflows_root(), refs,
            dest_folder=data.get("dest_folder", ""), move=bool(data.get("move")),
        )
        return web.json_response({"ok": True, **res})
    except ValueError as exc:
        return _err(exc, 400)


@routes.post(PREFIX + "/api/workflows/import")
async def api_workflows_import(request):
    data = await _body(request)
    content = data.get("content")
    rel = data.get("rel") or data.get("name")
    if content is None or not rel:
        return _err("Faltan 'rel'/'name' o 'content'.", 400)
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False)
    try:
        rel = workflows.write(rel, content, overwrite=bool(data.get("overwrite")))
        return web.json_response({"ok": True, "rel": rel})
    except ValueError as exc:
        return _err(exc, 400)


# ----------------------------- API: proyectos -----------------------------
@routes.get(PREFIX + "/api/projects")
async def api_projects(request):
    try:
        return web.json_response(projects.resolve())
    except Exception as exc:
        log.exception("api/projects")
        return _err(exc, 500)


@routes.post(PREFIX + "/api/projects/create")
async def api_projects_create(request):
    data = await _body(request)
    try:
        p = projects.create_project(
            name=data.get("name"), color=data.get("color", "#AC1F23"),
            storage=data.get("storage", "virtual"), folder=data.get("folder"),
            git=data.get("git"), notes=data.get("notes", ""),
            subfolders=data.get("subfolders"),
        )
        return web.json_response({"ok": True, "project": p})
    except ValueError as exc:
        return _err(exc, 400)


@routes.post(PREFIX + "/api/projects/update")
async def api_projects_update(request):
    data = await _body(request)
    pid = data.pop("id", None)
    if not pid:
        return _err("Falta el id del proyecto.", 400)
    try:
        p = projects.update_project(pid, **data)
        return web.json_response({"ok": True, "project": p})
    except ValueError as exc:
        return _err(exc, 400)


@routes.post(PREFIX + "/api/projects/delete")
async def api_projects_delete(request):
    data = await _body(request)
    try:
        projects.delete_project(data.get("id"), delete_files=bool(data.get("delete_files")))
        return web.json_response({"ok": True})
    except ValueError as exc:
        return _err(exc, 400)


@routes.post(PREFIX + "/api/projects/active")
async def api_projects_active(request):
    data = await _body(request)
    try:
        pid = projects.set_active_project(data.get("id"))
        return web.json_response({"ok": True, "active_project": pid})
    except ValueError as exc:
        return _err(exc, 400)


@routes.post(PREFIX + "/api/projects/subfolder/add")
async def api_projects_subfolder_add(request):
    data = await _body(request)
    try:
        subs = projects.add_subfolder(data.get("id"), data.get("name"))
        return web.json_response({"ok": True, "subfolders": subs})
    except ValueError as exc:
        return _err(exc, 400)


@routes.post(PREFIX + "/api/projects/subfolder/remove")
async def api_projects_subfolder_remove(request):
    data = await _body(request)
    try:
        subs = projects.remove_subfolder(data.get("id"), data.get("name"))
        return web.json_response({"ok": True, "subfolders": subs})
    except ValueError as exc:
        return _err(exc, 400)


@routes.post(PREFIX + "/api/projects/link")
async def api_projects_link(request):
    data = await _body(request)
    try:
        link = projects.link_workflow(
            data.get("project_id"), data.get("workflow_ref"),
            subfolder=data.get("subfolder", ""), alias=data.get("alias", ""),
            allow_multi=bool(data.get("allow_multi")),
        )
        return web.json_response({"ok": True, "link": link})
    except ValueError as exc:
        return _err(exc, 400)


@routes.post(PREFIX + "/api/projects/unlink")
async def api_projects_unlink(request):
    data = await _body(request)
    try:
        projects.unlink(data.get("link_id"))
        return web.json_response({"ok": True})
    except ValueError as exc:
        return _err(exc, 400)


@routes.post(PREFIX + "/api/projects/move")
async def api_projects_move(request):
    data = await _body(request)
    try:
        res = projects.project_move(
            data.get("pid"), data.get("ref"),
            data.get("target_pid"), data.get("target_subfolder", ""),
        )
        return web.json_response({"ok": True, **res})
    except ValueError as exc:
        return _err(exc, 400)


@routes.post(PREFIX + "/api/projects/rename")
async def api_projects_rename(request):
    data = await _body(request)
    try:
        rel = projects.project_rename(data.get("pid"), data.get("ref"), data.get("new_name"))
        return web.json_response({"ok": True, "ref": rel})
    except ValueError as exc:
        return _err(exc, 400)


@routes.post(PREFIX + "/api/projects/duplicate")
async def api_projects_duplicate(request):
    data = await _body(request)
    try:
        res = projects.project_duplicate(
            data.get("pid"), data.get("ref"),
            target_pid=data.get("target_pid"),
            target_subfolder=data.get("target_subfolder", ""),
            new_name=data.get("new_name"),
        )
        return web.json_response({"ok": True, **res})
    except ValueError as exc:
        return _err(exc, 400)


@routes.post(PREFIX + "/api/projects/delete-file")
async def api_projects_delete_file(request):
    data = await _body(request)
    try:
        projects.project_delete_file(data.get("pid"), data.get("ref"))
        return web.json_response({"ok": True})
    except ValueError as exc:
        return _err(exc, 400)


@routes.post(PREFIX + "/api/projects/add-current")
async def api_projects_add_current(request):
    data = await _body(request)
    try:
        res = projects.add_current_to_project(
            data.get("pid"), data.get("rel"), subfolder=data.get("subfolder", ""),
            alias=data.get("alias", ""), allow_multi=bool(data.get("allow_multi")),
        )
        return web.json_response({"ok": True, **res})
    except ValueError as exc:
        return _err(exc, 400)


@routes.post(PREFIX + "/api/projects/save-canvas")
async def api_projects_save_canvas(request):
    data = await _body(request)
    content = data.get("content")
    if content is None or not data.get("name"):
        return _err("Faltan 'name' o 'content'.", 400)
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False)
    try:
        res = projects.save_canvas(
            data.get("pid"), data.get("name"), content,
            subfolder=data.get("subfolder", ""), overwrite=bool(data.get("overwrite")),
        )
        return web.json_response({"ok": True, **res})
    except ValueError as exc:
        return _err(exc, 400)


@routes.get(PREFIX + "/api/projects/content")
async def api_projects_content(request):
    pid = request.rel_url.query.get("pid", "")
    ref = request.rel_url.query.get("ref", "")
    download = request.rel_url.query.get("download", "") == "1"
    try:
        abs_path, _ = projects.project_workflow_abs(pid, ref)
    except ValueError as exc:
        return _err(exc, 400)
    return _json_file_response(abs_path, os.path.basename(ref) if download else None)


# ----------------------------- API: exportación -----------------------------
def _export_files_for(data):
    """Construye la lista (abs_path, arcname) para un job de exportación según el modo."""
    mode = data.get("mode")
    files = []
    name = "workflows"
    if mode == "general_selection":
        for rel in (data.get("refs") or []):
            rel = normalize_rel(rel)
            files.append((workflows.abs_path(rel), rel))
        name = "workflows"
    elif mode == "general_folder":
        folder = normalize_rel(data.get("folder", ""))
        root = workflows.get_root()
        base = safe_join(root, *folder.split("/")) if folder else root
        for w in workflows.list_tree(root=base)["workflows"]:
            files.append((os.path.join(base, *w["rel"].split("/")), w["rel"]))
        name = folder.replace("/", "_") or "workflows"
    elif mode == "project_selection":
        pid = data.get("pid")
        db = projects.load_db()
        p = projects._get(db, pid)
        name = p["name"]
        for ref in (data.get("refs") or []):
            abs_path, _ = projects.project_workflow_abs(pid, ref)
            files.append((abs_path, f"{name}/{normalize_rel(ref)}"))
    elif mode in ("project", "project_subfolder"):
        sub = normalize_rel(data.get("subfolder", "")) if mode == "project_subfolder" else None
        for proj in projects.resolve()["projects"]:
            if proj["id"] != data.get("pid"):
                continue
            name = proj["name"]
            for item in proj["items"]:
                if not item["exists"]:
                    continue
                if sub is not None and item["subfolder"] != sub:
                    continue
                arc = f"{item['subfolder']}/{item['name']}" if item["subfolder"] else item["name"]
                files.append((item["abs"], f"{name}/{arc}"))
            break
    else:
        raise ValueError(f"Modo de exportación no válido: {mode}")
    return name, files


@routes.post(PREFIX + "/api/export")
async def api_export(request):
    data = await _body(request)
    try:
        name, files = _export_files_for(data)
        if not files:
            return _err("No hay workflows que exportar.", 400)
        jid = export_manager.enqueue(name, files)
        return web.json_response({"ok": True, "job": jid})
    except ValueError as exc:
        return _err(exc, 400)


@routes.get(PREFIX + "/api/export/status")
async def api_export_status(request):
    return web.json_response({"jobs": export_manager.status()})


@routes.get(PREFIX + "/api/export/download")
async def api_export_download(request):
    jid = request.rel_url.query.get("id", "")
    job = export_manager.get(jid)
    if not job or job.state != "done" or not job.zip_path or not os.path.isfile(job.zip_path):
        return _err("El archivo no está listo.", 404)
    return web.FileResponse(job.zip_path, headers={
        "Content-Disposition": f'attachment; filename="{os.path.basename(job.zip_path)}"'})


@routes.post(PREFIX + "/api/export/clear")
async def api_export_clear(request):
    export_manager.clear_finished()
    return web.json_response({"ok": True})


# ----------------------------- API: base de datos (import/export) -----------------------------
@routes.get(PREFIX + "/api/db/export")
async def api_db_export(request):
    body = json.dumps(projects.export_db(), ensure_ascii=False, indent=2).encode("utf-8")
    return web.Response(body=body, content_type="application/json", headers={
        "Content-Disposition": 'attachment; filename="bswm_projects.json"'})


@routes.post(PREFIX + "/api/db/import")
async def api_db_import(request):
    data = await _body(request)
    payload = data.get("data")
    if payload is None:
        return _err("Falta 'data'.", 400)
    try:
        projects.import_db(payload, merge=bool(data.get("merge")))
        return web.json_response({"ok": True})
    except ValueError as exc:
        return _err(exc, 400)


# ----------------------------- API: Git -----------------------------
@routes.get(PREFIX + "/api/git/detect")
async def api_git_detect(request):
    return web.json_response(git_ops.detect())


def _is_comfy_default(repo):
    return os.path.normcase(os.path.abspath(repo)) == os.path.normcase(os.path.abspath(config.default_workflows_root()))


@routes.get(PREFIX + "/api/git/info")
async def api_git_info(request):
    repo = _resolve_repo(request.rel_url.query.get("repo", "studio"))
    info = git_ops.info(repo)
    # Bloqueamos Git si la carpeta es la propia de ComfyUI (por seguridad) o cuelga de su repo.
    info["is_comfy_default"] = _is_comfy_default(repo)
    info["git_blocked"] = bool(info.get("foreign") or info["is_comfy_default"])
    return web.json_response(info)


@routes.get(PREFIX + "/api/git/log")
async def api_git_log(request):
    repo = _resolve_repo(request.rel_url.query.get("repo", "studio"))
    n = int(request.rel_url.query.get("n", "50") or 50)
    path = request.rel_url.query.get("path") or None
    return web.json_response({"log": git_ops.log(repo, n=n, path=path)})


@routes.post(PREFIX + "/api/git/run")
async def api_git_run(request):
    data = await _body(request)
    kind = data.get("kind")
    if not kind:
        return _err("Falta 'kind'.", 400)
    det = git_ops.detect()
    if not det["git"]["available"]:
        return _err("git no está instalado en el sistema.", 400)
    repo = _resolve_repo(data.get("repo", "studio"))
    # Seguridad: nunca operar sobre la carpeta propia de ComfyUI ni dentro de su repositorio.
    if kind != "clone" and (git_ops.is_foreign(repo) or _is_comfy_default(repo)):
        return _err(
            "Esta carpeta es la de ComfyUI o cuelga de su repositorio Git. Git está desactivado "
            "para no entrar en conflicto. Define una carpeta de workflows propia en Ajustes.", 400)
    opts = {k: v for k, v in data.items() if k not in ("kind", "repo")}
    jid = git_ops.manager.enqueue(kind, repo, label=kind, **opts)
    return web.json_response({"ok": True, "job": jid})


@routes.get(PREFIX + "/api/git/jobs")
async def api_git_jobs(request):
    return web.json_response({"jobs": git_ops.manager.status()})


@routes.post(PREFIX + "/api/git/clear")
async def api_git_clear(request):
    git_ops.manager.clear_finished()
    return web.json_response({"ok": True})


# ----------------------------- estáticos (mini-app) -----------------------------
# IMPORTANTE: registrar DESPUÉS de las rutas /api para que estas tengan prioridad.
def _serve_static(tail):
    tail = tail or "index.html"
    if tail.endswith("/"):
        tail += "index.html"
    try:
        full = safe_join(WEBAPP_DIR, *[p for p in tail.split("/") if p])
    except ValueError:
        return web.Response(status=403, text="forbidden")
    if not os.path.isfile(full):
        return web.Response(status=404, text="not found")
    return web.FileResponse(full)


@routes.get(PREFIX)
async def app_root_noslash(request):
    raise web.HTTPFound(PREFIX + "/")


@routes.get(PREFIX + "/{tail:.*}")
async def app_static(request):
    return _serve_static(request.match_info.get("tail", ""))


log.info("[BS Workflow Manager] rutas registradas en %s", PREFIX)
