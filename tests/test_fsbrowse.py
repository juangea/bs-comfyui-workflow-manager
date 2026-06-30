# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Tests de bswm.fsbrowse (explorador de carpetas del servidor; stdlib puro)."""
import os
import tempfile

from bswm import fsbrowse


def test_roots():
    r = fsbrowse.list_dir("")
    assert r["is_root_list"] is True
    assert isinstance(r["dirs"], list) and len(r["dirs"]) >= 1
    assert r["parent"] is None


def test_list_dir():
    base = tempfile.mkdtemp(prefix="bswm_fb_")
    os.makedirs(os.path.join(base, "alpha"))
    os.makedirs(os.path.join(base, "beta", "child"))
    # un archivo no debe aparecer (solo carpetas)
    with open(os.path.join(base, "note.txt"), "w") as fh:
        fh.write("x")
    d = fsbrowse.list_dir(base)
    names = [x["name"] for x in d["dirs"]]
    assert names == ["alpha", "beta"]
    assert d["is_root_list"] is False
    assert d["parent"]  # tiene padre


def test_list_dir_nonexistent():
    try:
        fsbrowse.list_dir(os.path.join(tempfile.gettempdir(), "bswm_nope_xyz"))
        raise AssertionError("debería fallar con ruta inexistente")
    except ValueError:
        pass


def test_mkdir():
    base = tempfile.mkdtemp(prefix="bswm_fb_")
    p = fsbrowse.mkdir(base, "nueva")
    assert os.path.isdir(p)
    # rechazos
    for bad in [("", "x"), (base, "a/b"), (base, ".."), (base, "")]:
        try:
            fsbrowse.mkdir(*bad)
            raise AssertionError(f"debería rechazar {bad}")
        except ValueError:
            pass
    # ya existe
    try:
        fsbrowse.mkdir(base, "nueva")
        raise AssertionError("debería rechazar duplicado")
    except ValueError:
        pass
