# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Tests de bswm.util (offline, sin ComfyUI)."""
import os

from bswm.util import (
    ensure_json_ext,
    human_size,
    is_workflow_file,
    normalize_rel,
    safe_join,
    slugify,
)


def test_human_size():
    assert human_size(0) == "0 B"
    assert human_size(1536).startswith("1.5")
    assert "MB" in human_size(5_000_000)


def test_is_workflow_file():
    assert is_workflow_file("my_workflow.json")
    assert is_workflow_file("sub/x.JSON")
    assert not is_workflow_file(".index.json")
    assert not is_workflow_file(".hidden.json")
    assert not is_workflow_file("notes.txt")


def test_ensure_json_ext():
    assert ensure_json_ext("foo") == "foo.json"
    assert ensure_json_ext("foo.json") == "foo.json"
    assert ensure_json_ext("foo.JSON") == "foo.JSON"
    for bad in ["", "a/b", "a\\b"]:
        try:
            ensure_json_ext(bad)
            raise AssertionError(f"no rechazó {bad!r}")
        except ValueError:
            pass


def test_normalize_rel():
    assert normalize_rel("a\\b/c") == "a/b/c"
    assert normalize_rel("/a//b/./c/") == "a/b/c"
    for bad in ["../x", "a/../../b"]:
        try:
            normalize_rel(bad)
            raise AssertionError(f"no rechazó {bad!r}")
        except ValueError:
            pass


def test_slugify():
    assert slugify("Pepe López!") == "Pepe-L-pez"
    assert slugify("  ") == "item"


def test_safe_join_ok():
    root = os.path.abspath(".")
    out = safe_join(root, "sub", "a.json")
    assert out.startswith(root)
    assert out.endswith(os.path.join("sub", "a.json"))


def test_safe_join_blocks_traversal():
    root = os.path.abspath(".")
    for bad in ["../x", os.path.join("..", "..", "y"), "sub/../../z"]:
        try:
            safe_join(root, bad)
            raise AssertionError(f"no bloqueó: {bad!r}")
        except ValueError:
            pass


def test_safe_join_blocks_absolute():
    root = os.path.abspath(".")
    abs_part = os.path.abspath(os.sep + "etc")
    try:
        safe_join(root, abs_part)
        raise AssertionError("no bloqueó ruta absoluta")
    except ValueError:
        pass
