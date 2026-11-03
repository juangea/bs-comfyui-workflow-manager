# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Tests de bswm.git_ops. Los que necesitan `git` se saltan si no está instalado."""
import os
import subprocess
import tempfile
import time

from bswm import git_ops
from bswm.util import UserError


def _has_git():
    return git_ops.detect()["git"]["available"]


def _init(path):
    subprocess.run(["git", "-C", path, "init"], capture_output=True)


def _wait(jid):
    for _ in range(200):
        job = next(j for j in git_ops.manager.status() if j["id"] == jid)
        if job["state"] in ("done", "error"):
            return job
        time.sleep(0.05)
    raise AssertionError("job sin terminar")


def test_remote_url_validation():
    for ok in ["https://github.com/a/b.git", "git@github.com:a/b.git", "ssh://git@host/a.git",
               "/mnt/repos/a.git", "\\\\server\\share\\a.git", "C:\\repos\\a.git"]:
        assert git_ops.validate_remote(ok) == ok
    for bad in ["ext::sh -c touch% /tmp/pwned", "--upload-pack=touch", "", "fd::3", "rel/path",
                "https://x y"]:
        try:
            git_ops.validate_remote(bad)
            raise AssertionError(f"no rechazó {bad!r}")
        except UserError:
            pass


def test_enqueue_rejects_unsafe_input():
    for kind, opts in [("clone", {}), ("nope", {}), ("restore", {"commit": "--orphan"}),
                       ("restore", {"commit": "HEAD; rm"}), ("gh_create", {"name": "--web"}),
                       ("remote", {"url": "ext::sh"})]:
        try:
            git_ops.manager.enqueue(kind, tempfile.gettempdir(), **opts)
            raise AssertionError(f"no rechazó {kind} {opts}")
        except UserError:
            pass


def test_not_a_repo():
    if not _has_git():
        return
    d = tempfile.mkdtemp(prefix="bswm_git_")
    protected = tempfile.mkdtemp(prefix="bswm_comfy_")
    info = git_ops.info(d, protected)
    assert info["is_repo"] is False and info["blocked"] is False


def test_blocks_comfy_repo_and_folder():
    if not _has_git():
        return
    comfy = tempfile.mkdtemp(prefix="bswm_comfy_")
    _init(comfy)                             # ComfyUI es un repositorio Git
    workflows = os.path.join(comfy, "user", "default", "workflows")
    inside = os.path.join(comfy, "custom", "proyecto")
    subfolder = os.path.join(workflows, "x")
    os.makedirs(subfolder)
    os.makedirs(inside)
    assert git_ops.is_blocked(workflows, workflows) is True      # su carpeta de workflows
    assert git_ops.is_blocked(subfolder, workflows) is True      # una subcarpeta de esa carpeta
    assert git_ops.is_blocked(inside, workflows) is True         # otra carpeta dentro de su repo
    assert git_ops.info(inside, workflows)["changes"] == []


def test_project_in_shared_studio_repo_is_allowed():
    if not _has_git():
        return
    comfy = tempfile.mkdtemp(prefix="bswm_comfy_")
    studio = tempfile.mkdtemp(prefix="bswm_studio_")
    _init(studio)
    project = os.path.join(studio, "pepe")
    other = os.path.join(studio, "otro")
    os.makedirs(project)
    os.makedirs(other)
    with open(os.path.join(project, "a.json"), "w") as fh:
        fh.write("{}")
    with open(os.path.join(other, "b.json"), "w") as fh:
        fh.write("{}")
    info = git_ops.info(project, comfy)
    assert info["blocked"] is False and info["is_repo"] is True and info["shared_repo"] is True
    assert [c["path"] for c in info["changes"]] and "otro" not in str(info["changes"])
    job = _wait(git_ops.manager.enqueue("commit", project, message="pepe"))
    assert job["state"] == "done", job
    rc, out, _ = git_ops._git(studio, "ls-files")
    assert "pepe/a.json" in out and "otro/b.json" not in out, "el commit debe limitarse a la carpeta"


def test_init_commit_log_restore():
    if not _has_git():
        return
    comfy = tempfile.mkdtemp(prefix="bswm_comfy_")
    repo = tempfile.mkdtemp(prefix="bswm_repo_")
    path = os.path.join(repo, "a.json")
    with open(path, "w") as fh:
        fh.write('{"v":1}')
    assert _wait(git_ops.manager.enqueue("init", repo))["state"] == "done"
    info = git_ops.info(repo, comfy)
    assert info["is_repo"] is True and info["branch"] == "main"
    assert _wait(git_ops.manager.enqueue("commit", repo, message="uno"))["state"] == "done"
    first = git_ops.log(repo)[0]
    assert first["subject"] == "uno"
    with open(path, "w") as fh:
        fh.write('{"v":2}')
    assert _wait(git_ops.manager.enqueue("commit", repo, message="dos"))["state"] == "done"
    assert _wait(git_ops.manager.enqueue("restore", repo, commit=first["hash"]))["state"] == "done"
    with open(path) as fh:
        assert fh.read() == '{"v":1}'
    done = _wait(git_ops.manager.enqueue("remote", repo, url="https://example.com/a.git"))
    assert done["state"] == "done", done
    assert git_ops.info(repo, comfy)["remote_url"] == "https://example.com/a.git"
