# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Lo que depende del sistema: permisos, mayúsculas, enlaces simbólicos, discos desmontados, rutas de
otro sistema. Los específicos de POSIX no hacen nada en Windows."""
import json
import os
import shutil
import stat
import tempfile
import time

from _fake import fresh_env

POSIX = os.name != "nt"


def _wf(mark="x"):
    return json.dumps({"id": "11111111-1111-4111-8111-111111111111", "nodes": [], "mark": mark})


def _raises(code, fn, *args, **kw):
    from bswm.util import UserError
    try:
        fn(*args, **kw)
    except UserError as exc:
        assert exc.code == code, f"código {exc.code}, esperado {code}"
        return
    raise AssertionError(f"debería fallar con {code}")


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def _project(tree, pid):
    return next(p for p in tree["projects"] if p["id"] == pid)


def _names(tree, pid):
    return [i["path"] for i in _project(tree, pid)["items"]]


def test_written_files_have_normal_permissions():
    if not POSIX:
        return
    base = fresh_env()
    from bswm import projects, util, workflows as wf
    expected = 0o666 & ~util._UMASK
    folder = os.path.join(base, "nas", "proy")
    p = projects.create_project("proy", folder=folder)
    rel = projects.import_workflow("i.json", _wf(), p["id"])
    mirror = os.path.join(folder, "i.json")
    assert _mode(wf.abs_path(rel)) == expected and _mode(mirror) == expected
    copy = projects.duplicate_item(rel, p["id"], "", "copia")
    assert _mode(wf.abs_path(copy)) == expected
    os.chmod(mirror, 0o664)
    projects.on_saved(rel)
    assert _mode(mirror) == 0o664, "guardar conserva los permisos de la carpeta compartida"


def test_copy_keeps_the_date_and_writing_through_a_link_keeps_it():
    base = fresh_env()
    from bswm import util
    src = os.path.join(base, "a.json")
    util.write_atomic(src, b"{}")
    os.utime(src, (1000, 1000))
    dst = os.path.join(base, "b.json")
    util.copy_atomic(src, dst)
    assert abs(os.path.getmtime(dst) - 1000) < 2
    if POSIX:
        link = os.path.join(base, "enlace.json")
        os.symlink(dst, link)
        util.write_atomic(link, b'{"n":1}')
        assert os.path.islink(link)
        with open(dst, encoding="utf-8") as fh:
            assert fh.read() == '{"n":1}'


def test_names_that_differ_only_in_case_are_different_on_linux():
    if not POSIX:
        return
    base = fresh_env()
    from bswm import projects, workflows as wf
    wf.write("x/Same.json", _wf())
    wf.write("y/same.json", _wf())
    v = projects.create_project("v")
    projects.add_to_project("x/Same.json", v["id"])
    projects.add_to_project("y/same.json", v["id"])
    projects.update_project(v["id"], folder=os.path.join(base, "fuera", "v"))
    assert sorted(_names(projects.tree(), v["id"])) == ["v/Same.json", "v/same.json"]
    projects.create_project("k", folder=wf.abs_path("Clientes"))
    assert projects.create_general_folder("clientes") == "clientes"
    wf.write("Foo.json", _wf("Foo"))
    wf.write("foo.json", _wf("foo"))
    _raises("exists", projects.rename_item, "Foo.json", "foo", dry_run=True)
    assert projects.rename_item("Foo.json", "FOO")["new"] == "FOO.json", "solo mayúsculas, destino libre"


def test_folder_given_through_a_link_is_recognized():
    if not POSIX:
        return
    base = fresh_env()
    from bswm import projects, workflows as wf
    root = wf.get_root()
    inside = os.path.join(root, "real")
    os.makedirs(inside)
    link = os.path.join(base, "enlace")
    os.symlink(inside, link)
    p = projects.create_project("s", folder=link)
    assert p["prefix"] == "real" and not projects._has_mirror(p)
    alias = os.path.join(base, "alias")
    os.symlink(os.path.dirname(root), alias)
    _raises("folder_forbidden", projects.create_project, "t", folder=alias)


def test_linked_folders_are_listed_but_not_deleted_through():
    if not POSIX:
        return
    base = fresh_env()
    from bswm import projects, workflows as wf
    root = wf.get_root()
    shared = os.path.join(base, "biblioteca")
    os.makedirs(shared)
    wf.write("e.json", _wf(), root=shared)
    os.symlink(shared, os.path.join(root, "enlazada"))
    os.symlink(root, os.path.join(root, "bucle"))
    tree = projects.tree()
    assert [w["path"] for w in tree["workflows"]] == ["enlazada/e.json"], "sin dar vueltas por el bucle"
    folder = os.path.join(base, "proy")
    os.makedirs(folder)
    os.symlink(shared, os.path.join(folder, "enlace"))
    wf.write("propio.json", _wf(), root=folder)
    p = projects.create_project("p", folder=folder)
    projects.delete_project(p["id"], delete_files=True)
    assert os.path.isfile(os.path.join(shared, "e.json")), "lo enlazado no es del proyecto"
    assert not os.path.isfile(os.path.join(folder, "propio.json"))


def test_unmounted_folder_is_not_recreated():
    base = fresh_env()
    from bswm import projects, workflows as wf
    mount = os.path.join(base, "mnt", "nas", "proy")
    p = projects.create_project("nas", folder=mount)
    other = projects.create_project("otro", folder=os.path.join(base, "local", "otro"))
    wf.write("nas/x.json", _wf())
    wf.write("libre.json", _wf())
    shutil.rmtree(os.path.join(base, "mnt"))

    _raises("folder_not_found", projects.on_saved, "nas/x.json")
    projects.prepare_open("nas/x.json")
    assert projects.tree() and _names(projects.tree(), p["id"]) == ["nas/x.json"]
    projects.update_project(p["id"], color="#123456", folder=mount)
    projects.add_subfolder(p["id"], "sub")
    _raises("folder_not_found", projects.move_item, "libre.json", None, p["id"], "", dry_run=True)
    _raises("folder_not_found", projects.move_item, "nas/x.json", p["id"], other["id"], "", dry_run=True)
    _raises("folder_not_found", projects.rename_item, "nas/x.json", "y", dry_run=True)
    _raises("folder_not_found", projects.import_workflow, "n.json", _wf(), p["id"])
    assert not wf.exists("nas/n.json")
    _raises("folder_not_found", projects.duplicate_item, "libre.json", p["id"], "")
    assert not os.path.exists(os.path.join(base, "mnt")), "no debe aparecer una carpeta local vacía"


def test_folder_paths_from_another_system():
    base = fresh_env()
    from bswm import config, projects, workflows as wf
    from bswm.util import save_json
    foreign = "/mnt/nas/proyecto" if not POSIX else "C:\\proyectos\\a"
    previous = os.getcwd()
    os.chdir(base)
    try:
        save_json(config.get_db_path(), {"projects": [
            {"id": "p_w", "name": "win", "folder": foreign, "prefix": "win"},
        ], "links": []})
        wf.write("win/x.json", _wf())
        assert projects.on_saved("win/x.json") is None
        projects.prepare_open("win/x.json")
        projects.update_project("p_w", name="otro nombre", folder=foreign)
        projects.add_subfolder("p_w", "sub")
        tree = projects.tree()
        assert _names(tree, "p_w") == ["win/x.json"] and not _project(tree, "p_w")["folder_ok"]
        projects.import_db({"projects": [{"id": "p", "name": "n", "folder": foreign}], "links": []})
        _raises("folder_absolute", projects.import_db,
                {"projects": [{"id": "p", "name": "n", "folder": "relativa/x"}], "links": []})
        assert [n for n in os.listdir(base) if n in ("C:", "mnt") or n.startswith("C:")] == []
    finally:
        os.chdir(previous)


def test_damaged_database_is_set_aside_and_unreadable_one_is_not_replaced():
    fresh_env()
    from bswm import config, projects
    projects.create_project("importante")
    path = config.get_db_path()
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{ corrupta importante")
    assert projects.load_db()["projects"] == []
    kept = [n for n in os.listdir(os.path.dirname(path)) if ".corrupt-" in n]
    assert len(kept) == 1
    with open(os.path.join(os.path.dirname(path), kept[0]), encoding="utf-8") as fh:
        assert "importante" in fh.read()

    fresh_env()
    path = config.get_db_path()
    os.makedirs(path)               # simula un error de lectura, que no es "no existe"
    try:
        projects.load_db()
        raise AssertionError("debería fallar sin sustituir la BD")
    except OSError:
        pass
    os.rmdir(path)


def test_rounded_dates_on_network_disks_are_not_changes():
    base = fresh_env()
    from bswm import projects, workflows as wf
    f = projects.create_project("r", folder=os.path.join(base, "nas"))
    wf.write("r/x.json", _wf("igual"))
    projects.on_saved("r/x.json")
    general, mirror = wf.abs_path("r/x.json"), os.path.join(base, "nas", "x.json")
    now = time.time()
    os.utime(general, (now, now))
    os.utime(mirror, (now + 1, now + 1))
    projects.prepare_open("r/x.json")
    assert abs(os.path.getmtime(general) - now) < 0.01, "sin copias inútiles"
    with open(mirror, "w", encoding="utf-8") as fh:
        fh.write(_wf("cambio real de otro tamaño"))
    os.utime(mirror, (now + 1, now + 1))
    projects.prepare_open("r/x.json")
    with open(general, encoding="utf-8") as fh:
        assert "cambio real" in fh.read()


def test_git_lists_accents_and_explains_a_folder_it_refuses():
    from bswm import git_ops
    if not git_ops.detect()["git"]["available"]:
        return
    repo = tempfile.mkdtemp(prefix="bswm_acentos_")
    with open(os.path.join(repo, "café.json"), "w", encoding="utf-8") as fh:
        fh.write("{}")
    git_ops._git(repo, "init")
    assert [c["path"] for c in git_ops.status(repo)] == ["café.json"]
    assert git_ops._repo_error(repo) is None
    assert git_ops._repo_error(tempfile.mkdtemp(prefix="bswm_norepo_")) is None
    real = git_ops._git
    message = "fatal: detected dubious ownership in repository at '/nas/x'"
    git_ops._git = lambda *_a, **_k: (128, "", message)
    try:
        info = git_ops.info(repo, tempfile.gettempdir())
    finally:
        git_ops._git = real
    assert info["error"] == message and info["is_repo"] is False


def test_slow_commands_end_with_their_children():
    if not POSIX:
        return
    from bswm import git_ops
    started = time.time()
    rc, _, err = git_ops._run(["sh", "-c", "sleep 30 & sleep 30"], timeout=1)
    assert rc == -2 and "Timed out" in err and time.time() - started < 10
    rc, out, _ = git_ops._run(["sh", "-c", "test -t 0 || echo sin-terminal"])
    assert rc == 0 and "sin-terminal" in out


def test_export_folder_is_private_to_the_user():
    if not POSIX:
        return
    from bswm import exporter
    path = exporter._private_tmpdir()
    assert os.lstat(path).st_uid == os.getuid() and _mode(path) & 0o077 == 0


def test_deleting_a_linked_folder_only_removes_the_link():
    if not POSIX:
        return
    base = fresh_env()
    from bswm import projects, workflows as wf
    shared = os.path.join(base, "biblioteca")
    os.makedirs(shared)
    wf.write("e.json", _wf(), root=shared)
    os.symlink(shared, wf.abs_path("enlazada"))
    v = projects.create_project("v")
    projects.add_to_project("enlazada/e.json", v["id"])
    result = projects.delete_general_folder("enlazada")
    assert result["gone"] and result["removed"] == 0
    assert os.path.isfile(os.path.join(shared, "e.json")), "el destino del enlace queda intacto"
    assert not os.path.lexists(wf.abs_path("enlazada"))
    assert _project(projects.tree(), v["id"])["items"] == []


def test_paths_differing_in_case_belong_to_the_project_on_windows():
    if POSIX:
        return
    fresh_env()
    from bswm import projects, workflows as wf
    p = projects.create_project("MiProyecto", folder=os.path.join(tempfile.mkdtemp(prefix="bswm_git_"), "x"))
    wf.write("miproyecto/a.json", _wf())
    assert projects.on_saved("miproyecto/a.json") == "MiProyecto"
    assert all("miproyecto" not in w["path"] for w in projects.tree()["workflows"])
