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
