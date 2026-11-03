# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Tests de bswm.workflows (capa de FS, con folder_paths falso)."""
import json
import os

from _fake import fresh_env


def _wf(extra=None):
    return json.dumps({"nodes": [], **(extra or {})})


def _raises(fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ValueError:
        return True
    raise AssertionError(f"debería fallar: {args!r}")


def test_write_and_list():
    fresh_env()
    from bswm import workflows as wf
    wf.write("a.json", _wf())
    wf.mkdir("clientes/pepe")
    wf.write("clientes/pepe/b.json", _wf())
    tree = wf.list_tree()
    assert sorted(w["rel"] for w in tree["workflows"]) == ["a.json", "clientes/pepe/b.json"]
    assert "clientes/pepe" in tree["folders"]


def test_write_no_overwrite():
    fresh_env()
    from bswm import workflows as wf
    wf.write("a.json", _wf())
    _raises(wf.write, "a.json", _wf())
    wf.write("a.json", _wf({"v": 2}), overwrite=True)


def test_relocate_collision():
    fresh_env()
    from bswm import workflows as wf
    wf.write("a.json", _wf())
    wf.write("dest/a.json", _wf())
    _raises(wf.relocate, "a.json", "dest/a.json")
    wf.relocate("a.json", "dest/b.json")
    assert wf.exists("dest/b.json") and not wf.exists("a.json")


def test_safe_against_traversal():
    fresh_env()
    from bswm import workflows as wf
    for bad in ["../escape.json", "..\\..\\escape.json"]:
        _raises(wf.write, bad, _wf())


def test_only_workflow_files_can_be_touched():
    base = fresh_env()
    from bswm import workflows as wf
    root = wf.get_root()
    secret = os.path.join(root, "secret.txt")
    with open(secret, "w") as fh:
        fh.write("x")
    _raises(wf.read_bytes, "secret.txt")
    _raises(wf.remove_file, "secret.txt")
    _raises(wf.relocate, "secret.txt", "moved.json")
    assert os.path.isfile(secret)


def test_move_folder():
    fresh_env()
    from bswm import workflows as wf
    wf.write("clientes/pepe/a.json", _wf())
    assert wf.move_folder("clientes/pepe", "clientes/jose") == "clientes/jose"
    assert wf.exists("clientes/jose/a.json") and not wf.exists("clientes/pepe/a.json")
    _raises(wf.move_folder, "clientes", "clientes/dentro")
    _raises(wf.move_folder, "", "x")


def test_delete_workflows_in_keeps_other_files():
    fresh_env()
    from bswm import workflows as wf
    root = wf.get_root()
    wf.write("carpeta/a.json", _wf())
    wf.write("carpeta/vacia/b.json", _wf())
    other = os.path.join(root, "carpeta", "render.png")
    with open(other, "w") as fh:
        fh.write("x")
    removed, gone = wf.delete_workflows_in("carpeta")
    assert sorted(removed) == ["carpeta/a.json", "carpeta/vacia/b.json"]
    assert gone is False
    assert os.path.isfile(other)
    assert not os.path.exists(os.path.join(root, "carpeta", "vacia"))
