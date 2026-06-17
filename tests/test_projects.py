# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Tests de bswm.projects (BD de proyectos, con folder_paths falso)."""
import json
import os

from _fake import fresh_env


def _seed_general():
    from bswm import workflows as wf
    wf.write("wf1.json", json.dumps({"nodes": []}))
    wf.mkdir("clientes")
    wf.write("clientes/wf2.json", json.dumps({"nodes": []}))


def test_create_and_resolve_virtual():
    fresh_env()
    from bswm import projects
    _seed_general()
    p = projects.create_project("pepe", storage="virtual")
    projects.add_subfolder(p["id"], "imagen")
    projects.link_workflow(p["id"], "wf1.json", subfolder="imagen")
    res = projects.resolve()
    proj = res["projects"][0]
    assert proj["name"] == "pepe"
    assert proj["count"] == 1
    assert proj["items"][0]["subfolder"] == "imagen"
    assert proj["items"][0]["exists"] is True


def test_exclusivity_and_multilink():
    fresh_env()
    from bswm import projects
    _seed_general()
    p1 = projects.create_project("pepe")
    p2 = projects.create_project("joseluis")
    projects.link_workflow(p1["id"], "wf1.json")
    try:
        projects.link_workflow(p2["id"], "wf1.json")
        raise AssertionError("la exclusividad no se aplicó")
    except ValueError:
        pass
    projects.link_workflow(p2["id"], "wf1.json", allow_multi=True)
    res = projects.resolve()
    # ambos proyectos contienen el mismo archivo, marcado como compartido
    shared = [i for proj in res["projects"] for i in proj["items"] if i["shared"]]
    assert len(shared) == 2


def test_move_link_between_subfolders_and_projects():
    fresh_env()
    from bswm import projects
    _seed_general()
    p1 = projects.create_project("pepe")
    p2 = projects.create_project("joseluis")
    projects.link_workflow(p1["id"], "wf1.json", subfolder="imagen")
    # mover de imagen -> video (misma metadata, el archivo no se mueve)
    projects.project_move(p1["id"], "wf1.json", p1["id"], "video")
    res = projects.resolve()
    p1r = [p for p in res["projects"] if p["id"] == p1["id"]][0]
    assert p1r["items"][0]["subfolder"] == "video"
    # mover de p1 -> p2
    projects.project_move(p1["id"], "wf1.json", p2["id"], "")
    res = projects.resolve()
    p1r = [p for p in res["projects"] if p["id"] == p1["id"]][0]
    p2r = [p for p in res["projects"] if p["id"] == p2["id"]][0]
    assert p1r["count"] == 0 and p2r["count"] == 1


def test_folder_project_copy_and_duplicate():
    fresh_env()
    from bswm import projects
    _seed_general()
    base = os.path.dirname(os.path.dirname(projects.config.default_workflows_root()))
    folder = os.path.join(base, "proj_render")
    p = projects.create_project("render", storage="folder", folder=folder,
                                git={"mode": "dedicated"})
    projects.add_current_to_project(p["id"], "wf1.json", subfolder="shots")
    res = projects.resolve()
    pr = res["projects"][0]
    assert pr["storage"] == "folder"
    assert pr["count"] == 1
    assert pr["items"][0]["ref"] == "shots/wf1.json"
    assert os.path.isfile(os.path.join(folder, "shots", "wf1.json"))
    # duplicar dentro del proyecto de carpeta
    projects.project_duplicate(p["id"], "shots/wf1.json")
    res = projects.resolve()
    assert res["projects"][0]["count"] == 2


def test_export_import_db():
    fresh_env()
    from bswm import projects
    _seed_general()
    p = projects.create_project("pepe")
    projects.link_workflow(p["id"], "wf1.json")
    dump = projects.export_db()
    assert dump["projects"] and dump["links"]
    # importar reemplazando: vaciar y restaurar
    projects.import_db({"version": 1, "projects": [], "links": []})
    assert projects.resolve()["projects"] == []
    projects.import_db(dump)
    assert len(projects.resolve()["projects"]) == 1


def test_save_canvas_virtual_and_folder():
    base = fresh_env()
    from bswm import projects
    content = json.dumps({"nodes": [{"id": 1}]})
    # virtual: escribe en la raíz general y crea vínculo
    pv = projects.create_project("pepe", storage="virtual")
    res = projects.save_canvas(pv["id"], "from_canvas", content, subfolder="imagen")
    assert res["ref"] == "imagen/from_canvas.json"
    pr = [p for p in projects.resolve()["projects"] if p["id"] == pv["id"]][0]
    assert pr["count"] == 1 and pr["items"][0]["subfolder"] == "imagen"
    # folder: escribe dentro de la carpeta del proyecto
    folder = os.path.join(base, "proj_folder")
    pf = projects.create_project("render", storage="folder", folder=folder)
    projects.save_canvas(pf["id"], "shot.json", content, subfolder="v01")
    assert os.path.isfile(os.path.join(folder, "v01", "shot.json"))
    # sin overwrite, repetir falla
    try:
        projects.save_canvas(pf["id"], "shot.json", content, subfolder="v01")
        raise AssertionError("debería fallar sin overwrite")
    except ValueError:
        pass
    projects.save_canvas(pf["id"], "shot.json", content, subfolder="v01", overwrite=True)  # ok


def test_dedicated_requires_folder():
    fresh_env()
    from bswm import projects
    try:
        projects.create_project("x", storage="virtual", git={"mode": "dedicated"})
        raise AssertionError("debería exigir carpeta para 'dedicated'")
    except ValueError:
        pass
