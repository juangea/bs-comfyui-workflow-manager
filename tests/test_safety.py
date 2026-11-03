# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Casos en los que una operación podía perder archivos o dejarlos a medias (offline, sin ComfyUI)."""
import json
import os
import subprocess
import sys
import time
import zipfile

from bswm import config, exporter, git_ops, projects, workflows
from bswm.util import UserError, ensure_json_ext, normalize_rel, safe_component, save_json

from _fake import fresh_env

WF = json.dumps({"id": "x", "nodes": [], "links": []})


def _setup():
    return fresh_env()


def _raises(code, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except UserError as exc:
        assert exc.code == code, exc.code
        return
    raise AssertionError(f"no falló con {code}")


def _write(path, text=WF):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _link_dir(link, target):
    """Enlace a carpeta: unión en Windows, enlace simbólico en el resto."""
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", link, target], check=True, capture_output=True)
    else:
        os.symlink(target, link)


def _folder_project(tmp, name="P"):
    return projects.create_project(name, folder=os.path.join(tmp, name + "_folder"))


def test_names_the_system_would_alter_are_rejected():
    _setup()
    _raises("bad_name", ensure_json_ext, "a\0b")
    _raises("bad_path", normalize_rel, "a\0b")
    if os.name == "nt":
        for bad in ("v2: final", "a?b", "a*", "a|b", "CON", "nul", "com1"):
            _raises("bad_name", ensure_json_ext, bad)
        for bad in ("v2: final.json", "a./b.json", "a /b.json"):
            _raises("bad_path", workflows.abs_path, bad)
        assert normalize_rel("a\\b.json") == "a/b.json"
    else:
        assert ensure_json_ext("v2: final") == "v2: final.json"
        assert normalize_rel(" a.json") == " a.json"
        assert normalize_rel("a\\b.json") == "a\\b.json"


def test_rename_with_a_colon_never_loses_the_file():
    _setup()
    workflows.write("a.json", WF)
    if os.name == "nt":
        _raises("bad_name", projects.rename_item, "a.json", "v2: final")
        assert workflows.exists("a.json")
    else:
        projects.rename_item("a.json", "v2: final")
        assert workflows.exists("v2: final.json")


def test_project_names_make_usable_folders():
    assert len(safe_component("x" * 300)) <= 100
    assert safe_component("CON") == "_CON"
    assert safe_component("com1.txt") == "_com1.txt"
    tmp = _setup()
    p = projects.create_project("y" * 300, folder=os.path.join(tmp, "largo"))
    workflows.write(f"{p['prefix']}/a.json", WF)
    assert workflows.exists(f"{p['prefix']}/a.json")


def test_delete_does_not_enter_nested_links():
    tmp = _setup()
    outside = os.path.join(tmp, "externo")
    _write(os.path.join(outside, "ajeno.json"))
    _write(os.path.join(outside, "sub", "ajeno2.json"))
    workflows.write("a/mio.json", WF)
    _link_dir(os.path.join(workflows.get_root(), "a", "enlace"), outside)

    assert os.path.isfile(os.path.join(outside, "ajeno.json"))
    result = projects.delete_general_folder("a")
    assert result["removed"] == 1
    assert os.path.isfile(os.path.join(outside, "ajeno.json"))
    assert os.path.isfile(os.path.join(outside, "sub", "ajeno2.json"))
    assert not workflows.exists("a/mio.json")


def test_delete_project_and_subfolder_do_not_enter_links():
    tmp = _setup()
    outside = os.path.join(tmp, "externo")
    _write(os.path.join(outside, "ajeno.json"))
    p = _folder_project(tmp)
    projects.add_subfolder(p["id"], "s")
    workflows.write(f"{p['prefix']}/s/mio.json", WF)
    _link_dir(os.path.join(workflows.get_root(), p["prefix"], "s", "enlace"), outside)
    _link_dir(os.path.join(p["folder"], "enlace2"), outside)
    projects.remove_subfolder(p["id"], "s")
    assert os.path.isfile(os.path.join(outside, "ajeno.json"))
    projects.delete_project(p["id"], delete_files=True)
    assert os.path.isfile(os.path.join(outside, "ajeno.json"))


def test_deleting_a_file_keeps_the_linked_folder_it_was_in():
    tmp = _setup()
    outside = os.path.join(tmp, "externo")
    _write(os.path.join(outside, "uno.json"))
    _link_dir(os.path.join(workflows.get_root(), "compartida"), outside)
    projects.delete_item("compartida/uno.json")
    assert os.path.isdir(os.path.join(workflows.get_root(), "compartida"))


def test_move_failure_leaves_a_single_copy():
    _setup()
    workflows.write("a.json", WF)
    real_rename = os.rename

    def fails(*a, **k):
        raise PermissionError(13, "in use")
    os.rename = fails
    try:
        try:
            workflows.relocate("a.json", "b.json")
        except PermissionError:
            pass
        else:
            raise AssertionError("debía fallar")
    finally:
        os.rename = real_rename
    assert workflows.exists("a.json") and not workflows.exists("b.json")


def test_mirror_failure_removes_the_new_copy():
    tmp = _setup()
    p = _folder_project(tmp)
    workflows.write(f"{p['prefix']}/a.json", WF)
    projects.on_saved(f"{p['prefix']}/a.json")
    real_remove = os.remove

    def fails(path, *a, **k):
        if path.endswith("a.json") and "P_folder" in path:
            raise PermissionError(13, "in use")
        return real_remove(path, *a, **k)
    os.remove = fails
    try:
        try:
            projects.rename_item(f"{p['prefix']}/a.json", "b")
        except PermissionError:
            pass
        else:
            raise AssertionError("debía fallar")
    finally:
        os.remove = real_remove
    assert workflows.exists(f"{p['prefix']}/a.json") and not workflows.exists(f"{p['prefix']}/b.json")
    assert os.path.isfile(os.path.join(p["folder"], "a.json"))
    assert not os.path.isfile(os.path.join(p["folder"], "b.json"))


def test_giving_a_folder_to_a_project_is_all_or_nothing():
    tmp = _setup()
    p = projects.create_project("Tag")
    workflows.write("a.json", WF)
    workflows.write("b.json", WF.replace("x", "y"))
    projects.link_workflow(p["id"], "a.json")
    projects.link_workflow(p["id"], "b.json")
    target = os.path.join(tmp, "destino")
    os.makedirs(os.path.join(target, "b.json"))     # una carpeta con el nombre de un archivo
    _raises("exists", projects.update_project, p["id"], folder=target)
    assert workflows.exists("a.json") and workflows.exists("b.json")
    assert not projects.load_db()["projects"][0].get("folder")

    # También si el fallo llega con la operación ya empezada.
    os.rmdir(os.path.join(target, "b.json"))
    real = projects.copy_atomic
    calls = []

    def fails(src, dst):
        calls.append(dst)
        if len(calls) == 2:
            raise OSError("disk full")
        return real(src, dst)
    projects.copy_atomic = fails
    try:
        try:
            projects.update_project(p["id"], folder=target)
        except OSError:
            pass
        else:
            raise AssertionError("debía fallar")
    finally:
        projects.copy_atomic = real
    assert workflows.exists("a.json") and workflows.exists("b.json")
    assert not os.path.exists(os.path.join(target, "a.json"))
    assert not projects.load_db()["projects"][0].get("folder")


def test_partial_delete_drops_the_links_of_what_was_removed():
    _setup()
    p = projects.create_project("Tag")
    workflows.write("c/a.json", WF)
    workflows.write("c/b.json", WF)
    projects.link_workflow(p["id"], "c/a.json")
    projects.link_workflow(p["id"], "c/b.json")
    real = os.remove
    done = []

    def fails(path, *a, **k):
        if done:
            raise PermissionError(13, "in use")
        done.append(path)
        return real(path, *a, **k)
    os.remove = fails
    try:
        try:
            projects.delete_general_folder("c")
        except PermissionError:
            pass
        else:
            raise AssertionError("debía fallar")
    finally:
        os.remove = real
    db = projects.load_db()
    left = [l["workflow_ref"] for l in db["links"]]
    assert len(left) == 1 and workflows.exists(left[0])


def test_native_save_keeps_a_file_that_was_only_in_the_project_folder():
    tmp = _setup()
    p = _folder_project(tmp)
    _write(os.path.join(p["folder"], "b.json"), WF.replace("x", "del_compañero"))
    workflows.write(f"{p['prefix']}/b.json", WF)    # "Guardar como" nativo: ComfyUI no veía el otro
    projects.on_saved(f"{p['prefix']}/b.json", created=True)
    names = sorted(os.listdir(p["folder"]))
    assert names == ["b (conflict).json", "b.json"], names
    with open(os.path.join(p["folder"], "b (conflict).json"), encoding="utf-8") as fh:
        assert "del_compañero" in fh.read()
    # Los guardados normales siguen actualizando la copia sin más.
    workflows.write(f"{p['prefix']}/b.json", WF.replace("x", "v2"), overwrite=True)
    projects.on_saved(f"{p['prefix']}/b.json")
    assert sorted(os.listdir(p["folder"])) == names


def test_native_rename_keeps_a_file_that_was_only_in_the_project_folder():
    tmp = _setup()
    p = _folder_project(tmp)
    workflows.write(f"{p['prefix']}/a.json", WF)
    projects.on_saved(f"{p['prefix']}/a.json")
    _write(os.path.join(p["folder"], "b.json"), WF.replace("x", "ajeno"))
    workflows.relocate(f"{p['prefix']}/a.json", f"{p['prefix']}/b.json")    # ComfyUI ya lo ha movido
    projects.on_renamed(f"{p['prefix']}/a.json", f"{p['prefix']}/b.json")
    assert sorted(os.listdir(p["folder"])) == ["b (conflict).json", "b.json"]


def test_imported_prefix_does_not_take_over_an_existing_folder():
    tmp = _setup()
    workflows.write("render/ajeno.json", WF)
    folder = os.path.join(tmp, "remoto")
    os.makedirs(folder)
    projects.import_db({"projects": [{"id": "p_1", "name": "R", "folder": folder, "prefix": "render"}], "links": []})
    prefix = projects.load_db()["projects"][0]["prefix"]
    assert prefix != "render", prefix
    # Reimportar la propia BD en el mismo equipo conserva el prefijo.
    own = projects.export_db()
    workflows.write(f"{prefix}/mio.json", WF)
    projects.import_db(own)
    assert projects.load_db()["projects"][0]["prefix"] == prefix


def test_import_rejects_what_would_break_the_panel():
    _setup()
    for project in ({"id": "a", "name": 5}, {"id": ["a"], "name": "a"},
                    {"id": "a", "name": "a", "subfolders": 7}, {"id": "a", "name": "a", "subfolders": [5]},
                    {"id": "a", "name": "a", "color": 3}):
        _raises("bad_db", projects.import_db, {"projects": [project], "links": []})
    for link in ({"id": "l", "project_id": [], "workflow_ref": "a.json"},
                 {"id": "l", "project_id": "a", "workflow_ref": "a.json", "subfolder": 5}):
        _raises("bad_db", projects.import_db, {"projects": [{"id": "a", "name": "a"}], "links": [link]})
    projects.tree()


def test_unusable_links_do_not_break_the_panel():
    _setup()
    save_json(config.get_db_path(), {"version": 2, "projects": [{"id": "a", "name": "a"}], "links": [
        {"id": "l1", "project_id": "a", "workflow_ref": "../fuera.json"},
        {"id": "l2", "project_id": ["x"], "workflow_ref": "b.json"},
        "basura",
    ], "settings": {}})
    assert projects.tree()["projects"][0]["items"] == []


def test_reserved_names_that_already_exist_keep_working():
    if os.name != "nt":
        return
    _setup()
    path = os.path.join(workflows.get_root(), "aux.json")
    try:
        _write(path)
    except OSError:
        return      # versiones anteriores de Windows no los admiten
    p = projects.create_project("Tag")
    projects.link_workflow(p["id"], "aux.json")
    projects.on_saved("aux.json")
    assert projects.tree()["projects"][0]["items"][0]["exists"]
    copy = projects.duplicate_item("aux.json")
    assert workflows.exists(copy)
    projects.rename_item("aux.json", "normal")
    assert workflows.exists("normal.json")
    _raises("bad_name", projects.rename_item, "normal.json", "aux")


def test_old_label_subfolders_stay_usable():
    _setup()
    name = "WIP? v1."
    save_json(config.get_db_path(), {"version": 2, "settings": {}, "projects": [
        {"id": "a", "name": "A", "subfolders": [name, ".old"]},
        {"id": "b", "name": "B"}], "links": [
        {"id": "l", "project_id": "a", "workflow_ref": "x.json", "subfolder": name}]})
    workflows.write("x.json", WF)
    workflows.write("y.json", WF)
    item = projects.tree()["projects"][0]["items"][0]
    assert item["folder"] == name and item["exists"]
    projects.move_item("y.json", None, "a", name)
    projects.move_item("y.json", "a", "a", ".old")
    projects.move_item("x.json", "a", "a", "")
    projects.rename_subfolder("a", name, "bien")
    projects.remove_subfolder("a", "bien")
    projects.remove_subfolder("a", ".old")
    assert projects.tree()["projects"][0]["subfolders"] == []


def test_links_to_names_this_system_cannot_have_are_ignored():
    _setup()
    projects.import_db({"projects": [{"id": "a", "name": "A"}], "links": [
        {"id": "l", "project_id": "a", "workflow_ref": "v2: final.json"}]})
    items = projects.tree()["projects"][0]["items"]
    assert len(items) == (0 if os.name == "nt" else 1)


def test_backup_with_a_folder_no_longer_accepted_is_restored_without_it():
    _setup()
    projects.import_db({"projects": [{"id": "a", "name": "A", "folder": workflows.get_root()}], "links": []})
    assert projects.tree()["projects"][0]["folder"] is None


def test_restoring_a_lost_database_keeps_the_prefix_of_identical_files():
    base = _setup()
    folder = os.path.join(base, "propio")
    _write(os.path.join(folder, "a.json"))
    workflows.write("R/a.json", WF)
    projects.import_db({"projects": [{"id": "p_1", "name": "R", "folder": folder, "prefix": "R"}], "links": []})
    assert projects.load_db()["projects"][0]["prefix"] == "R"
    assert [i["path"] for i in projects.tree()["projects"][0]["items"]] == ["R/a.json"]


def test_name_with_spaces_is_duplicated_where_it_says():
    if os.name == "nt":
        return
    _setup()
    workflows.write(" lead.json", WF)
    copy = projects.duplicate_item(" lead.json")
    assert workflows.exists(copy), copy


def test_case_variants_on_a_disk_that_distinguishes_them_each_have_their_copy():
    base = _setup()
    p = _folder_project(base)
    probe = os.path.join(p["folder"], "CaseProbe")
    _write(probe, "x")
    insensitive = os.path.exists(probe.lower())
    os.remove(probe)
    if insensitive:
        return
    workflows.write(f"{p['prefix']}/foo.json", WF)
    projects.on_saved(f"{p['prefix']}/foo.json")
    workflows.write(f"{p['prefix']}/Foo.json", WF.replace("x", "otro"))
    projects.on_saved(f"{p['prefix']}/Foo.json", created=True)
    assert sorted(os.listdir(p["folder"])) == ["Foo.json", "foo.json"]


def test_hidden_project_prefix_does_not_block_its_subfolders():
    _setup()
    inside = os.path.join(workflows.get_root(), ".proj")
    os.makedirs(os.path.join(inside, "s"))
    save_json(config.get_db_path(), {"version": 2, "settings": {}, "links": [], "projects": [
        {"id": "a", "name": "A", "folder": inside, "prefix": ".proj", "subfolders": ["s"]}]})
    projects.rename_subfolder("a", "s", "t")
    assert os.path.isdir(os.path.join(inside, "t"))


def test_hidden_folders_cannot_be_created():
    _setup()
    p = projects.create_project("Tag")
    _raises("bad_name", projects.add_subfolder, p["id"], ".antiguo")
    _raises("bad_name", projects.add_subfolder, p["id"], "a/.b")
    _raises("bad_name", projects.create_general_folder, ".oculta")
    projects.add_subfolder(p["id"], "visible")
    _raises("bad_name", projects.rename_subfolder, p["id"], "visible", ".oculta")
    workflows.write("x.json", WF)
    _raises("bad_name", projects.move_item, "x.json", None, None, ".oculta")
    assert workflows.exists("x.json")


def test_folder_rules_do_not_depend_on_project_order():
    tmp = _setup()
    inside = os.path.join(workflows.get_root(), "dentro")
    os.makedirs(inside)
    db = {"projects": [{"id": "a", "name": "A", "folder": workflows.get_root()},
                       {"id": "b", "name": "B", "folder": inside}], "links": [], "settings": {}, "version": 1}
    save_json(config.get_db_path(), db)
    folders = {p["id"]: p["folder"] for p in projects.load_db()["projects"]}
    assert folders["a"] is None
    assert folders["b"] and os.path.samefile(folders["b"], inside)


def test_repeated_project_names_do_not_block_other_changes():
    _setup()
    save_json(config.get_db_path(), {"version": 2, "links": [], "settings": {}, "projects": [
        {"id": "a", "name": "Cliente"}, {"id": "b", "name": "cliente"}]})
    assert projects.update_project("a", name="Cliente", notes="n")["notes"] == "n"
    projects.update_project("a", name="Otro")
    _raises("project_exists", projects.update_project, "a", name="cliente")


def test_renaming_a_label_subfolder_over_another_does_not_merge():
    _setup()
    p = projects.create_project("Tag")
    projects.add_subfolder(p["id"], "a/x")
    projects.add_subfolder(p["id"], "x")
    _raises("exists", projects.rename_subfolder, p["id"], "a/x", "x")
    projects.add_subfolder(p["id"], "b")
    assert projects.rename_subfolder(p["id"], "b", "B") == "B"
    assert projects.rename_subfolder(p["id"], "B", "c") == "c"


def test_undo_trial_refuses_a_copy_that_has_changed():
    tmp = _setup()
    p = _folder_project(tmp, "A")
    q = _folder_project(tmp, "B")
    workflows.write(f"{p['prefix']}/a.json", WF)
    r = projects.add_to_project(f"{p['prefix']}/a.json", q["id"], allow_multi=True)
    assert r["copied"]
    path = workflows.file_path(r["copied"])
    os.utime(path, (time.time() + 50, time.time() + 50))
    _raises("copy_changed", projects.undo_move, r["old"], r["new"], r["links"], r["copied"], r["copied_mtime"], dry_run=True)
    assert workflows.exists(r["copied"])


def test_git_protects_comfyui_even_if_the_user_folder_is_elsewhere():
    if not git_ops.detect()["git"]["available"]:
        return
    tmp = _setup()
    comfy = os.path.join(tmp, "ComfyUI")
    flows = os.path.join(comfy, "flows")
    os.makedirs(flows)
    subprocess.run(["git", "init", comfy], check=True, capture_output=True)
    assert git_ops.is_blocked(flows, [workflows.get_root(), comfy])
    other = os.path.join(tmp, "otro")
    os.makedirs(other)
    assert not git_ops.is_blocked(other, [workflows.get_root(), comfy])
    assert not git_ops.is_blocked(other, workflows.get_root())


def test_git_init_keeps_the_branches_of_an_existing_repository():
    if not git_ops.detect()["git"]["available"]:
        return
    tmp = _setup()
    repo = os.path.join(tmp, "repo")
    os.makedirs(repo)
    git = ["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "init", repo], check=True, capture_output=True)
    subprocess.run([*git, "commit", "--allow-empty", "-m", "uno"], check=True, capture_output=True)
    subprocess.run([*git, "branch", "-M", "dev"], check=True, capture_output=True)
    job = git_ops._Job("j", "init", repo)
    git_ops.manager._do_init(job, {})
    out = subprocess.run([*git, "symbolic-ref", "--short", "HEAD"], check=True, capture_output=True, text=True).stdout
    assert out.strip() == "dev"


def test_export_survives_old_dates():
    tmp = _setup()
    path = os.path.join(tmp, "viejo.json")
    _write(path)
    os.utime(path, (100000000, 100000000))     # 1973
    manager = exporter.ExportManager()
    jid = manager.enqueue("x", [(path, "viejo.json")])
    for _ in range(100):
        job = manager.get(jid)
        if job.state in ("done", "error"):
            break
        time.sleep(0.05)
    assert job.state == "done", job.error
    with zipfile.ZipFile(job.zip_path) as zf:
        assert zf.namelist() == ["viejo.json"]
    manager.clear_finished()


def test_names_not_in_utf8_survive_on_linux():
    if sys.platform == "win32" or sys.platform == "darwin":
        return
    tmp = _setup()
    name = os.fsdecode(b"caf\xe9.json")
    workflows.write("base.json", WF)
    os.rename(workflows.file_path("base.json"), os.path.join(workflows.get_root(), name))
    p = projects.create_project("Tag")
    projects.link_workflow(p["id"], name)
    assert projects.tree()["projects"][0]["items"][0]["path"] == name
    manager = exporter.ExportManager()
    jid = manager.enqueue("x", [(os.path.join(workflows.get_root(), name), name)])
    for _ in range(100):
        job = manager.get(jid)
        if job.state in ("done", "error"):
            break
        time.sleep(0.05)
    assert job.state == "done", job.error
    manager.clear_finished()
    assert tmp


def test_dangling_link_is_not_written_through():
    if os.name == "nt":
        return
    tmp = _setup()
    outside = os.path.join(tmp, "fuera.json")
    os.symlink(outside, os.path.join(workflows.get_root(), "a.json"))
    _raises("exists", workflows.write, "a.json", WF)
    assert not os.path.exists(outside)


def test_only_case_changes_keep_the_file_and_never_replace_another():
    tmp = _setup()
    p = _folder_project(tmp)
    prefix = p["prefix"]
    workflows.write(f"{prefix}/a.json", WF)
    probe = os.path.join(p["folder"], "CaseProbe")
    _write(probe, "x")
    insensitive = os.path.exists(probe.lower())
    os.remove(probe)
    if insensitive:
        # ComfyUI renombra solo mayúsculas sin que hubiera copia en el proyecto.
        os.rename(workflows.file_path(f"{prefix}/a.json"), workflows.abs_path(f"{prefix}/A.json"))
        projects.on_renamed(f"{prefix}/a.json", f"{prefix}/A.json")
        assert [n.lower() for n in os.listdir(p["folder"])] == ["a.json"]
    else:
        workflows.write(f"{prefix}/A.json", WF.replace("x", "otro"))
        _raises("exists", projects.rename_item, f"{prefix}/a.json", "A")
        assert workflows.exists(f"{prefix}/a.json") and workflows.exists(f"{prefix}/A.json")

# ----------------------------- 1.1.1 -----------------------------
def _later(path, seconds=60):
    now = time.time() + seconds
    os.utime(path, (now, now))


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _synced(tmp, name="a.json"):
    """Proyecto con carpeta y un workflow ya igual en las dos copias. Devuelve (proyecto, ruta, copia)."""
    p = _folder_project(tmp)
    rel = f"{p['prefix']}/{name}"
    workflows.write(rel, '{"id": "viejo"}')
    projects.on_saved(rel)
    return p, rel, os.path.join(p["folder"], name)


def test_moving_an_open_tab_keeps_what_arrived_at_the_project_folder():
    tmp = _setup()
    p, rel, mirror = _synced(tmp)
    _write(mirror, '{"id": "de git"}')
    _later(mirror)
    workflows.relocate(rel, f"{p['prefix']}/b.json")
    projects.on_renamed(rel, f"{p['prefix']}/b.json")
    assert _text(os.path.join(p["folder"], "a (conflict).json")) == '{"id": "de git"}'
    assert _text(os.path.join(p["folder"], "b.json")) == '{"id": "viejo"}'
    assert not os.path.exists(mirror)


def test_panel_rename_with_tab_keeps_what_arrived_at_the_project_folder():
    tmp = _setup()
    p, rel, mirror = _synced(tmp)
    _write(mirror, '{"id": "de git"}')
    _later(mirror)
    workflows.relocate(rel, f"{p['prefix']}/b.json")
    projects.rename_item(rel, "b", general_moved=True)
    assert _text(os.path.join(p["folder"], "a (conflict).json")) == '{"id": "de git"}'


def test_rename_without_tab_uses_the_newest_copy():
    tmp = _setup()
    p, rel, mirror = _synced(tmp)
    _write(mirror, '{"id": "de git"}')
    _later(mirror)
    projects.rename_item(rel, "b")
    assert _text(os.path.join(p["folder"], "b.json")) == '{"id": "de git"}'
    assert sorted(os.listdir(p["folder"])) == ["b.json"]


def test_a_normal_rename_leaves_no_conflict_file():
    tmp = _setup()
    p, rel, _ = _synced(tmp)
    workflows.relocate(rel, f"{p['prefix']}/b.json")
    projects.on_renamed(rel, f"{p['prefix']}/b.json")
    assert sorted(os.listdir(p["folder"])) == ["b.json"]


def test_saving_a_stale_tab_keeps_what_arrived_at_the_project_folder():
    tmp = _setup()
    p, rel, mirror = _synced(tmp)
    known = os.path.getmtime(workflows.file_path(rel))
    _write(mirror, '{"id": "de git"}')
    _later(mirror)
    workflows.write(rel, '{"id": "pestaña"}', overwrite=True)
    for unit in (1, 1000):      # ComfyUI da la fecha en segundos o en milisegundos según su versión
        name, conflict = projects.mirror_saved(rel, previous=known * unit)
        assert name == "P"
        if unit == 1:
            assert conflict == "a (conflict).json"
            assert _text(os.path.join(p["folder"], conflict)) == '{"id": "de git"}'
        assert _text(mirror) == '{"id": "pestaña"}'
        _write(mirror, '{"id": "otra vez"}')
        _later(mirror)
    assert _text(os.path.join(p["folder"], "a (conflict 2).json")) != ""


def test_saving_an_up_to_date_tab_leaves_no_conflict_file():
    tmp = _setup()
    p, rel, mirror = _synced(tmp)
    for n in range(3):
        known = os.path.getmtime(workflows.file_path(rel))
        workflows.write(rel, json.dumps({"id": n}), overwrite=True)
        assert projects.mirror_saved(rel, previous=known * 1000) == ("P", None)
    assert os.listdir(p["folder"]) == ["a.json"]
    for bad in (None, True, "x", 0, -1):
        assert projects.mirror_saved(rel, previous=bad) == ("P", None)


def test_a_copy_with_the_same_content_is_not_a_conflict():
    """Solo ha cambiado la fecha: cambiar de rama y volver, o un disco de red con otro reloj."""
    tmp = _setup()
    p, rel, mirror = _synced(tmp)
    known = os.path.getmtime(workflows.file_path(rel))
    base = _text(mirror)
    _later(mirror)
    workflows.write(rel, '{"id": "pestaña"}', overwrite=True)
    assert projects.mirror_saved(rel, previous=known, base=base) == ("P", None)
    assert os.listdir(p["folder"]) == ["a.json"]
    assert _text(mirror) == '{"id": "pestaña"}'
    # Con otro contenido sí lo es, aunque la pestaña también lo haya enviado.
    known = os.path.getmtime(workflows.file_path(rel))
    base = _text(mirror)
    _write(mirror, '{"id": "de git"}')
    _later(mirror)
    workflows.write(rel, '{"id": "otra"}', overwrite=True)
    assert projects.mirror_saved(rel, previous=known, base=base) == ("P", "a (conflict).json")


def test_adding_again_to_the_same_project_doesnt_ask():
    tmp = _setup()
    p, rel, _ = _synced(tmp)
    tag = projects.create_project("Tag")
    projects.add_to_project(rel, tag["id"], allow_multi=True)
    projects.add_to_project(rel, tag["id"], "otra")
    assert [l["subfolder"] for l in projects.load_db()["links"]] == ["otra"]


def test_rename_event_without_a_real_move_changes_nothing():
    tmp = _setup()
    p, rel, mirror = _synced(tmp)
    t = projects.create_project("T")
    workflows.write("x.json", WF)
    projects.link_workflow(t["id"], "x.json")
    _raises("missing_field", projects.on_renamed, rel, None)
    _raises("missing_field", projects.on_renamed, None, rel)
    _raises("not_found", projects.on_renamed, rel, f"{p['prefix']}/z.json")
    _raises("not_found", projects.on_renamed, "x.json", "z.json")
    assert os.path.isfile(mirror)
    assert [l["workflow_ref"] for l in projects.load_db()["links"]] == ["x.json"]
    _raises("not_found", projects.rename_item, rel, "z", general_moved=True)
    assert os.path.isfile(mirror)


def test_renaming_a_subfolder_checks_both_copies():
    tmp = _setup()
    p = _folder_project(tmp)
    root = workflows.get_root()
    _write(os.path.join(root, p["prefix"], "old", "a.json"), '{"id": "comfy"}')
    _write(os.path.join(p["folder"], "new", "a.json"), '{"id": "carpeta"}')
    _raises("exists", projects.rename_subfolder, p["id"], "old", "new")
    assert _text(os.path.join(p["folder"], "new", "a.json")) == '{"id": "carpeta"}'
    assert os.path.isfile(os.path.join(root, p["prefix"], "old", "a.json"))
    assert projects.rename_subfolder(p["id"], "old", "libre") == "libre"


def test_case_only_subfolder_rename_still_works():
    tmp = _setup()
    p = _folder_project(tmp)
    workflows.write(f"{p['prefix']}/sub/a.json", WF)
    projects.on_saved(f"{p['prefix']}/sub/a.json")
    assert projects.rename_subfolder(p["id"], "sub", "Sub") == "Sub"
    assert os.listdir(p["folder"]) == ["Sub"]


def test_failed_folder_change_keeps_files_it_did_not_create():
    tmp = _setup()
    t = projects.create_project("T")
    workflows.write("one.json", WF)
    workflows.write("two.json", WF)
    projects.link_workflow(t["id"], "one.json")
    projects.link_workflow(t["id"], "two.json")
    folder = os.path.join(tmp, "TF")
    _write(os.path.join(folder, "one.json"))
    real = workflows.relocate

    def fail_on_two(old, new, root=None):
        if old == "two.json":
            raise OSError("in use")
        return real(old, new, root)

    workflows.relocate = fail_on_two
    try:
        projects.update_project(t["id"], folder=folder)
        raise AssertionError("no falló")
    except OSError:
        pass
    finally:
        workflows.relocate = real
    assert os.listdir(folder) == ["one.json"]
    assert workflows.exists("one.json") and workflows.exists("two.json")


def test_comfy_folder_is_refused_when_reached_by_another_path():
    tmp = _setup()
    workflows.write("keep.json", WF)
    root = workflows.get_root()
    other = os.path.join(tmp, "por_enlace")
    _link_dir(other, root)
    _raises("folder_forbidden", projects.create_project, "Q", folder=other)
    if os.name == "nt":
        _raises("folder_forbidden", projects.create_project, "Q", folder="\\\\?\\" + root)
        _raises("folder_forbidden", projects.create_project, "Q", folder="\\\\?\\" + os.path.join(root, "sub"))
        drive, rest = os.path.splitdrive(root)
        share = f"\\\\localhost\\{drive[0]}${rest}"
        if os.path.isdir(share):
            _raises("folder_forbidden", projects.create_project, "Q", folder=share)
    assert workflows.exists("keep.json")
    inside = projects.create_project("Dentro", folder=os.path.join(root, "dentro"))
    assert inside["prefix"] == "dentro"


def test_two_projects_cant_share_a_folder_through_another_path():
    tmp = _setup()
    p = _folder_project(tmp)
    if os.name == "nt":
        _raises("folder_in_use", projects.create_project, "Q", folder="\\\\?\\" + p["folder"])


def test_case_variants_are_one_item_where_the_disk_ignores_case():
    tmp = _setup()
    p, rel, mirror = _synced(tmp, "Foo.json")
    other = os.path.join(p["folder"], "foo.json")
    if os.name == "nt":
        os.rename(mirror, other)
        _later(other)
        tree = next(x for x in projects.tree()["projects"] if x["id"] == p["id"])
        assert [i["path"] for i in tree["items"]] == [rel]
        assert tree["items"][0]["mtime"] == os.path.getmtime(other)
        projects.update_project(p["id"], folder="")
        assert [l["workflow_ref"] for l in projects.load_db()["links"]] == [rel]


def test_project_inside_the_old_root_keeps_its_workflows():
    tmp = _setup()
    lib = os.path.join(tmp, "lib")
    _write(os.path.join(lib, "suelto.json"))
    _write(os.path.join(lib, "projA", "sub", "a.json"), '{"id": "a"}')
    save_json(config.get_db_path(), {"version": 1, "projects": [
        {"id": "p_a", "name": "A", "color": "#111111", "folder": os.path.join(lib, "projA"), "storage": "folder"},
    ], "links": []})
    real = config.legacy_root
    config.legacy_root = lambda: lib
    forgot = config.forget_legacy_root
    config.forget_legacy_root = lambda: None
    try:
        tree = projects.tree()
    finally:
        config.legacy_root = real
        config.forget_legacy_root = forgot
    a = next(x for x in tree["projects"] if x["name"] == "A")
    assert a["folder"] is None
    assert [(i["path"], i["folder"], i["exists"]) for i in a["items"]] == [("lib/projA/sub/a.json", "sub", True)]
    parent = next(x for x in tree["projects"] if x["name"] == "lib")
    assert parent["folder"] == os.path.abspath(lib)
    assert _text(os.path.join(lib, "projA", "sub", "a.json")) == '{"id": "a"}'


def test_merge_import_cant_take_over_a_prefix():
    tmp = _setup()
    p = projects.create_project("Proj", folder=os.path.join(tmp, "PF"))
    workflows.write(f"{p['prefix']}/k.json", WF)
    projects.on_saved(f"{p['prefix']}/k.json")
    projects.import_db({"projects": [{"id": "p_z", "name": "Z", "folder": os.path.join(tmp, "ZF"),
                                      "prefix": f"{p['prefix']}/sub"}], "links": []}, merge=True)
    mine = next(x for x in projects.tree()["projects"] if x["id"] == p["id"])
    assert mine["prefix"] == p["prefix"]
    assert [i["path"] for i in mine["items"]] == [f"{p['prefix']}/k.json"]


def test_non_text_project_fields_are_refused():
    _setup()
    _raises("bad_name", projects.create_project, "C", color=123)
    _raises("bad_name", projects.create_project, "C", notes=[1])
    p = projects.create_project("C")
    _raises("bad_name", projects.update_project, p["id"], color=123)
    projects.import_db(projects.export_db())


def test_import_fails_before_writing_if_a_link_blocks_it():
    tmp = _setup()
    tag = projects.create_project("Tag")
    other = projects.create_project("B")
    workflows.write("st.json", WF)
    projects.link_workflow(tag["id"], "st.json")
    workflows.remove_file("st.json")
    _raises("already_linked", projects.import_workflow, "st.json", WF, other["id"])
    assert not workflows.exists("st.json")


def test_adding_a_file_of_a_folder_project_to_another_asks_first():
    tmp = _setup()
    p, rel, _ = _synced(tmp)
    tag = projects.create_project("Tag")
    _raises("already_linked", projects.add_to_project, rel, tag["id"])
    assert not projects.load_db()["links"]
    projects.add_to_project(rel, tag["id"], allow_multi=True)
    assert [l["project_id"] for l in projects.load_db()["links"]] == [tag["id"]]


# --- Git
def _git_run(*args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True, env=env).stdout


def test_git_blocks_a_project_linked_to_comfys_repository():
    tmp = _setup()
    comfy = os.path.join(tmp, "comfy")
    os.makedirs(comfy)
    _git_run("init", comfy)
    other = os.path.join(tmp, "elsewhere")
    os.makedirs(other)
    with open(os.path.join(other, ".git"), "w", encoding="utf-8") as fh:
        fh.write("gitdir: " + os.path.join(comfy, ".git").replace("\\", "/") + "\n")
    assert git_ops.is_blocked(other, [comfy])
    _write(os.path.join(comfy, "main.py"), "x")
    _git_run("-C", comfy, "add", ".")
    _git_run("-C", comfy, "commit", "-m", "uno")
    worktree = os.path.join(tmp, "wt")
    _git_run("-C", comfy, "worktree", "add", worktree)
    assert git_ops.is_blocked(worktree, [comfy])
    own = os.path.join(tmp, "own")
    os.makedirs(own)
    _git_run("init", own)
    assert not git_ops.is_blocked(own, [comfy])


def test_git_blocks_a_folder_that_contains_comfy():
    tmp = _setup()
    parent = os.path.join(tmp, "todo")
    comfy = os.path.join(parent, "ComfyUI")
    os.makedirs(comfy)
    assert git_ops.is_blocked(parent, [comfy])


def test_opening_the_git_view_doesnt_run_index_hooks():
    tmp = _setup()
    repo = os.path.join(tmp, "repo")
    os.makedirs(repo)
    _git_run("init", repo)
    _write(os.path.join(repo, "a.json"))
    _git_run("-C", repo, "add", ".")
    _git_run("-C", repo, "commit", "-m", "uno")
    os.utime(os.path.join(repo, "a.json"), (1, 1))
    os.utime(os.path.join(repo, "a.json"))
    mark = os.path.join(tmp, "ran").replace("\\", "/")
    hook = os.path.join(repo, ".git", "hooks", "post-index-change")
    with open(hook, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f'#!/bin/sh\ntouch "{mark}"\n')
    os.chmod(hook, 0o755)
    git_ops.info(repo, [os.path.join(tmp, "comfy")])
    assert not os.path.exists(mark)


def test_git_listings_survive_unusual_characters():
    tmp = _setup()
    repo = os.path.join(tmp, "repo")
    os.makedirs(repo)
    _git_run("init", repo)
    for n, subject in enumerate(("normal", "con\x1fseparador", "con raro")):
        _write(os.path.join(repo, "a.json"), json.dumps({"id": n}))
        _git_run("-C", repo, "add", ".")
        _git_run("-C", repo, "commit", "-m", subject)
    assert [c["subject"] for c in git_ops.log(repo)] == ["con raro", "con\x1fseparador", "normal"]


def test_git_log_survives_a_strange_author():
    tmp = _setup()
    repo = os.path.join(tmp, "repo")
    os.makedirs(repo)
    _git_run("init", repo)
    _write(os.path.join(repo, "a.json"))
    _git_run("-C", repo, "add", ".")
    _git_run("-C", repo, "commit", "--author", "a\x1fb <a@b>", "-m", "uno")
    rows = git_ops.log(repo)
    assert len(rows) == 1 and rows[0]["date"] > 0


def test_common_remote_forms_are_accepted():
    for url in ("HTTPS://github.com/a/b.git", "github:equipo/b.git", "git@github.com:a/b.git", "ssh://git@host/a.git"):
        assert git_ops.validate_remote(url) == url
    for bad in ("ext::sh -c x", "-oProxyCommand=x", "--upload-pack=x", "fd::3", "a b", "x:", ":x", "c:foo"):
        _raises("git_bad_url", git_ops.validate_remote, bad)


def test_git_timeout_ends_the_command_and_its_children():
    tmp = _setup()
    mark = os.path.join(tmp, "survived").replace("\\", "/")
    code = f"import subprocess,sys,time;subprocess.Popen([sys.executable,'-c','import time;time.sleep(3);open(r\"{mark}\",\"w\")']);time.sleep(30)"
    started = time.time()
    rc, _, _ = git_ops._run([sys.executable, "-c", code], timeout=1)
    assert rc == -2 and time.time() - started < 15
    time.sleep(3.5)
    assert not os.path.exists(mark)
