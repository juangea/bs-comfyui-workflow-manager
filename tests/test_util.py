# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Tests de bswm.util (offline, sin ComfyUI)."""
import os

from bswm.util import (
    UserError,
    ensure_json_ext,
    is_workflow_file,
    normalize_rel,
    safe_component,
    safe_join,
)


def _raises(fn, *args):
    try:
        fn(*args)
    except ValueError:
        return True
    raise AssertionError(f"no rechazó {args!r}")


def test_user_error_has_code_and_message():
    err = UserError("exists", path="a.json")
    assert err.code == "exists" and err.params == {"path": "a.json"}
    assert "a.json" in str(err)


def test_is_workflow_file():
    assert is_workflow_file("my_workflow.json")
    assert is_workflow_file("sub/x.JSON")
    assert not is_workflow_file(".index.json")
    assert not is_workflow_file(".hidden.json")
    assert not is_workflow_file("notes.txt")
    assert not is_workflow_file("id_rsa")


def test_ensure_json_ext():
    assert ensure_json_ext("foo") == "foo.json"
    assert ensure_json_ext("foo.json") == "foo.json"
    assert ensure_json_ext("foo.JSON") == "foo.JSON"
    for bad in ["", "a/b", "a\\b", ".."]:
        _raises(ensure_json_ext, bad)


def test_normalize_rel():
    assert normalize_rel("/a//b/./c/") == "a/b/c"
    for bad in ["../x", "a/../../b"]:
        _raises(normalize_rel, bad)


def test_safe_component():
    assert safe_component('Pepe: "López"/v1') == "Pepe- -López-v1"
    assert safe_component("  ...  ") == "item"
    assert safe_component("Jacarandas") == "Jacarandas"


def test_safe_join_ok():
    root = os.path.abspath(".")
    out = safe_join(root, "sub", "a.json")
    assert out.startswith(root)
    assert out.endswith(os.path.join("sub", "a.json"))


def test_safe_join_blocks_traversal():
    root = os.path.abspath(".")
    for bad in ["../x", os.path.join("..", "..", "y"), "sub/../../z"]:
        _raises(safe_join, root, bad)


def test_safe_join_blocks_absolute():
    root = os.path.abspath(".")
    _raises(safe_join, root, os.path.abspath(os.sep + "etc"))
