# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Rutas HTTP registradas en el PromptServer de ComfyUI (aiohttp).

Sirve la mini-app web (en `webapp/`) y expone su API JSON. Todas las rutas cuelgan del prefijo
`/bs_workflow_manager`.

Nota: el módulo top-level `server` es el de ComfyUI (PromptServer). Nuestro paquete se llama `bswm`
precisamente para no ensombrecerlo.
"""
import asyncio
import functools
import json
import logging
import mimetypes
import os
from urllib.parse import quote

from aiohttp import web
from server import PromptServer

# Asegura el content-type correcto al servir las fuentes (.woff2).
mimetypes.add_type("font/woff2", ".woff2")

from . import config, fsbrowse, git_ops, projects, workflows
from .exporter import manager as export_manager
from .util import UserError, normalize_rel, safe_join

log = logging.getLogger("BS_Workflow_Manager")

PREFIX = "/bs_workflow_manager"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBAPP_DIR = os.path.join(PROJECT_ROOT, "webapp")

routes = PromptServer.instance.routes


# ----------------------------- helpers -----------------------------
def _ok(**data):
    return web.json_response({"ok": True, **data})


def _bind_user(request):
    """Usa el usuario de ComfyUI de la petición (relevante con --multi-user)."""
    manager = getattr(PromptServer.instance, "user_manager", None)
    if manager is None:
        return
    try:
        config.set_request_user(manager.get_request_user_id(request))
    except KeyError:
        raise UserError("unknown_user")


def _api(handler):
    """Vincula el usuario y convierte errores en respuestas JSON con código traducible."""
    @functools.wraps(handler)
    async def wrapper(request):
        try:
            _bind_user(request)
            return await handler(request)
        except UserError as exc:
            return web.json_response({"error": str(exc), "code": exc.code, "params": exc.params}, status=400)
        except OSError as exc:
            log.warning("%s: %s", request.path, exc)
            return web.json_response({"error": str(exc)}, status=400)
        except web.HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception(request.path)
            return web.json_response({"error": str(exc)}, status=500)
    return wrapper


def get(path):
    return lambda fn: routes.get(PREFIX + "/api" + path)(_api(fn))


def post(path):
    return lambda fn: routes.post(PREFIX + "/api" + path)(_api(fn))


async def _body(request):
    # Exigir JSON obliga a un preflight CORS: otra web no puede lanzar estas operaciones a ciegas.
    if request.content_type != "application/json":
        raise web.HTTPUnsupportedMediaType(text="application/json required")
    try:
        data = await request.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _query(request, name, default=""):
    return request.rel_url.query.get(name, default)


def _attachment(name):
    return {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name, errors='replace')}"}


def _git_protected():
    return [workflows.get_root(), config.comfy_code_dir()]


def _content_text(content):
    return content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)


# ----------------------------- estado -----------------------------
@get("/config")
async def api_config(request):
    return web.json_response({"comfy_root": workflows.get_root(), "db_path": config.get_db_path(),
                              "git": await asyncio.to_thread(git_ops.detect)})


@get("/tree")
async def api_tree(request):
    return web.json_response(projects.tree())


# ----------------------------- explorador de carpetas del servidor -----------------------------
@get("/fs/list")
async def api_fs_list(request):
    return web.json_response(fsbrowse.list_dir(_query(request, "path")))


@post("/fs/mkdir")
async def api_fs_mkdir(request):
    data = await _body(request)
    return _ok(path=fsbrowse.mkdir(data.get("path"), data.get("name")))


# ----------------------------- workflows -----------------------------
@get("/workflow/download")
async def api_workflow_download(request):
    path = projects.source_file(_query(request, "path"))
    with open(path, "rb") as fh:
        body = fh.read()
    return web.Response(body=body, content_type="application/json",
                        headers=_attachment(os.path.basename(path)))


@post("/workflow/prepare-open")
async def api_prepare_open(request):
    return _ok(path=projects.prepare_open((await _body(request)).get("path")))


@post("/workflow/rename")
async def api_workflow_rename(request):
    data = await _body(request)
    return _ok(**projects.rename_item(data.get("path"), data.get("new_name"), bool(data.get("dry_run")),
                                      bool(data.get("general_moved"))))


@post("/workflow/move")
async def api_workflow_move(request):
    data = await _body(request)
    return _ok(**projects.move_item(data.get("path"), data.get("from_project"), data.get("to_project"),
                                    data.get("folder", ""), bool(data.get("dry_run")),
                                    bool(data.get("general_moved")), bool(data.get("exclusive"))))


@post("/workflow/add-to-project")
async def api_workflow_add(request):
    data = await _body(request)
    return _ok(**projects.add_to_project(data.get("path"), data.get("project"), data.get("folder", ""),
                                         bool(data.get("allow_multi")), bool(data.get("dry_run")),
                                         bool(data.get("general_moved"))))


@post("/workflow/undo-move")
async def api_workflow_undo_move(request):
    data = await _body(request)
    return _ok(**projects.undo_move(data.get("old"), data.get("new"), data.get("links"), data.get("copied"),
                                    data.get("copied_mtime"), bool(data.get("dry_run")),
                                    bool(data.get("general_moved"))))


@post("/workflow/check-free")
async def api_workflow_check_free(request):
    projects.check_free((await _body(request)).get("path"))
    return _ok()


@post("/workflow/remove-from-project")
async def api_workflow_unlink(request):
    data = await _body(request)
    projects.unlink(data.get("project"), data.get("path"))
    return _ok()


@post("/workflow/duplicate")
async def api_workflow_duplicate(request):
    data = await _body(request)
    return _ok(path=projects.duplicate_item(data.get("path"), data.get("project"), data.get("folder"),
                                            data.get("new_name")))


@post("/workflow/delete")
async def api_workflow_delete(request):
    projects.delete_item((await _body(request)).get("path"))
    return _ok()


@post("/workflow/import")
async def api_workflow_import(request):
    """Importa un .json a una carpeta de Workflows o a un proyecto."""
    data = await _body(request)
    content = data.get("content")
    if content is None:
        raise UserError("missing_field", field="content")
    return _ok(path=projects.import_workflow(data.get("name"), _content_text(content), data.get("project"),
                                             data.get("folder", "")))


# ----------------------------- eventos de ComfyUI (Guardar, renombrar, borrar) -----------------------------
@post("/events/saved")
async def api_event_saved(request):
    data = await _body(request)
    name, conflict = projects.mirror_saved(data.get("path"), bool(data.get("created")), data.get("previous"),
                                           data.get("base"))
    return _ok(mirrored=name, conflict=conflict)


@post("/events/renamed")
async def api_event_renamed(request):
    data = await _body(request)
    projects.on_renamed(data.get("old"), data.get("new"))
    return _ok()


@post("/events/deleted")
async def api_event_deleted(request):
    projects.on_deleted((await _body(request)).get("path"))
    return _ok()


# ----------------------------- carpetas de Workflows -----------------------------
@post("/folder/create")
async def api_folder_create(request):
    return _ok(folder=projects.create_general_folder((await _body(request)).get("folder", "")))


@post("/folder/move")
async def api_folder_move(request):
    data = await _body(request)
    return _ok(folder=projects.rename_general_folder(data.get("folder"), data.get("new_folder")))


@post("/folder/delete")
async def api_folder_delete(request):
    return _ok(**projects.delete_general_folder((await _body(request)).get("folder")))


# ----------------------------- proyectos -----------------------------
@post("/project/create")
async def api_project_create(request):
    data = await _body(request)
    return _ok(project=projects.create_project(
        data.get("name"), color=data.get("color"), folder=data.get("folder"), notes=data.get("notes", "")))


@post("/project/update")
async def api_project_update(request):
    data = await _body(request)
    return _ok(project=projects.update_project(
        data.get("id"), name=data.get("name"), color=data.get("color"), notes=data.get("notes"),
        folder=data.get("folder")))


@post("/project/delete")
async def api_project_delete(request):
    data = await _body(request)
    projects.delete_project(data.get("id"), delete_files=bool(data.get("delete_files")))
    return _ok()


@post("/project/subfolder/add")
async def api_subfolder_add(request):
    data = await _body(request)
    return _ok(folder=projects.add_subfolder(data.get("id"), data.get("name")))


@post("/project/subfolder/rename")
async def api_subfolder_rename(request):
    data = await _body(request)
    return _ok(folder=projects.rename_subfolder(data.get("id"), data.get("old"), data.get("new")))


@post("/project/subfolder/remove")
async def api_subfolder_remove(request):
    data = await _body(request)
    projects.remove_subfolder(data.get("id"), data.get("name"))
    return _ok()


# ----------------------------- exportación -----------------------------
def _export_files(data):
    """Construye (nombre, [(abs_path, arcname)]) para un job de exportación."""
    pid = data.get("project")
    if pid:
        return projects.project_export_files(pid, normalize_rel(data["folder"]) if data.get("folder") else None)
    folder = data.get("folder")
    if folder is not None:
        folder = normalize_rel(folder)
        root = workflows.get_root()
        base = safe_join(root, *folder.split("/")) if folder else root
        files = [(os.path.join(base, *w["rel"].split("/")), w["rel"])
                 for w in workflows.list_tree(root=base)["workflows"]]
        return folder.replace("/", "_") or "workflows", files
    files = []
    for path in data.get("paths") or []:
        rel = normalize_rel(path)
        files.append((projects.source_file(rel), rel))
    return str(data.get("name") or "workflows"), files


@post("/export")
async def api_export(request):
    name, files = _export_files(await _body(request))
    if not files:
        raise UserError("nothing_to_export")
    return _ok(job=export_manager.enqueue(name, files, config.current_user()))


@get("/export/status")
async def api_export_status(request):
    return web.json_response({"jobs": export_manager.status(config.current_user())})


@get("/export/download")
async def api_export_download(request):
    job = export_manager.get(_query(request, "id"), config.current_user())
    if not job or job.state != "done" or not job.zip_path or not os.path.isfile(job.zip_path):
        raise UserError("export_not_ready")
    return web.FileResponse(job.zip_path, headers=_attachment(f"{job.name}.zip"))


@post("/export/clear")
async def api_export_clear(request):
    export_manager.clear_finished(config.current_user())
    return _ok()


# ----------------------------- base de datos (import/export) -----------------------------
@get("/db/export")
async def api_db_export(request):
    body = json.dumps(projects.export_db(), ensure_ascii=False, indent=2).encode("utf-8", "backslashreplace")
    return web.Response(body=body, content_type="application/json", headers=_attachment("bswm_projects.json"))


@post("/db/import")
async def api_db_import(request):
    data = await _body(request)
    if data.get("data") is None:
        raise UserError("missing_field", field="data")
    projects.import_db(data["data"], merge=bool(data.get("merge")))
    return _ok()


# ----------------------------- Git -----------------------------
@get("/git/detect")
async def api_git_detect(request):
    return web.json_response(await asyncio.to_thread(git_ops.detect))


@get("/git/info")
async def api_git_info(request):
    folder = projects.git_folder(_query(request, "project"))
    return web.json_response(await asyncio.to_thread(git_ops.info, folder, _git_protected()))


@get("/git/log")
async def api_git_log(request):
    folder = projects.git_folder(_query(request, "project"))
    if await asyncio.to_thread(git_ops.is_blocked, folder, _git_protected()):
        return web.json_response({"log": []})
    try:
        n = int(_query(request, "n", "50"))
    except ValueError:
        n = 50
    return web.json_response({"log": await asyncio.to_thread(git_ops.log, folder, n=n)})


@post("/git/run")
async def api_git_run(request):
    data = await _body(request)
    pid = data.get("project")
    folder = projects.git_folder(pid)
    if not (await asyncio.to_thread(git_ops.detect))["git"]["available"]:
        raise UserError("git_missing")
    # Seguridad: nunca operar sobre la carpeta de ComfyUI ni dentro de su repositorio.
    if await asyncio.to_thread(git_ops.is_blocked, folder, _git_protected()):
        raise UserError("git_blocked")
    kind = data.get("kind")
    opts = {k: data[k] for k in ("message", "url", "commit", "name", "private") if k in data}
    jid = git_ops.manager.enqueue(kind, folder, owner=config.current_user(), **opts)
    if kind == "remote":
        projects.set_remote(pid, opts.get("url", ""))
    return _ok(job=jid)


@get("/git/jobs")
async def api_git_jobs(request):
    return web.json_response({"jobs": git_ops.manager.status(config.current_user())})


@post("/git/clear")
async def api_git_clear(request):
    git_ops.manager.clear_finished(config.current_user())
    return _ok()


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
