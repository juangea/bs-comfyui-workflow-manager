# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Tests de bswm.projects: árbol, vínculos, espejo en carpeta propia y operaciones cruzadas."""
import json
import os
import time

from _fake import fresh_env


def _wf(mark="x", id_="11111111-1111-4111-8111-111111111111"):
    return json.dumps({"id": id_, "nodes": [], "mark": mark})


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _raises(code, fn, *args, **kw):
    from bswm.util import UserError
    try:
        fn(*args, **kw)
    except UserError as exc:
        assert exc.code == code, f"código {exc.code}, esperado {code}"
        return
    raise AssertionError(f"debería fallar con {code}")


def _seed():
    from bswm import workflows as wf
    wf.write("wf1.json", _wf("wf1"))
    wf.write("clientes/wf2.json", _wf("wf2"))


def _project(tree, pid):
    return next(p for p in tree["projects"] if p["id"] == pid)


def _with_folder(base, name="render"):
    from bswm import projects
    folder = os.path.join(base, "fuera", name)
    return projects.create_project(name, folder=folder), folder


# ----------------------------- proyectos sin carpeta -----------------------------
def test_project_without_folder_only_groups():
    fresh_env()
    from bswm import projects, workflows as wf
    _seed()
    p = projects.create_project("pepe")
    projects.add_subfolder(p["id"], "imagen")
    projects.link_workflow(p["id"], "wf1.json", "imagen")
    tree = projects.tree()
    item = _project(tree, p["id"])["items"][0]
    assert item["path"] == "wf1.json" and item["folder"] == "imagen"
    assert wf.exists("wf1.json")
    general = next(w for w in tree["workflows"] if w["path"] == "wf1.json")
    assert general["projects"] == [p["id"]]


def test_exclusive_by_default_and_optional_sharing():
    fresh_env()
    from bswm import projects
    _seed()
    p1 = projects.create_project("pepe")
    p2 = projects.create_project("joseluis")
    projects.link_workflow(p1["id"], "wf1.json")
    _raises("already_linked", projects.link_workflow, p2["id"], "wf1.json")
    projects.link_workflow(p2["id"], "wf1.json", allow_multi=True)
    tree = projects.tree()
    assert _project(tree, p1["id"])["items"][0]["shared"] is True
    assert _project(tree, p2["id"])["items"][0]["shared"] is True


def test_move_between_subfolders_and_projects_keeps_file():
    fresh_env()
    from bswm import projects, workflows as wf
    _seed()
    p1 = projects.create_project("pepe")
    p2 = projects.create_project("joseluis")
    projects.link_workflow(p1["id"], "wf1.json", "imagen")
    res = projects.move_item("wf1.json", p1["id"], p1["id"], "video")
    assert res["old"] == res["new"] == "wf1.json"
    assert _project(projects.tree(), p1["id"])["items"][0]["folder"] == "video"
    projects.move_item("wf1.json", p1["id"], p2["id"], "")
    tree = projects.tree()
    assert not _project(tree, p1["id"])["items"]
    assert _project(tree, p2["id"])["items"][0]["path"] == "wf1.json"
    assert wf.exists("wf1.json")


def test_move_keeps_other_shared_links():
    fresh_env()
    from bswm import projects
    _seed()
    a, b, c = [projects.create_project(n) for n in ("a", "b", "c")]
    projects.link_workflow(a["id"], "wf1.json")
    projects.link_workflow(b["id"], "wf1.json", allow_multi=True)
    projects.move_item("wf1.json", a["id"], c["id"], "")
    tree = projects.tree()
    assert len(_project(tree, b["id"])["items"]) == 1
    assert len(_project(tree, c["id"])["items"]) == 1
    assert not _project(tree, a["id"])["items"]


def test_drag_out_of_project_unlinks():
    fresh_env()
    from bswm import projects, workflows as wf
    _seed()
    p = projects.create_project("pepe")
    projects.link_workflow(p["id"], "wf1.json", "imagen")
    projects.move_item("wf1.json", p["id"], None, "")
    assert not _project(projects.tree(), p["id"])["items"]
    assert wf.exists("wf1.json")


def test_rename_and_general_moves_update_links():
    fresh_env()
    from bswm import projects
    _seed()
    p = projects.create_project("pepe")
    projects.link_workflow(p["id"], "clientes/wf2.json")
    projects.rename_item("clientes/wf2.json", "nuevo")
    assert _project(projects.tree(), p["id"])["items"][0]["path"] == "clientes/nuevo.json"
    projects.rename_general_folder("clientes", "studio")
    item = _project(projects.tree(), p["id"])["items"][0]
    assert item["path"] == "studio/nuevo.json" and item["exists"]
    projects.on_renamed("studio/nuevo.json", "otro.json")
    assert _project(projects.tree(), p["id"])["items"][0]["path"] == "otro.json"
    projects.on_deleted("otro.json")
    assert not _project(projects.tree(), p["id"])["items"]


def test_remove_subfolder_moves_items_to_root():
    fresh_env()
    from bswm import projects
    _seed()
    p = projects.create_project("pepe")
    projects.link_workflow(p["id"], "wf1.json", "imagen/v1")
    projects.remove_subfolder(p["id"], "imagen")
    project = _project(projects.tree(), p["id"])
    assert project["items"][0]["folder"] == "" and "imagen" not in project["subfolders"]


# ----------------------------- proyectos con carpeta propia -----------------------------
def test_save_writes_to_comfy_and_project_folder():
    base = fresh_env()
    from bswm import projects, workflows as wf
    p, folder = _with_folder(base)
    rel = f"{p['prefix']}/shots/a.json"
    wf.write(rel, _wf("v1"))          # lo que hace el Guardar nativo de ComfyUI
    assert projects.on_saved(rel) == "render"
    assert _read(os.path.join(folder, "shots", "a.json"))["mark"] == "v1"
    wf.write(rel, _wf("v2"), overwrite=True)
    projects.on_saved(rel)
    assert _read(os.path.join(folder, "shots", "a.json"))["mark"] == "v2"


def test_save_outside_projects_touches_nothing():
    base = fresh_env()
    from bswm import projects, workflows as wf
    _with_folder(base)
    wf.write("suelto.json", _wf())
    assert projects.on_saved("suelto.json") is None


def test_open_materializes_file_in_comfy():
    base = fresh_env()
    from bswm import projects, workflows as wf
    p, folder = _with_folder(base)
    # Un archivo que solo está en la carpeta del proyecto (p. ej. tras un git pull).
    wf.write("shots/b.json", _wf("del-git"), root=folder)
    item = _project(projects.tree(), p["id"])["items"][0]
    assert item["path"] == f"{p['prefix']}/shots/b.json"
    assert not wf.exists(item["path"])
    assert projects.prepare_open(item["path"]) == item["path"]
    assert json.loads(wf.read_bytes(item["path"]))["mark"] == "del-git"


def test_open_uses_newest_copy():
    base = fresh_env()
    from bswm import projects, workflows as wf
    p, folder = _with_folder(base)
    rel = f"{p['prefix']}/c.json"
    wf.write(rel, _wf("comfy"))
    projects.on_saved(rel)
    mirror = os.path.join(folder, "c.json")
    with open(mirror, "w", encoding="utf-8") as fh:
        fh.write(_wf("pull"))
    future = time.time() + 60
    os.utime(mirror, (future, future))
    projects.prepare_open(rel)
    assert json.loads(wf.read_bytes(rel))["mark"] == "pull"


def test_tree_hides_project_files_from_general():
    base = fresh_env()
    from bswm import projects, workflows as wf
    p, _folder = _with_folder(base)
    wf.write(f"{p['prefix']}/oculto.json", _wf())
    wf.write("visible.json", _wf())
    tree = projects.tree()
    assert [w["path"] for w in tree["workflows"]] == ["visible.json"]
    assert p["prefix"] not in tree["folders"]


def test_move_into_and_out_of_folder_project():
    base = fresh_env()
    from bswm import projects, workflows as wf
    _seed()
    p, folder = _with_folder(base)
    res = projects.add_to_project("wf1.json", p["id"], "shots")
    assert res["new"] == f"{p['prefix']}/shots/wf1.json"
    assert not wf.exists("wf1.json") and wf.exists(res["new"])
    assert os.path.isfile(os.path.join(folder, "shots", "wf1.json"))

    # Dentro del proyecto: de subcarpeta a subcarpeta.
    res = projects.move_item(res["new"], p["id"], p["id"], "final")
    assert os.path.isfile(os.path.join(folder, "final", "wf1.json"))
    assert not os.path.exists(os.path.join(folder, "shots", "wf1.json"))

    # Fuera del proyecto: vuelve a Workflows y desaparece de la carpeta.
    res = projects.move_item(res["new"], p["id"], None, "clientes")
    assert res["new"] == "clientes/wf1.json" and wf.exists("clientes/wf1.json")
    assert not os.path.exists(os.path.join(folder, "final", "wf1.json"))


def test_move_between_folder_projects():
    base = fresh_env()
    from bswm import projects, workflows as wf
    a, fa = _with_folder(base, "a")
    b, fb = _with_folder(base, "b")
    rel = f"{a['prefix']}/x.json"
    wf.write(rel, _wf())
    projects.on_saved(rel)
    res = projects.move_item(rel, a["id"], b["id"], "sub")
    assert res["new"] == f"{b['prefix']}/sub/x.json"
    assert os.path.isfile(os.path.join(fb, "sub", "x.json"))
    assert not os.path.exists(os.path.join(fa, "x.json"))


def test_move_with_tab_open_only_reconciles():
    """Con pestaña abierta ComfyUI mueve el archivo; el backend reconcilia el resto."""
    base = fresh_env()
    from bswm import projects, workflows as wf
    p, folder = _with_folder(base)
    rel = f"{p['prefix']}/x.json"
    wf.write(rel, _wf())
    projects.on_saved(rel)
    plan = projects.move_item(rel, p["id"], p["id"], "sub", dry_run=True)
    assert wf.exists(rel), "dry_run no debe tocar nada"
    wf.relocate(rel, plan["new"])     # lo que hace store.renameWorkflow
    projects.move_item(rel, p["id"], p["id"], "sub", general_moved=True)
    assert wf.exists(plan["new"]) and not wf.exists(rel)
    assert os.path.isfile(os.path.join(folder, "sub", "x.json"))
    assert not os.path.exists(os.path.join(folder, "x.json"))


def test_no_overwrite_in_project_folder():
    base = fresh_env()
    from bswm import projects, workflows as wf
    _seed()
    p, folder = _with_folder(base)
    wf.write("wf1.json", _wf("en-carpeta"), root=folder)
    _raises("exists", projects.add_to_project, "wf1.json", p["id"], "")
    assert wf.exists("wf1.json")


def test_duplicate_is_independent_and_gets_new_id():
    base = fresh_env()
    from bswm import projects, workflows as wf
    _seed()
    p, folder = _with_folder(base)
    new = projects.duplicate_item("wf1.json", p["id"], "copias")
    assert new == f"{p['prefix']}/copias/wf1.json"
    copy = json.loads(wf.read_bytes(new))
    assert copy["id"] != json.loads(wf.read_bytes("wf1.json"))["id"]
    assert os.path.isfile(os.path.join(folder, "copias", "wf1.json"))
    other = projects.create_project("etiquetas")
    new2 = projects.duplicate_item("wf1.json", other["id"], "v2")
    assert new2 == "wf1 copy.json"
    assert _project(projects.tree(), other["id"])["items"][0]["folder"] == "v2"


def test_delete_removes_both_copies():
    base = fresh_env()
    from bswm import projects, workflows as wf
    p, folder = _with_folder(base)
    rel = f"{p['prefix']}/x.json"
    wf.write(rel, _wf())
    projects.on_saved(rel)
    projects.delete_item(rel)
    assert not wf.exists(rel) and not os.path.exists(os.path.join(folder, "x.json"))


def test_folder_inside_comfy_has_no_mirror():
    fresh_env()
    from bswm import projects, workflows as wf
    folder = os.path.join(wf.get_root(), "dentro")
    p = projects.create_project("dentro", folder=folder)
    assert p["prefix"] == "dentro"
    wf.write("dentro/a.json", _wf())
    assert projects.on_saved("dentro/a.json") is None
    assert [i["path"] for i in _project(projects.tree(), p["id"])["items"]] == ["dentro/a.json"]


def test_add_folder_later_and_remove_it():
    base = fresh_env()
    from bswm import projects, workflows as wf
    _seed()
    p = projects.create_project("pepe")
    projects.link_workflow(p["id"], "wf1.json", "imagen")
    folder = os.path.join(base, "fuera", "pepe")
    updated = projects.update_project(p["id"], folder=folder)
    moved = f"{updated['prefix']}/imagen/wf1.json"
    assert wf.exists(moved) and not wf.exists("wf1.json")
    assert os.path.isfile(os.path.join(folder, "imagen", "wf1.json"))
    projects.update_project(p["id"], folder="")
    item = _project(projects.tree(), p["id"])["items"][0]
    assert item["path"] == moved and item["folder"] == "imagen" and item["exists"]
    assert os.path.isfile(os.path.join(folder, "imagen", "wf1.json")), "la carpeta no se toca"


# ----------------------------- seguridad -----------------------------
def test_project_folder_validation():
    base = fresh_env()
    from bswm import projects, workflows as wf
    _raises("folder_absolute", projects.create_project, "a", folder="relativa/carpeta")
    _raises("folder_forbidden", projects.create_project, "b", folder=os.path.abspath(os.sep))
    _raises("folder_forbidden", projects.create_project, "c", folder=base)
    assert os.path.dirname(wf.get_root()).startswith(base)


def test_project_ops_only_touch_workflow_files():
    base = fresh_env()
    from bswm import projects
    p, folder = _with_folder(base)
    secret = os.path.join(folder, "secret.txt")
    with open(secret, "w") as fh:
        fh.write("x")
    _raises("not_workflow", projects.source_file, f"{p['prefix']}/secret.txt")
    _raises("not_workflow", projects.delete_item, f"{p['prefix']}/secret.txt")
    _raises("bad_path", projects.delete_item, "../../secret.json")
    assert os.path.isfile(secret)


def test_delete_project_with_files_keeps_other_files():
    base = fresh_env()
    from bswm import projects, workflows as wf
    p, folder = _with_folder(base)
    rel = f"{p['prefix']}/sub/x.json"
    wf.write(rel, _wf())
    projects.on_saved(rel)
    other = os.path.join(folder, "render.png")
    with open(other, "w") as fh:
        fh.write("x")
    projects.delete_project(p["id"], delete_files=True)
    assert not wf.exists(rel)
    assert not os.path.exists(os.path.join(folder, "sub", "x.json"))
    assert os.path.isfile(other)
    assert projects.tree()["projects"] == []


def test_delete_project_without_files_keeps_workflows():
    base = fresh_env()
    from bswm import projects, workflows as wf
    p, folder = _with_folder(base)
    rel = f"{p['prefix']}/x.json"
    wf.write(rel, _wf())
    projects.on_saved(rel)
    projects.delete_project(p["id"])
    assert wf.exists(rel) and os.path.isfile(os.path.join(folder, "x.json"))
    assert rel in [w["path"] for w in projects.tree()["workflows"]]


def test_import_validates_structure():
    base = fresh_env()
    from bswm import projects
    _raises("bad_db", projects.import_db, {"projects": "x", "links": []})
    _raises("bad_db", projects.import_db, {"projects": [{"name": "sin id"}], "links": []})
    _raises("bad_path", projects.import_db, {"projects": [], "links": [
        {"id": "l", "project_id": "p", "workflow_ref": "../../x.json"}]})
    # Se restaura sin esa carpeta, que contiene la de ComfyUI.
    projects.import_db({"projects": [{"id": "p", "name": "n", "folder": base}], "links": []})
    assert projects.tree()["projects"][0]["folder"] is None


def test_export_import_roundtrip():
    fresh_env()
    from bswm import projects
    _seed()
    p = projects.create_project("pepe")
    projects.link_workflow(p["id"], "wf1.json")
    dump = projects.export_db()
    projects.import_db({"projects": [], "links": []})
    assert projects.tree()["projects"] == []
    projects.import_db(dump)
    assert len(projects.tree()["projects"]) == 1


# ----------------------------- datos de versiones anteriores -----------------------------
def test_old_database_is_upgraded():
    base = fresh_env()
    from bswm import config, projects, workflows as wf
    wf.write("a.json", _wf())
    folder = os.path.join(base, "fuera", "viejo")
    wf.write("shots/b.json", _wf(), root=folder)
    from bswm.util import save_json
    save_json(config.get_db_path(), {
        "version": 1,
        "settings": {"active_project": None},
        "projects": [
            {"id": "p_v", "name": "virtual", "color": "#111111", "storage": "virtual", "folder": None,
             "subfolders": ["imagen"], "git": {"mode": "studio", "remote_url": ""}, "notes": ""},
            {"id": "p_f", "name": "viejo", "color": "#222222", "storage": "folder", "folder": folder,
             "subfolders": [], "git": {"mode": "dedicated", "remote_url": "git@x:y.git"}, "notes": ""},
        ],
        "links": [{"id": "l1", "project_id": "p_v", "subfolder": "imagen", "workflow_ref": "a.json",
                   "alias": "", "primary": True}],
    })
    tree = projects.tree()
    v = _project(tree, "p_v")
    f = _project(tree, "p_f")
    assert v["items"][0]["path"] == "a.json" and v["folder"] is None
    assert f["prefix"] == "viejo" and f["remote_url"] == "git@x:y.git"
    assert f["items"][0]["path"] == "viejo/shots/b.json"


def test_legacy_custom_root_becomes_project():
    base = fresh_env()
    from bswm import config, projects, workflows as wf
    legacy = os.path.join(base, "mi_biblioteca")
    wf.write("carpeta/antiguo.json", _wf("antiguo"), root=legacy)
    wf.write("otro.json", _wf(), root=legacy)
    cfg = config.load()
    cfg["workflows_root"] = legacy
    config.save(cfg)
    from bswm.util import save_json
    save_json(config.get_db_path(), {"projects": [
        {"id": "p_v", "name": "etiquetas", "folder": None, "storage": "virtual"},
    ], "links": [{"id": "l1", "project_id": "p_v", "subfolder": "", "workflow_ref": "carpeta/antiguo.json"}]})
    tree = projects.tree()
    lib = next(p for p in tree["projects"] if p["name"] == "mi_biblioteca")
    assert sorted(i["ref"] for i in lib["items"]) == ["carpeta/antiguo.json", "otro.json"]
    linked = _project(tree, "p_v")["items"][0]
    assert linked["path"] == "mi_biblioteca/carpeta/antiguo.json" and linked["exists"]
    assert os.path.isfile(os.path.join(legacy, "otro.json")), "la carpeta original no se toca"
    assert config.load().get("workflows_root") is None


# ----------------------------- incluir y mover entre proyectos -----------------------------
def _item(tree, pid, name):
    return next((i for i in _project(tree, pid)["items"] if i["name"] == name), None)


def test_include_in_second_project_keeps_the_first():
    fresh_env()
    from bswm import projects
    _seed()
    a, b = projects.create_project("a"), projects.create_project("b")
    projects.add_to_project("wf1.json", a["id"])
    projects.add_to_project("wf1.json", b["id"], "sub", allow_multi=True)
    tree = projects.tree()
    assert _item(tree, a["id"], "wf1.json")["shared"] and _item(tree, b["id"], "wf1.json")["folder"] == "sub"


def test_include_project_file_into_project_with_folder_keeps_link():
    base = fresh_env()
    from bswm import projects, workflows as wf
    _seed()
    a = projects.create_project("a")
    b, folder = _with_folder(base)
    projects.add_to_project("wf1.json", a["id"])
    res = projects.add_to_project("wf1.json", b["id"])
    assert res["new"] == "render/wf1.json" and wf.exists("render/wf1.json")
    assert os.path.isfile(os.path.join(folder, "wf1.json"))
    tree = projects.tree()
    assert _item(tree, a["id"], "wf1.json")["path"] == "render/wf1.json"
    assert _item(tree, a["id"], "wf1.json")["shared"] and _item(tree, b["id"], "wf1.json")["shared"]


def test_include_between_folder_projects_makes_a_copy():
    base = fresh_env()
    from bswm import projects, workflows as wf
    a, _fa = _with_folder(base, "uno")
    b, fb = _with_folder(base, "dos")
    wf.write("uno/x.json", _wf("x"))
    plan = projects.add_to_project("uno/x.json", b["id"], dry_run=True)
    assert plan["old"] == plan["new"], "la pestaña abierta no debe moverse"
    projects.add_to_project("uno/x.json", b["id"], "sub")
    assert wf.exists("uno/x.json") and wf.exists("dos/sub/x.json")
    copy = _read(os.path.join(fb, "sub", "x.json"))
    assert copy["mark"] == "x" and copy["id"] != _read(wf.abs_path("uno/x.json"))["id"]


def test_include_folder_file_into_tag_project_is_a_link():
    base = fresh_env()
    from bswm import projects, workflows as wf
    a, _f = _with_folder(base, "uno")
    v = projects.create_project("v")
    wf.write("uno/x.json", _wf("x"))
    projects.add_to_project("uno/x.json", v["id"], allow_multi=True)
    tree = projects.tree()
    assert _item(tree, v["id"], "x.json")["path"] == "uno/x.json"
    assert _item(tree, a["id"], "x.json")["shared"]


def test_exclusive_move_from_tag_project():
    base = fresh_env()
    from bswm import projects, workflows as wf
    _seed()
    a, b, c = projects.create_project("a"), projects.create_project("b"), projects.create_project("c")
    projects.add_to_project("wf1.json", a["id"])
    projects.add_to_project("wf1.json", c["id"], allow_multi=True)
    projects.move_item("wf1.json", a["id"], b["id"], "sub")
    tree = projects.tree()
    assert _item(tree, a["id"], "wf1.json") is None
    assert _item(tree, b["id"], "wf1.json")["folder"] == "sub"
    assert _item(tree, c["id"], "wf1.json"), "solo sale del proyecto de origen"
    d, folder = _with_folder(base)
    res = projects.move_item("wf1.json", b["id"], d["id"], "")
    assert res["new"] == "render/wf1.json" and os.path.isfile(os.path.join(folder, "wf1.json"))
    assert _item(projects.tree(), c["id"], "wf1.json")["path"] == "render/wf1.json"
    assert wf.exists("render/wf1.json") and not wf.exists("wf1.json")


def test_exclusive_from_workflows_row_leaves_other_projects():
    fresh_env()
    from bswm import projects
    _seed()
    a, b = projects.create_project("a"), projects.create_project("b")
    projects.add_to_project("wf1.json", a["id"])
    projects.move_item("wf1.json", None, b["id"], "", exclusive=True)
    tree = projects.tree()
    assert _item(tree, a["id"], "wf1.json") is None and _item(tree, b["id"], "wf1.json")


def test_moving_a_link_never_takes_the_file_from_its_folder_project():
    base = fresh_env()
    from bswm import projects, workflows as wf
    a, _f = _with_folder(base, "uno")
    c, _g = _with_folder(base, "tres")
    v, w = projects.create_project("v"), projects.create_project("w")
    wf.write("uno/x.json", _wf("x"))
    projects.add_to_project("uno/x.json", v["id"])
    # A "Workflows": solo se quita el vínculo, aunque se suelte en una carpeta.
    assert projects.move_item("uno/x.json", v["id"], None, "carpeta", dry_run=True)["new"] == "uno/x.json"
    projects.move_item("uno/x.json", v["id"], None, "carpeta")
    assert wf.exists("uno/x.json") and _item(projects.tree(), v["id"], "x.json") is None
    # A otro proyecto sin carpeta: el vínculo cambia de proyecto.
    projects.add_to_project("uno/x.json", v["id"])
    projects.move_item("uno/x.json", v["id"], w["id"], "")
    assert _item(projects.tree(), w["id"], "x.json")["path"] == "uno/x.json"
    # A otro proyecto con carpeta: recibe una copia y el original sigue en su proyecto.
    assert projects.move_item("uno/x.json", w["id"], c["id"], "", dry_run=True)["new"] == "uno/x.json"
    projects.move_item("uno/x.json", w["id"], c["id"], "")
    tree = projects.tree()
    assert wf.exists("uno/x.json") and wf.exists("tres/x.json")
    assert _item(tree, w["id"], "x.json") is None and _item(tree, a["id"], "x.json")


def test_links_follow_subfolder_changes_of_the_owning_project():
    base = fresh_env()
    from bswm import projects, workflows as wf
    a, _f = _with_folder(base, "uno")
    v = projects.create_project("v")
    projects.add_subfolder(a["id"], "viejo")
    wf.write("uno/viejo/x.json", _wf("x"))
    projects.add_to_project("uno/viejo/x.json", v["id"])
    projects.rename_subfolder(a["id"], "viejo", "nuevo")
    item = _item(projects.tree(), v["id"], "x.json")
    assert item["path"] == "uno/nuevo/x.json" and item["exists"]
    projects.remove_subfolder(a["id"], "nuevo")
    assert _item(projects.tree(), v["id"], "x.json") is None, "sin vínculos colgando"


def test_deleting_projects_respects_shared_files():
    base = fresh_env()
    from bswm import projects, workflows as wf
    a, _f = _with_folder(base, "uno")
    v, w = projects.create_project("v"), projects.create_project("w")
    wf.write("uno/x.json", _wf("x"))
    projects.add_to_project("uno/x.json", v["id"])
    projects.add_to_project("uno/x.json", w["id"], allow_multi=True)
    projects.delete_project(v["id"], delete_files=True)
    assert wf.exists("uno/x.json"), "el archivo es del proyecto con carpeta"
    projects.delete_project(a["id"], delete_files=True)
    assert not wf.exists("uno/x.json") and _project(projects.tree(), w["id"])["items"] == []


def test_giving_a_folder_to_a_project_copies_files_of_other_folder_projects():
    base = fresh_env()
    from bswm import projects, workflows as wf
    a, _f = _with_folder(base, "uno")
    v = projects.create_project("v")
    wf.write("uno/x.json", _wf("x"))
    projects.add_to_project("uno/x.json", v["id"])
    projects.update_project(v["id"], folder=os.path.join(base, "fuera", "v"))
    tree = projects.tree()
    assert wf.exists("uno/x.json") and wf.exists("v/x.json")
    assert _item(tree, a["id"], "x.json") and _item(tree, v["id"], "x.json")["path"] == "v/x.json"
    assert _read(wf.abs_path("v/x.json"))["id"] != _read(wf.abs_path("uno/x.json"))["id"]


# ----------------------------- deshacer -----------------------------
def _undo(res, **kw):
    from bswm import projects
    return projects.undo_move(res["old"], res["new"], res.get("links"), res.get("copied"), res.get("copied_mtime"), **kw)


def _state():
    from bswm import projects
    tree = projects.tree()
    return {
        "general": sorted(w["path"] for w in tree["workflows"]),
        "projects": {p["name"]: sorted((i["path"], i["folder"]) for i in p["items"]) for p in tree["projects"]},
    }


def test_undo_restores_every_kind_of_move():
    base = fresh_env()
    from bswm import projects
    _seed()
    a, b = projects.create_project("a"), projects.create_project("b")
    f, folder = _with_folder(base)
    g, _ = _with_folder(base, "otro")
    projects.add_subfolder(a["id"], "sub")
    projects.add_to_project("wf1.json", a["id"], "sub")
    projects.add_to_project("clientes/wf2.json", g["id"])
    ops = [
        lambda: projects.add_to_project("wf1.json", b["id"], "x", allow_multi=True),   # incluir en otro
        lambda: projects.add_to_project("wf1.json", f["id"]),                           # incluir en carpeta
        lambda: projects.move_item("wf1.json", a["id"], b["id"], "x"),                  # exclusivo
        lambda: projects.move_item("wf1.json", a["id"], f["id"], "x"),                  # exclusivo a carpeta
        lambda: projects.move_item("wf1.json", a["id"], None, "nueva"),                 # sacar a una carpeta
        lambda: projects.move_item("wf1.json", a["id"], a["id"], ""),                   # entre subcarpetas
        lambda: projects.move_item("otro/wf2.json", g["id"], None, "vuelta"),           # sacar de carpeta propia
        lambda: projects.move_item("otro/wf2.json", g["id"], f["id"], ""),              # entre carpetas propias
        lambda: projects.add_to_project("otro/wf2.json", f["id"]),                      # copia entre carpetas
    ]
    for op in ops:
        before = _state()
        res = op()
        assert _state() != before, "la operación debería cambiar algo"
        _undo(res)
        assert _state() == before, f"no se restauró: {res}"
    assert os.path.isfile(os.path.join(os.path.dirname(folder), "otro", "wf2.json"))


def test_undo_with_open_tab_only_reconciles():
    base = fresh_env()
    from bswm import projects, workflows as wf
    _seed()
    f, folder = _with_folder(base)
    res = projects.add_to_project("wf1.json", f["id"])
    plan = _undo(res, dry_run=True)
    assert plan == {"old": "render/wf1.json", "new": "wf1.json"}
    assert wf.exists("render/wf1.json"), "el ensayo no cambia nada"
    wf.relocate("render/wf1.json", "wf1.json")      # lo que hace ComfyUI con la pestaña abierta
    _undo(res, general_moved=True)
    assert not os.path.isfile(os.path.join(folder, "wf1.json")), "la copia del proyecto se retira"


def test_undo_does_not_overwrite_or_remove_edited_copies():
    base = fresh_env()
    from bswm import projects, workflows as wf
    _seed()
    f, _ = _with_folder(base)
    res = projects.add_to_project("wf1.json", f["id"])
    wf.write("wf1.json", _wf("nuevo"))
    _raises("exists", _undo, res)
    assert wf.exists("render/wf1.json"), "sin pisar nada ni perder el archivo movido"

    g, _ = _with_folder(base, "otro")
    res = projects.add_to_project("render/wf1.json", g["id"])
    assert res["copied"] == "otro/wf1.json"
    os.utime(wf.file_path(res["copied"]), (1, 1))
    _raises("copy_changed", _undo, res)
    assert wf.exists("otro/wf1.json")


def test_undo_ignores_projects_deleted_meanwhile():
    fresh_env()
    from bswm import projects
    _seed()
    a, b = projects.create_project("a"), projects.create_project("b")
    projects.add_to_project("wf1.json", a["id"])
    res = projects.move_item("wf1.json", a["id"], b["id"], "")
    projects.delete_project(a["id"])
    _undo(res)
    assert _project(projects.tree(), b["id"])["items"] == []


# ----------------------------- revisión: nada se pierde ni se pisa -----------------------------
def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def test_assigning_a_folder_never_overwrites_its_files():
    base = fresh_env()
    from bswm import projects, workflows as wf
    target = os.path.join(base, "destino")
    _write(os.path.join(target, "wf1.json"), _wf("valioso"))
    _seed()
    v = projects.create_project("v")
    projects.add_to_project("wf1.json", v["id"])
    _raises("exists", projects.update_project, v["id"], folder=target)
    assert _read(os.path.join(target, "wf1.json"))["mark"] == "valioso"
    assert wf.exists("wf1.json"), "sin cambios si no se puede completar"
    assert _project(projects.tree(), v["id"])["folder"] is None

    f, _ = _with_folder(base)
    wf.write("render/wf1b.json", _wf("comfy"))
    _write(os.path.join(target, "wf1b.json"), _wf("valioso"))
    _raises("exists", projects.update_project, f["id"], folder=target)
    assert _read(os.path.join(target, "wf1b.json"))["mark"] == "valioso"


def test_assigning_a_folder_with_identical_files_is_fine():
    base = fresh_env()
    from bswm import projects, workflows as wf
    target = os.path.join(base, "destino")
    _write(os.path.join(target, "wf1.json"), _wf("wf1"))
    _seed()
    v = projects.create_project("v")
    projects.add_to_project("wf1.json", v["id"])
    projects.update_project(v["id"], folder=target)
    assert _project(projects.tree(), v["id"])["items"][0]["ref"] == "wf1.json"


def test_moving_a_project_folder_into_comfy_takes_its_files():
    base = fresh_env()
    from bswm import projects, workflows as wf
    f, _ = _with_folder(base)
    v = projects.create_project("v")
    wf.write("render/sub/a.json", _wf("a"))
    projects.add_to_project("render/sub/a.json", v["id"])
    projects.update_project(f["id"], folder=wf.abs_path("dentro/proyecto"))
    tree = projects.tree()
    assert [i["path"] for i in _project(tree, f["id"])["items"]] == ["dentro/proyecto/sub/a.json"]
    assert _project(tree, v["id"])["items"][0]["path"] == "dentro/proyecto/sub/a.json"
    assert not wf.exists("render/sub/a.json")


def test_prefixes_cannot_overlap_or_be_the_whole_root():
    fresh_env()
    from bswm import projects, workflows as wf
    projects.create_project("a", folder=wf.abs_path("mismo"))
    _raises("folder_in_use", projects.create_project, "b", folder=wf.abs_path("mismo"))
    _raises("folder_in_use", projects.create_project, "c", folder=wf.abs_path("mismo/dentro"))
    projects.create_project("d", folder=wf.abs_path("otro/dentro"))
    _raises("folder_in_use", projects.create_project, "e", folder=wf.abs_path("otro"))
    _raises("folder_forbidden", projects.create_project, "f", folder=wf.get_root())


def test_old_or_imported_bad_prefixes_can_not_delete_everything():
    fresh_env()
    from bswm import config, projects, workflows as wf
    from bswm.util import save_json
    _seed()
    save_json(config.get_db_path(), {"projects": [
        {"id": "p_raiz", "name": "raiz", "folder": wf.get_root()},
        {"id": "p_punto", "name": "punto", "folder": "/fuera/x", "prefix": "."},
        {"id": "p_mala", "name": "mala", "folder": "/fuera/y", "prefix": "../fuera"},
    ], "links": []})
    tree = projects.tree()
    assert _project(tree, "p_raiz")["folder"] is None and _project(tree, "p_raiz")["items"] == []
    assert _project(tree, "p_punto")["prefix"] not in (".", "") and _project(tree, "p_mala")["prefix"] != "../fuera"
    projects.delete_project("p_raiz", delete_files=True)
    assert wf.exists("wf1.json"), "borrar ese proyecto no borra los workflows de ComfyUI"
    _raises("root_forbidden", wf.delete_workflows_in, ".")


def test_legacy_migration_survives_a_failure_and_retries():
    base = fresh_env()
    from bswm import config, projects, workflows as wf
    legacy = os.path.join(base, "biblioteca_offline")
    cfg = config.load()
    cfg["workflows_root"] = legacy
    config.save(cfg)
    assert projects.tree()["projects"] == [], "carpeta no disponible"
    assert config.legacy_root() == legacy, "no se olvida: se reintenta en el siguiente arranque"
    wf.write("a.json", _wf(), root=legacy)
    projects._legacy_failed.clear()                 # siguiente arranque
    assert [p["name"] for p in projects.tree()["projects"]] == ["biblioteca_offline"]
    assert config.legacy_root() is None


def test_same_name_links_fail_before_moving_anything():
    base = fresh_env()
    from bswm import projects, workflows as wf
    wf.write("x/mismo.json", _wf("x"))
    wf.write("y/mismo.json", _wf("y"))
    v = projects.create_project("v")
    projects.add_to_project("x/mismo.json", v["id"])
    projects.add_to_project("y/mismo.json", v["id"])
    _raises("exists", projects.update_project, v["id"], folder=os.path.join(base, "fuera", "v"))
    assert wf.exists("x/mismo.json") and wf.exists("y/mismo.json")
    assert len(_project(projects.tree(), v["id"])["items"]) == 2


def test_deleting_a_tag_project_keeps_files_shared_with_others():
    fresh_env()
    from bswm import projects, workflows as wf
    _seed()
    a, b = projects.create_project("a"), projects.create_project("b")
    projects.add_to_project("wf1.json", a["id"])
    projects.add_to_project("clientes/wf2.json", a["id"])
    projects.add_to_project("wf1.json", b["id"], allow_multi=True)
    projects.delete_project(a["id"], delete_files=True)
    assert wf.exists("wf1.json") and _item(projects.tree(), b["id"], "wf1.json")
    assert not wf.exists("clientes/wf2.json"), "lo que solo era suyo sí se borra"


def test_general_folders_can_not_touch_projects_inside():
    fresh_env()
    from bswm import projects, workflows as wf
    a = projects.create_project("a", folder=wf.abs_path("clientes/pepe"))
    wf.write("clientes/pepe/x.json", _wf())
    wf.write("clientes/otro.json", _wf())
    _raises("folder_has_project", projects.rename_general_folder, "clientes", "nuevo")
    _raises("folder_has_project", projects.delete_general_folder, "clientes")
    _raises("folder_has_project", projects.create_general_folder, "clientes/pepe/sub")
    assert wf.exists("clientes/pepe/x.json") and _project(projects.tree(), a["id"])["items"]
    assert projects.create_general_folder("clientes/libre") == "clientes/libre"


def test_rehearsal_reports_problems_before_a_tab_is_moved():
    base = fresh_env()
    from bswm import projects, workflows as wf
    _seed()
    f, folder = _with_folder(base)
    _write(os.path.join(folder, "wf1.json"), _wf("solo en la carpeta"))
    _raises("exists", projects.move_item, "wf1.json", None, f["id"], "", dry_run=True)
    _raises("exists", projects.add_to_project, "wf1.json", f["id"], "", dry_run=True)
    wf.write("otro.json", _wf())
    _raises("exists", projects.rename_item, "wf1.json", "otro", dry_run=True)
    assert wf.exists("wf1.json")


def test_import_never_overwrites():
    base = fresh_env()
    from bswm import projects, workflows as wf
    f, folder = _with_folder(base)
    _write(os.path.join(folder, "m.json"), _wf("solo en la carpeta"))
    _raises("exists", projects.import_workflow, "m.json", _wf("nuevo"), f["id"])
    assert _read(os.path.join(folder, "m.json"))["mark"] == "solo en la carpeta"
    _raises("bad_json", projects.import_workflow, "roto.json", "no es json")
    assert not wf.exists("roto.json")
    v = projects.create_project("v")
    assert projects.import_workflow("n", _wf("n"), v["id"], "sub") == "n.json"
    assert _item(projects.tree(), v["id"], "n.json")["folder"] == "sub"
    assert projects.import_workflow("p.json", _wf("p"), f["id"], "sub") == "render/sub/p.json"
    assert os.path.isfile(os.path.join(folder, "sub", "p.json"))


def test_export_and_duplicate_do_not_touch_a_possibly_open_file():
    base = fresh_env()
    from bswm import projects, workflows as wf
    f, folder = _with_folder(base)
    wf.write("render/x.json", _wf("viejo"))
    mirror = os.path.join(folder, "x.json")
    _write(mirror, _wf("nuevo"))
    os.utime(mirror, (time.time() + 60, time.time() + 60))
    assert os.path.samefile(projects.source_file("render/x.json"), mirror), "se exporta lo más reciente"
    assert _read(wf.abs_path("render/x.json"))["mark"] == "viejo", "sin tocar la copia de ComfyUI"
    copy = projects.duplicate_item("render/x.json", f["id"], "", "copia")
    assert _read(wf.abs_path(copy))["mark"] == "nuevo"
    assert _read(wf.abs_path("render/x.json"))["mark"] == "viejo"


def test_overwrite_with_save_as_keeps_links():
    fresh_env()
    from bswm import projects, workflows as wf
    _seed()
    v = projects.create_project("v")
    projects.add_to_project("wf1.json", v["id"])
    projects.on_deleted("wf1.json")          # ComfyUI ya lo ha vuelto a crear
    assert _item(projects.tree(), v["id"], "wf1.json")
    wf.remove_file("wf1.json")
    projects.on_deleted("wf1.json")          # borrado de verdad
    assert _item(projects.tree(), v["id"], "wf1.json") is None


def test_failed_mirror_leaves_the_move_undone():
    base = fresh_env()
    from bswm import projects, workflows as wf
    from bswm.util import save_json
    _seed()
    f, folder = _with_folder(base)
    real = projects._sync_mirrors_after_move

    def offline(*_args):
        raise OSError("carpeta del proyecto sin conexión")

    projects._sync_mirrors_after_move = offline
    try:
        try:
            projects.move_item("wf1.json", None, f["id"], "")
            raise AssertionError("debería fallar")
        except OSError:
            pass
    finally:
        projects._sync_mirrors_after_move = real
    assert wf.exists("wf1.json") and not wf.exists("render/wf1.json")


def test_old_mirror_is_kept_if_the_new_one_fails():
    base = fresh_env()
    from bswm import projects, workflows as wf
    a, fa = _with_folder(base, "uno")
    b, fb = _with_folder(base, "dos")
    wf.write("uno/x.json", _wf("x"))
    projects.on_saved("uno/x.json")
    real = projects.copy_atomic

    def offline(*_args):
        raise OSError("sin conexión")

    projects.copy_atomic = offline
    try:
        try:
            projects.move_item("uno/x.json", a["id"], b["id"], "")
            raise AssertionError("debería fallar")
        except OSError:
            pass
    finally:
        projects.copy_atomic = real
    assert os.path.isfile(os.path.join(fa, "x.json")) and wf.exists("uno/x.json")


# ----------------------------- segunda revisión -----------------------------
def test_case_only_rename_keeps_the_project_copy():
    base = fresh_env()
    from bswm import projects, workflows as wf
    f, folder = _with_folder(base)
    wf.write("render/a.json", _wf("a"))
    projects.on_saved("render/a.json")
    projects.rename_item("render/a.json", "A")
    assert os.listdir(folder) == ["A.json"], os.listdir(folder)
    assert [i["path"] for i in _project(projects.tree(), f["id"])["items"]] == ["render/A.json"]


def test_projects_can_not_share_or_nest_folders():
    base = fresh_env()
    from bswm import projects
    shared = os.path.join(base, "fuera", "compartida")
    a = projects.create_project("a", folder=shared)
    _raises("folder_in_use", projects.create_project, "b", folder=shared)
    _raises("folder_in_use", projects.create_project, "c", folder=os.path.join(shared, "dentro"))
    _raises("folder_in_use", projects.create_project, "d", folder=os.path.dirname(shared))
    e = projects.create_project("e", folder=os.path.join(base, "fuera", "otra"))
    _raises("folder_in_use", projects.update_project, e["id"], folder=shared)
    assert projects.update_project(a["id"], name="a2", folder=shared)["name"] == "a2", "su propia carpeta sí"


def test_rename_subfolder_is_all_or_nothing():
    base = fresh_env()
    from bswm import projects, workflows as wf
    f, folder = _with_folder(base)
    wf.write("render/viejo/a.json", _wf("a"))
    projects.on_saved("render/viejo/a.json")
    wf.write("render/nuevo/b.json", _wf("b"))
    _raises("exists", projects.rename_subfolder, f["id"], "viejo", "nuevo")
    assert os.path.isfile(os.path.join(folder, "viejo", "a.json")), "la copia del proyecto no se ha movido"
    assert wf.exists("render/viejo/a.json")


def test_deleting_with_the_folder_unmounted_is_refused():
    base = fresh_env()
    import shutil
    from bswm import projects, workflows as wf
    f, folder = _with_folder(base)
    wf.write("render/sub/x.json", _wf())
    wf.write("render/z.json", _wf())
    shutil.rmtree(folder)
    _raises("folder_not_found", projects.delete_item, "render/z.json")
    _raises("folder_not_found", projects.remove_subfolder, f["id"], "sub")
    _raises("folder_not_found", projects.rename_subfolder, f["id"], "sub", "otra")
    _raises("folder_not_found", projects.delete_project, f["id"], delete_files=True)
    assert wf.exists("render/z.json") and wf.exists("render/sub/x.json")
    assert not os.path.exists(folder)
    projects.delete_project(f["id"])         # sin borrar archivos no hace falta la carpeta


def test_comfy_rename_updates_links_even_if_the_mirror_fails():
    base = fresh_env()
    import shutil
    from bswm import projects, workflows as wf
    from bswm.util import UserError
    _seed()
    v = projects.create_project("v")
    f, folder = _with_folder(base)
    projects.add_to_project("wf1.json", v["id"])
    shutil.rmtree(folder)
    wf.relocate("wf1.json", "render/wf1.json")
    try:
        projects.on_renamed("wf1.json", "render/wf1.json")
        raise AssertionError("debería avisar del fallo")
    except UserError as exc:
        assert exc.code == "folder_not_found"
    assert _item(projects.tree(), v["id"], "wf1.json")["path"] == "render/wf1.json"


def test_check_free_looks_at_the_project_folder():
    base = fresh_env()
    from bswm import projects, workflows as wf
    f, folder = _with_folder(base)
    with open(os.path.join(folder, "solo.json"), "w", encoding="utf-8") as fh:
        fh.write(_wf("en la carpeta"))
    _raises("exists", projects.check_free, "render/solo.json")
    projects.check_free("render/libre.json")


def test_folder_named_like_the_data_folder_is_listed():
    fresh_env()
    from bswm import projects, workflows as wf
    wf.write("bswm/x/a.json", _wf())
    assert [w["path"] for w in projects.tree()["workflows"]] == ["bswm/x/a.json"]


def test_project_folder_inside_comfy_survives_losing_its_last_workflow():
    fresh_env()
    from bswm import projects, workflows as wf
    p = projects.create_project("dentro", folder=wf.abs_path("dentro"))
    wf.write("dentro/sub/a.json", _wf())
    projects.delete_item("dentro/sub/a.json")
    assert os.path.isdir(wf.abs_path("dentro")) and not os.path.isdir(wf.abs_path("dentro/sub"))
    assert _project(projects.tree(), p["id"])["folder_ok"]


# ----------------------------- datos de versiones anteriores o importados -----------------------------
def _old_db(projects_, links=()):
    from bswm import config
    from bswm.util import save_json
    save_json(config.get_db_path(), {"version": 1, "settings": {"active_project": None},
                                     "projects": list(projects_), "links": list(links)})


def test_legacy_root_that_already_was_a_project_without_prefix():
    base = fresh_env()
    from bswm import config, projects, workflows as wf
    lib = os.path.join(base, "lib")
    wf.write("x.json", _wf("x"), root=lib)
    _old_db([{"id": "p_lib", "name": "lib", "storage": "folder", "folder": lib},
             {"id": "p_v", "name": "v", "storage": "virtual", "folder": None}],
            [{"id": "l", "project_id": "p_v", "subfolder": "", "workflow_ref": "x.json"}])
    cfg = config.load()
    cfg["workflows_root"] = lib
    config.save(cfg)
    tree = projects.tree()
    assert _project(tree, "p_lib")["prefix"] == "lib"
    assert _project(tree, "p_v")["items"][0]["path"] == "lib/x.json"
    assert config.legacy_root() is None


def test_old_folder_containing_comfy_is_dropped_without_touching_files():
    base = fresh_env()
    from bswm import config, projects, workflows as wf
    wf.write("keep.json", _wf())
    user = os.path.dirname(wf.get_root())
    _old_db([{"id": "p", "name": "todo", "storage": "folder", "folder": user},
             {"id": "q", "name": "datos", "storage": "folder", "folder": config.data_dir()}])
    tree = projects.tree()
    assert _project(tree, "p")["folder"] is None and _project(tree, "q")["folder"] is None
    projects.delete_project("p", delete_files=True)
    assert wf.exists("keep.json") and os.path.isfile(config.get_db_path())
    _raises("folder_forbidden", projects.create_project, "z", folder=config.data_dir())


def test_old_overlapping_folders_do_not_delete_each_other():
    base = fresh_env()
    from bswm import projects, workflows as wf
    outer, inner = os.path.join(base, "o"), os.path.join(base, "o", "i")
    wf.write("a.json", _wf(), root=inner)
    _old_db([{"id": "p_o", "name": "fuera", "storage": "folder", "folder": outer},
             {"id": "p_i", "name": "dentro", "storage": "folder", "folder": inner}])
    tree = projects.tree()
    using = [p for p in tree["projects"] if p["folder"]]
    assert len(using) == 1, "solo uno conserva la carpeta"
    if using[0]["id"] == "p_o":
        projects.delete_project("p_o", delete_files=True)
    assert os.path.isfile(os.path.join(inner, "a.json")) or using[0]["id"] == "p_i"


def test_imported_overlaps_and_orphan_links_are_repaired():
    base = fresh_env()
    from bswm import projects, workflows as wf
    _seed()
    folder = os.path.join(base, "o")
    os.makedirs(folder)
    projects.import_db({"version": 2, "projects": [
        {"id": "a", "name": "a", "folder": folder}, {"id": "b", "name": "b", "folder": folder},
    ], "links": [{"id": "l", "project_id": "fantasma", "workflow_ref": "wf1.json"}]})
    tree = projects.tree()
    assert len([p for p in tree["projects"] if p["folder"]]) == 1
    general = next(w for w in tree["workflows"] if w["path"] == "wf1.json")
    assert general["projects"] == [], "un vínculo huérfano no debe ocultar el archivo"


def test_old_links_on_a_project_with_folder_do_not_hide_files():
    base = fresh_env()
    from bswm import projects, workflows as wf
    _seed()
    folder = os.path.join(base, "o")
    os.makedirs(folder)
    _old_db([{"id": "p", "name": "p", "storage": "folder", "folder": folder}],
            [{"id": "l", "project_id": "p", "subfolder": "", "workflow_ref": "wf1.json"}])
    tree = projects.tree()
    assert next(w for w in tree["workflows"] if w["path"] == "wf1.json")["projects"] == []
    projects.delete_project("p", delete_files=True)
    assert wf.exists("wf1.json"), "no era suyo"


def test_deleting_keeps_json_files_that_are_not_workflows():
    base = fresh_env()
    from bswm import projects, workflows as wf
    f, folder = _with_folder(base)
    for name in ("package.json", "datos.json"):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
            fh.write('{"name": "otra cosa"}')
    with open(os.path.join(folder, "api.json"), "w", encoding="utf-8") as fh:
        fh.write('{"3": {"class_type": "KSampler", "inputs": {}}}')
    wf.write("render/n.json", _wf())
    projects.on_saved("render/n.json")
    projects.delete_project(f["id"], delete_files=True)
    assert sorted(os.listdir(folder)) == ["datos.json", "package.json"]
    wf.write("carpeta/package.json", '{"name": "x"}')
    wf.write("carpeta/w.json", _wf())
    assert projects.delete_general_folder("carpeta") == {"removed": 1, "gone": False}
    assert wf.exists("carpeta/package.json")


def test_jobs_belong_to_their_user():
    fresh_env()
    from bswm import git_ops
    from bswm.exporter import ExportManager
    exp = ExportManager()
    a, b = exp.enqueue("a", [], "ana"), exp.enqueue("b", [], "beto")
    for _ in range(100):
        if all(j["state"] == "done" for j in exp.status()):
            break
        time.sleep(0.02)
    assert [j["id"] for j in exp.status("ana")] == [a] and exp.get(b, "ana") is None and exp.get(b, "beto")
    exp.clear_finished("ana")
    assert [j["id"] for j in exp.status()] == [b]
    git = git_ops.GitManager()
    j = git.enqueue("remote", base_tmp(), owner="ana", url="https://example.com/a.git")
    assert [x["id"] for x in git.status("ana")] == [j] and git.status("beto") == []


def base_tmp():
    import tempfile
    return tempfile.mkdtemp(prefix="bswm_git_")
