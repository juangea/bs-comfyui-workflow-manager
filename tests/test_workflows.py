# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Tests de bswm.workflows (capa de FS, con folder_paths falso)."""
import json
import os

from _fake import fresh_env


def _wf(extra=None):
    return json.dumps({"nodes": [], **(extra or {})})


def test_write_and_list():
    fresh_env()
    from bswm import workflows as wf
    wf.write("a.json", _wf())
    wf.mkdir("clientes/pepe")
    wf.write("clientes/pepe/b.json", _wf())
    tree = wf.list_tree()
    rels = sorted(w["rel"] for w in tree["workflows"])
    assert rels == ["a.json", "clientes/pepe/b.json"]
    assert "clientes/pepe" in tree["folders"]


def test_write_no_overwrite():
    fresh_env()
    from bswm import workflows as wf
    wf.write("a.json", _wf())
    try:
        wf.write("a.json", _wf())
        raise AssertionError("debería rechazar sobrescritura")
    except ValueError:
        pass
    wf.write("a.json", _wf({"v": 2}), overwrite=True)  # ok


def test_rename_move_duplicate_delete():
    fresh_env()
    from bswm import workflows as wf
    wf.write("a.json", _wf())
    new = wf.rename("a.json", "renamed")
    assert new == "renamed.json"
    dup = wf.duplicate("renamed.json")
    assert dup == "renamed copy.json"
    wf.mkdir("dest")
    moved = wf.move(dup, "dest")
    assert moved == "dest/renamed copy.json"
    assert wf.exists("dest/renamed copy.json")
    wf.delete("dest/renamed copy.json")
    assert not wf.exists("dest/renamed copy.json")


def test_move_collision():
    fresh_env()
    from bswm import workflows as wf
    wf.write("a.json", _wf())
    wf.mkdir("dest")
    wf.write("dest/a.json", _wf())
    try:
        wf.move("a.json", "dest")
        raise AssertionError("debería rechazar colisión")
    except ValueError:
        pass


def test_safe_against_traversal():
    fresh_env()
    from bswm import workflows as wf
    for bad in ["../escape.json", "..\\..\\escape.json"]:
        try:
            wf.write(bad, _wf())
            raise AssertionError(f"no bloqueó {bad!r}")
        except ValueError:
            pass


def test_rename_folder():
    fresh_env()
    from bswm import workflows as wf
    wf.mkdir("clientes/pepe")
    wf.write("clientes/pepe/a.json", _wf())
    new = wf.rename_folder("clientes/pepe", "jose")
    assert new == "clientes/jose"
    assert wf.exists("clientes/jose/a.json")
    assert not wf.exists("clientes/pepe/a.json")


def test_transfer_from():
    base = fresh_env()
    from bswm import workflows as wf
    # carpeta "ComfyUI" simulada como origen externo
    src = os.path.join(base, "comfy_src")
    os.makedirs(os.path.join(src, "video"), exist_ok=True)
    for rel in ["solo.json", "video/clip.json"]:
        p = os.path.join(src, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            fh.write(_wf())
    res = wf.transfer_from(src, ["solo.json", "video/clip.json"], dest_folder="importados")
    assert sorted(res["copied"]) == ["importados/solo.json", "importados/video/clip.json"]
    assert wf.exists("importados/video/clip.json")
    # repetir: ahora se omiten (ya existen)
    res2 = wf.transfer_from(src, ["solo.json"], dest_folder="importados")
    assert res2["copied"] == [] and len(res2["skipped"]) == 1
