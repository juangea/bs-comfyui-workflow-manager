# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Integración Git opcional: detección de `git`/`gh` y operaciones en segundo plano.

Espejo del patrón de `downloads.py` del model-manager: las operaciones que pueden tardar se ejecutan
como *jobs* en un hilo worker y su estado se consulta por polling. Las lecturas son síncronas.

NUNCA instalamos git ni gh: solo invocamos los del sistema vía subprocess, siempre con lista de
argumentos (sin shell). Todo valor que llega de la red se valida antes de pasarlo a git: los remotos
se limitan a protocolos de transporte normales (git admite otros, como `ext::`, que ejecutan comandos).
"""
import os
import re
import signal
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from .util import UserError, reaches, same_path

GIT = "git"
GH = "gh"
_DETECT_TTL = 60

_ENV = {
    "GIT_TERMINAL_PROMPT": "0",            # sin credenciales guardadas: falla, no se queda esperando
    "GIT_ALLOW_PROTOCOL": "https:http:ssh:git:file",
    "GH_PROMPT_DISABLED": "1",
    "GIT_OPTIONAL_LOCKS": "0",             # consultar no reescribe el índice, ni lanza los hooks de eso
    "LC_ALL": "C",                         # mensajes en inglés: hay que poder reconocerlos
}
_REMOTE_OK = re.compile(
    r"^(?:(?i:https?|ssh|git|file)://[^\s]+"    # URL con esquema
    r"|[\w.-]+@[\w.-]+:[^\s]+"                  # git@host:ruta
    r"|[\w.-]{2,}:[^\s/][^\s]*"                 # alias de ~/.ssh/config: github:equipo/repo.git
    r"|/[^\s]*"                                 # ruta absoluta POSIX
    r"|[A-Za-z]:[\\/][^\s]*"                    # ruta absoluta Windows
    r"|\\\\[^\s]+)$"                            # recurso de red Windows
)
_COMMIT_OK = re.compile(r"^[0-9a-fA-F]{7,64}$")
_REPO_NAME_OK = re.compile(r"^[\w][\w.-]*(/[\w][\w.-]*)?$")


# ----------------------------- subprocess helpers -----------------------------
def _run(args, cwd=None, timeout=180):
    """Ejecuta un comando y devuelve (rc, stdout, stderr). rc=-1 si no existe el ejecutable."""
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        # Sin terminal: ssh no puede quedarse pidiendo la clave en la consola donde corre ComfyUI.
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(
            args, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", env={**os.environ, **_ENV}, **kwargs,
        )
    except OSError:
        return -1, "", f"Executable not found: {args[0]}"
    try:
        out, err = proc.communicate(timeout=timeout)
        return proc.returncode, out or "", err or ""
    except subprocess.TimeoutExpired:
        _kill(proc)
        return -2, "", f"Timed out: {args[0]} {args[1] if len(args) > 1 else ''}"


def _kill(proc):
    """Termina el comando y sus hijos (ssh): si no, sus tuberías seguirían abiertas y esto no acabaría.

    En Linux, primero con SIGTERM: git quita su `index.lock` al recibirlo, y si no el repositorio se queda
    bloqueado. Windows no tiene un aviso equivalente: si queda un bloqueo, git lo explica en su error.
    """
    try:
        if os.name == "nt":
            try:
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            except (OSError, subprocess.TimeoutExpired):
                pass
            proc.kill()
        else:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.communicate(timeout=5)
                return
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _git(repo, *args, **kw):
    # core.fsmonitor puede ejecutar un comando definido en la config del repo: lo desactivamos.
    # core.quotepath: sin esto, "café.json" se listaría como "caf\\303\\251.json".
    return _run([GIT, "-c", "core.fsmonitor=false", "-c", "core.quotepath=false", "-C", repo, *args], **kw)


def _first_line(text):
    return (text or "").strip().splitlines()[0] if (text or "").strip() else ""


# ----------------------------- detección -----------------------------
_detect_cache = (0.0, None)


def detect():
    """Disponibilidad y versiones de git y gh (+ si gh está autenticado). Cacheado 60 s."""
    global _detect_cache
    stamp, cached = _detect_cache
    if cached and time.time() - stamp < _DETECT_TTL:
        return cached
    rc, out, _ = _run([GIT, "--version"], timeout=15)
    git_version = _first_line(out).replace("git version ", "") if rc == 0 else None
    rc, out, _ = _run([GH, "--version"], timeout=15)
    gh_version = _first_line(out).replace("gh version ", "") if rc == 0 else None
    gh_authed = None
    if gh_version is not None:
        rc, _, _ = _run([GH, "auth", "status"], timeout=15)
        gh_authed = rc == 0
    result = {
        "git": {"available": git_version is not None, "version": git_version},
        "gh": {"available": gh_version is not None, "version": gh_version, "authed": gh_authed},
    }
    _detect_cache = (time.time(), result)
    return result


# ----------------------------- lecturas síncronas -----------------------------
def _toplevel(folder):
    """Raíz del repositorio Git que contiene `folder` (o None si no hay ninguno)."""
    if not folder or not os.path.isdir(folder):
        return None
    rc, out, _ = _git(folder, "rev-parse", "--show-toplevel")
    if rc == 0 and out.strip():
        return os.path.abspath(out.strip())
    return None


def _repo_error(folder):
    """Motivo por el que git no puede usar la carpeta, aparte de no ser un repositorio.

    Típico en Linux: una carpeta de otro usuario da "dubious ownership". Lo decide quien administra
    el equipo (`safe.directory`), así que se explica en vez de ofrecer crear un repositorio.
    """
    rc, _, err = _git(folder, "rev-parse", "--show-toplevel")
    if rc in (0, -1) or "not a git repository" in err:
        return None
    return err.strip()


def is_blocked(folder, protected):
    """True si operar aquí podría tocar el repo de ComfyUI o su propia carpeta de workflows.

    `protected`: una carpeta o varias. Si git no puede decir a qué repositorio pertenece la carpeta,
    tampoco se puede asegurar que no sea el de ComfyUI.
    """
    roots = [r for r in ([protected] if isinstance(protected, str) else protected) if r]
    # La que contiene a ComfyUI tampoco: su `git add -A` se llevaría los archivos de ComfyUI.
    if any(reaches(root, folder) or reaches(folder, root) for root in roots):
        return True
    if os.path.isdir(folder) and _repo_error(folder):
        return True
    top = _toplevel(folder)
    if top and any(reaches(top, root) for root in roots):
        return True
    # Un `.git` que es un archivo (worktree) puede apuntar al repositorio de ComfyUI desde otra carpeta.
    rc, out, _ = _git(folder, "rev-parse", "--git-common-dir") if top else (1, "", "")
    common = os.path.abspath(os.path.join(folder, out.strip())) if rc == 0 and out.strip() else None
    return bool(common and any(reaches(root, common) for root in roots))


def info(folder, protected):
    """Resumen del repo de un proyecto. `blocked`: comparte repo/carpeta con ComfyUI."""
    out = {"folder": folder, "exists": os.path.isdir(folder), "is_repo": False, "blocked": False,
           "toplevel": None, "shared_repo": False, "branch": None, "remote_url": None,
           "changes": [], "ahead": 0, "behind": 0, "error": None}
    if not out["exists"]:
        return out
    out["error"] = _repo_error(folder)
    if out["error"]:
        return out
    out["blocked"] = is_blocked(folder, protected)
    top = _toplevel(folder)
    out["toplevel"] = top
    if out["blocked"] or top is None:
        return out
    out["is_repo"] = True
    out["shared_repo"] = not same_path(top, folder)   # p. ej. un repo general de estudio
    # symbolic-ref también funciona en un repositorio recién creado, todavía sin commits.
    rc, br, _ = _git(folder, "symbolic-ref", "--short", "-q", "HEAD")
    out["branch"] = br.strip() if rc == 0 else None
    rc, url, _ = _git(folder, "remote", "get-url", "origin")
    if rc == 0 and url.strip():
        out["remote_url"] = url.strip()
    out["changes"] = status(folder)
    rc, ab, _ = _git(folder, "rev-list", "--left-right", "--count", "@{upstream}...HEAD")
    if rc == 0 and ab.strip():
        try:
            behind, ahead = ab.split()
            out["behind"], out["ahead"] = int(behind), int(ahead)
        except ValueError:
            pass
    return out


def status(folder):
    """Cambios pendientes dentro de `folder`: [{code, path}] (porcelain v1)."""
    rc, out, _ = _git(folder, "status", "--porcelain=v1", "--", ".")
    if rc != 0:
        return []
    items = []
    # split y no splitlines: esta también corta por caracteres raros que puede haber en un nombre.
    for line in out.split("\n"):
        if line.strip():
            items.append({"code": line[:2].strip(), "path": line[3:].strip().strip('"')})
    return items


def log(folder, n=50):
    """Historial de `folder`: [{hash, short, author, date(ts), subject}]."""
    sep = "\x1f"
    fmt = sep.join(["%H", "%h", "%at", "%an", "%s"])     # primero los campos fijos: lo demás lo escribe cualquiera
    rc, out, _ = _git(folder, "log", f"-n{max(1, min(int(n), 500))}", f"--pretty=format:{fmt}", "--", ".")
    if rc != 0:
        return []
    rows = []
    for line in out.split("\n"):
        parts = line.split(sep, 4)
        if len(parts) == 5:
            rows.append({"hash": parts[0], "short": parts[1], "date": float(parts[2] or 0),
                         "author": parts[3], "subject": parts[4]})
    return rows


def validate_remote(url):
    url = (url or "").strip()
    if not url or url.startswith("-") or "::" in url or not _REMOTE_OK.match(url):
        raise UserError("git_bad_url", url=url)
    return url


# ----------------------------- jobs (operaciones de escritura) -----------------------------
class _Job:
    __slots__ = ("id", "kind", "repo", "owner", "state", "log", "error", "created")

    def __init__(self, jid, kind, repo, owner=None):
        self.id = jid
        self.owner = owner
        self.kind = kind
        self.repo = repo
        self.state = "queued"   # queued | running | done | error
        self.log = ""
        self.error = ""
        self.created = time.time()

    def to_dict(self):
        return {"id": self.id, "kind": self.kind, "repo": self.repo,
                "state": self.state, "log": self.log, "error": self.error, "created": self.created}


class GitManager:
    KINDS = ("init", "commit", "remote", "push", "pull", "restore", "gh_create")

    def __init__(self):
        self._jobs = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bs-git")
        self._counter = 0

    def enqueue(self, kind, repo, owner=None, **opts):
        if kind not in self.KINDS:
            raise UserError("git_unknown_op", op=kind)
        if kind == "remote":
            opts["url"] = validate_remote(opts.get("url"))
        if kind == "restore" and not _COMMIT_OK.match(str(opts.get("commit") or "")):
            raise UserError("git_bad_commit", commit=opts.get("commit"))
        if kind == "gh_create" and not _REPO_NAME_OK.match(str(opts.get("name") or "")):
            raise UserError("git_bad_name", name=opts.get("name"))
        with self._lock:
            self._counter += 1
            jid = f"git{self._counter}"
            self._jobs[jid] = _Job(jid, kind, repo, owner)
        self._executor.submit(self._run_job, jid, opts)
        return jid

    def status(self, owner=None):
        with self._lock:
            jobs = [j for j in self._jobs.values() if owner is None or j.owner == owner]
            return [j.to_dict() for j in sorted(jobs, key=lambda j: j.created)]

    def clear_finished(self, owner=None):
        with self._lock:
            self._jobs = {k: v for k, v in self._jobs.items()
                          if v.state in ("queued", "running") or (owner is not None and v.owner != owner)}

    # -- worker --
    def _run_job(self, jid, opts):
        with self._lock:
            job = self._jobs.get(jid)
        if job is None:
            return
        job.state = "running"
        try:
            getattr(self, f"_do_{job.kind}")(job, opts)
            job.state = "done"
        except Exception as exc:  # noqa: BLE001
            job.state = "error"
            job.error = str(exc)

    def _check(self, job, rc, out, err):
        job.log = (job.log + "\n" + (out or "") + (err or "")).strip()
        if rc != 0:
            raise RuntimeError((err or out or f"git exited with {rc}").strip())

    def _ensure_identity(self, repo):
        """Configura una identidad local si no existe (git commit la exige)."""
        rc, email, _ = _git(repo, "config", "user.email")
        if rc != 0 or not email.strip():
            _git(repo, "config", "user.name", "Bone-Studio Workflow Manager")
            _git(repo, "config", "user.email", "workflow-manager@bone-studio.local")

    # -- handlers --
    def _do_init(self, job, opts):
        existed = os.path.exists(os.path.join(job.repo, ".git"))
        rc, out, err = _git(job.repo, "init")
        self._check(job, rc, out, err)
        if not existed:     # en un repositorio que ya existe, esto machacaría su rama main
            _git(job.repo, "branch", "-M", "main")
        self._ensure_identity(job.repo)
        gi = os.path.join(job.repo, ".gitignore")
        if not os.path.exists(gi):
            try:
                with open(gi, "w", encoding="utf-8") as fh:
                    fh.write("*.part\n*.tmp\n.index.json\n")
            except OSError:
                pass

    def _do_commit(self, job, opts):
        self._ensure_identity(job.repo)
        rc, out, err = _git(job.repo, "add", "-A", "--", ".")
        self._check(job, rc, out, err)
        if not status(job.repo):
            job.log = (job.log + "\nNothing to commit.").strip()
            return
        msg = (opts.get("message") or "").strip() or "Update workflows"
        rc, out, err = _git(job.repo, "commit", "-m", msg, "--", ".")
        self._check(job, rc, out, err)

    def _do_remote(self, job, opts):
        url = opts["url"]
        rc, _, _ = _git(job.repo, "remote", "get-url", "origin")
        verb = "set-url" if rc == 0 else "add"
        rc, out, err = _git(job.repo, "remote", verb, "origin", url)
        self._check(job, rc, out, err)
        job.log = (job.log + f"\norigin -> {url}").strip()

    def _do_push(self, job, opts):
        rc, out, err = _git(job.repo, "push", "-u", "origin", "HEAD", timeout=300)
        self._check(job, rc, out, err)

    def _do_pull(self, job, opts):
        rc, out, err = _git(job.repo, "pull", "--ff-only", timeout=300)
        self._check(job, rc, out, err)

    def _do_restore(self, job, opts):
        rc, out, err = _git(job.repo, "checkout", opts["commit"], "--", ".")
        self._check(job, rc, out, err)

    def _do_gh_create(self, job, opts):
        """Crea un repo en GitHub con `gh` y lo enlaza/empuja como origin."""
        visibility = "--private" if opts.get("private", True) else "--public"
        args = [GH, "repo", "create", opts["name"], visibility,
                "--source", job.repo, "--remote", "origin", "--push"]
        rc, out, err = _run(args, cwd=job.repo, timeout=300)
        self._check(job, rc, out, err)


# Instancia única usada por las rutas.
manager = GitManager()
