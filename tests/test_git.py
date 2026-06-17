# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Tests de bswm.git_ops: detección de repo propio vs ajeno (requiere `git` en el sistema).

Si git no está instalado, los tests se saltan (no fallan).
"""
import os
import subprocess
import tempfile

from bswm import git_ops


def _has_git():
    return git_ops.detect()["git"]["available"]


def test_not_a_repo():
    if not _has_git():
        return
    d = tempfile.mkdtemp(prefix="bswm_git_")
    assert git_ops.is_repo(d) is False
    assert git_ops.is_foreign(d) is False
    assert git_ops.info(d)["is_repo"] is False


def test_own_vs_foreign_repo():
    if not _has_git():
        return
    base = tempfile.mkdtemp(prefix="bswm_git_")
    subprocess.run(["git", "-C", base, "init"], capture_output=True)
    sub = os.path.join(base, "workflows")
    os.makedirs(sub, exist_ok=True)
    # La raíz es NUESTRO repo; la subcarpeta cuelga de él => ajena.
    assert git_ops.is_repo(base) is True
    assert git_ops.is_foreign(base) is False
    assert git_ops.is_repo(sub) is False
    assert git_ops.is_foreign(sub) is True
    info = git_ops.info(sub)
    assert info["foreign"] is True and info["is_repo"] is False
