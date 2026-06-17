# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Integración Git opcional: detección de `git`/`gh` y operaciones en segundo plano.

Espejo del patrón de `downloads.py` del model-manager: las operaciones que pueden tardar (commit,
push, pull, clone, restore, crear repo en GitHub) se ejecutan como *jobs* en un hilo worker y su
estado se consulta por polling. Las lecturas rápidas (status, log, info) son síncronas.

NUNCA instalamos git ni gh: solo invocamos los del sistema vía subprocess. Si no están, la UI
deshabilita estas funciones.
"""
import os
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

GIT = "git"
GH = "gh"


# ----------------------------- subprocess helpers -----------------------------
def _run(args, cwd=None, timeout=180, input_text=None):
    """Ejecuta un comando y devuelve (rc, stdout, stderr). rc=-1 si no existe el ejecutable."""
    try:
        proc = subprocess.run(
            args, cwd=cwd, input=input_text, timeout=timeout,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except FileNotFoundError:
        return -1, "", f"No se encontró el ejecutable: {args[0]}"
    except subprocess.TimeoutExpired:
        return -2, "", f"Tiempo de espera agotado: {' '.join(args)}"


def _git(repo, *args, **kw):
    return _run([GIT, "-C", repo, *args], **kw)


def _first_line(text):
    return (text or "").strip().splitlines()[0] if (text or "").strip() else ""


# ----------------------------- detección -----------------------------
def detect():
    """Devuelve disponibilidad y versiones de git y gh (+ si gh está autenticado)."""
    rc, out, _ = _run([GIT, "--version"])
    git_version = _first_line(out).replace("git version ", "") if rc == 0 else None

    rc, out, _ = _run([GH, "--version"])
    gh_version = _first_line(out).replace("gh version ", "") if rc == 0 else None
    gh_authed = None
    if gh_version is not None:
        rc, _, _ = _run([GH, "auth", "status"])
        gh_authed = rc == 0

    return {
        "git": {"available": git_version is not None, "version": git_version},
        "gh": {"available": gh_version is not None, "version": gh_version, "authed": gh_authed},
    }


# ----------------------------- lecturas síncronas -----------------------------
def _toplevel(repo):
    """Raíz del repositorio Git que contiene `repo` (o None si no hay ninguno)."""
    rc, out, _ = _git(repo, "rev-parse", "--show-toplevel")
    if rc == 0 and out.strip():
        return os.path.abspath(out.strip())
    return None


def _samepath(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def is_repo(repo):
    """True solo si `repo` es la RAÍZ de un repositorio Git (no si cuelga de uno ajeno)."""
    if not repo or not os.path.isdir(repo):
        return False
    top = _toplevel(repo)
    return bool(top and _samepath(top, repo))


def is_foreign(repo):
    """True si `repo` está DENTRO de un repo Git cuya raíz está por encima (p.ej. el de ComfyUI)."""
    if not repo or not os.path.isdir(repo):
        return False
    top = _toplevel(repo)
    return bool(top and not _samepath(top, repo))


def info(repo):
    """Resumen del repo. Distingue tres estados:
      - no es repo (se puede `init`),
      - es NUESTRO repo (su raíz coincide con `repo`),
      - es AJENO (`foreign`): `repo` cuelga de un repo cuya raíz está por encima (ComfyUI) → Git bloqueado.
    """
    out = {"repo": repo, "is_repo": False, "foreign": False, "toplevel": None,
           "branch": None, "remote": None, "remote_url": None,
           "changes": 0, "changes_list": [], "ahead": 0, "behind": 0}
    top = _toplevel(repo)
    out["toplevel"] = top
    if top is None:
        return out  # no es repo: se puede inicializar
    if not _samepath(top, repo):
        out["foreign"] = True
        return out  # repo ajeno (ComfyUI u otro): no tocamos nada
    out["is_repo"] = True
    rc, br, _ = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    out["branch"] = br.strip() if rc == 0 else None
    rc, url, _ = _git(repo, "remote", "get-url", "origin")
    if rc == 0 and url.strip():
        out["remote"] = "origin"
        out["remote_url"] = url.strip()
    out["changes_list"] = status(repo)
    out["changes"] = len(out["changes_list"])
    rc, ab, _ = _git(repo, "rev-list", "--left-right", "--count", "@{upstream}...HEAD")
    if rc == 0 and ab.strip():
        try:
            behind, ahead = ab.split()
            out["behind"], out["ahead"] = int(behind), int(ahead)
        except ValueError:
            pass
    return out


def status(repo):
    """Lista de cambios pendientes: [{code, path}] (porcelain v1)."""
    rc, out, _ = _git(repo, "status", "--porcelain=v1")
    if rc != 0:
        return []
    items = []
    for line in out.splitlines():
        if not line.strip():
            continue
        code, _, path = line[:2], line[2], line[3:]
        items.append({"code": code.strip() or code, "path": path.strip().strip('"')})
    return items


def log(repo, n=50, path=None):
    """Historial: [{hash, short, author, date(ts), subject}]."""
    sep = "\x1f"
    fmt = sep.join(["%H", "%h", "%an", "%at", "%s"])
    args = ["log", f"-n{int(n)}", f"--pretty=format:{fmt}"]
    if path:
        args += ["--", path]
    rc, out, _ = _git(repo, *args)
    if rc != 0:
        return []
    rows = []
    for line in out.splitlines():
        parts = line.split(sep)
        if len(parts) == 5:
            rows.append({"hash": parts[0], "short": parts[1], "author": parts[2],
                         "date": float(parts[3] or 0), "subject": parts[4]})
    return rows


# ----------------------------- jobs (operaciones de escritura) -----------------------------
class _Job:
    __slots__ = ("id", "kind", "repo", "label", "state", "log", "error", "created")

    def __init__(self, jid, kind, repo, label):
        self.id = jid
        self.kind = kind
        self.repo = repo
        self.label = label
        self.state = "queued"   # queued | running | done | error
        self.log = ""
        self.error = ""
        self.created = time.time()

    def to_dict(self):
        return {"id": self.id, "kind": self.kind, "repo": self.repo, "label": self.label,
                "state": self.state, "log": self.log, "error": self.error, "created": self.created}


class GitManager:
    def __init__(self):
        self._jobs = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bs-git")
        self._counter = 0

    def enqueue(self, kind, repo, label="", **opts):
        with self._lock:
            self._counter += 1
            jid = f"git{self._counter}"
            job = _Job(jid, kind, repo, label or kind)
            self._jobs[jid] = job
        self._executor.submit(self._run_job, jid, opts)
        return jid

    def status(self):
        with self._lock:
            return [j.to_dict() for j in sorted(self._jobs.values(), key=lambda j: j.created)]

    def clear_finished(self):
        with self._lock:
            self._jobs = {k: v for k, v in self._jobs.items() if v.state in ("queued", "running")}

    # -- worker --
    def _run_job(self, jid, opts):
        with self._lock:
            job = self._jobs.get(jid)
        if job is None:
            return
        job.state = "running"
        try:
            handler = getattr(self, f"_do_{job.kind}", None)
            if handler is None:
                raise ValueError(f"Operación Git desconocida: {job.kind}")
            # Seguridad: nunca operar dentro de un repositorio Git ajeno (p.ej. el de ComfyUI).
            if job.kind != "clone" and is_foreign(job.repo):
                raise RuntimeError(
                    "La carpeta está dentro del repositorio Git de ComfyUI. Git está "
                    "desactivado para no entrar en conflicto: define una carpeta de workflows "
                    "propia en Ajustes."
                )
            handler(job, opts)
            if job.state == "running":
                job.state = "done"
        except Exception as exc:  # noqa: BLE001
            job.state = "error"
            job.error = str(exc)

    def _check(self, job, rc, out, err, ok_msg=""):
        job.log = (job.log + "\n" + (out or "") + (err or "")).strip()
        if rc != 0:
            raise RuntimeError((err or out or f"git devolvió {rc}").strip())
        if ok_msg:
            job.log = (job.log + "\n" + ok_msg).strip()

    def _ensure_identity(self, repo, opts):
        """Configura una identidad local si no existe (git commit la exige)."""
        rc, email, _ = _git(repo, "config", "user.email")
        if rc != 0 or not email.strip():
            name = (opts.get("author_name") or "Bone-Studio Workflow Manager").strip()
            mail = (opts.get("author_email") or "workflow-manager@bone-studio.local").strip()
            _git(repo, "config", "user.name", name)
            _git(repo, "config", "user.email", mail)

    # -- handlers --
    def _do_init(self, job, opts):
        rc, out, err = _git(job.repo, "init")
        self._check(job, rc, out, err)
        _git(job.repo, "branch", "-M", opts.get("branch", "main"))
        self._ensure_identity(job.repo, opts)
        # .gitignore básico para no versionar temporales/índices internos.
        gi = os.path.join(job.repo, ".gitignore")
        if not os.path.exists(gi):
            try:
                with open(gi, "w", encoding="utf-8") as fh:
                    fh.write("*.part\n*.tmp\n.index.json\n")
            except OSError:
                pass

    def _do_commit(self, job, opts):
        self._ensure_identity(job.repo, opts)
        paths = opts.get("paths")
        if paths:
            rc, out, err = _git(job.repo, "add", "--", *paths)
        else:
            rc, out, err = _git(job.repo, "add", "-A")
        self._check(job, rc, out, err)
        msg = (opts.get("message") or "").strip() or "Update workflows"
        rc, out, err = _git(job.repo, "commit", "-m", msg)
        # "nothing to commit" no es un error real para el usuario.
        if rc != 0 and ("nothing to commit" in (out + err).lower() or "nada para hacer commit" in (out + err).lower()):
            job.log = (job.log + "\nNo hay cambios que confirmar.").strip()
            return
        self._check(job, rc, out, err)

    def _do_remote(self, job, opts):
        url = (opts.get("url") or "").strip()
        if not url:
            raise ValueError("URL de remoto vacía.")
        rc, _, _ = _git(job.repo, "remote", "get-url", "origin")
        if rc == 0:
            rc, out, err = _git(job.repo, "remote", "set-url", "origin", url)
        else:
            rc, out, err = _git(job.repo, "remote", "add", "origin", url)
        self._check(job, rc, out, err, ok_msg=f"origin → {url}")

    def _do_push(self, job, opts):
        branch = opts.get("branch")
        if not branch:
            rc, br, _ = _git(job.repo, "rev-parse", "--abbrev-ref", "HEAD")
            branch = br.strip() if rc == 0 else "main"
        rc, out, err = _git(job.repo, "push", "-u", "origin", branch, timeout=300)
        self._check(job, rc, out, err)

    def _do_pull(self, job, opts):
        rc, out, err = _git(job.repo, "pull", "--ff-only", timeout=300)
        self._check(job, rc, out, err)

    def _do_clone(self, job, opts):
        url = (opts.get("url") or "").strip()
        dest = (opts.get("dest") or "").strip()
        if not url or not dest:
            raise ValueError("Clonar requiere URL y carpeta destino.")
        rc, out, err = _run([GIT, "clone", url, dest], timeout=600)
        self._check(job, rc, out, err)

    def _do_restore(self, job, opts):
        commit = (opts.get("commit") or "").strip()
        path = (opts.get("path") or "").strip()
        if not commit:
            raise ValueError("Restaurar requiere un commit.")
        if path:
            rc, out, err = _git(job.repo, "checkout", commit, "--", path)
        else:
            rc, out, err = _git(job.repo, "checkout", commit, "--", ".")
        self._check(job, rc, out, err)

    def _do_gh_create(self, job, opts):
        """Crea un repo en GitHub con `gh` y lo enlaza/empuja como origin."""
        name = (opts.get("name") or "").strip()
        if not name:
            raise ValueError("Nombre de repositorio vacío.")
        visibility = "--private" if opts.get("private", True) else "--public"
        args = [GH, "repo", "create", name, visibility, "--source", job.repo, "--remote", "origin"]
        if opts.get("push", True):
            args.append("--push")
        rc, out, err = _run(args, cwd=job.repo, timeout=300)
        self._check(job, rc, out, err)


# Instancia única usada por las rutas.
manager = GitManager()
