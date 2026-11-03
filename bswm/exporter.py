# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Exportación masiva de workflows a un .zip en segundo plano.

La exportación de un único workflow se sirve como descarga directa (ver routes). Para selecciones,
proyectos o carpetas completas, se construye un .zip en una carpeta temporal como *job* (con
progreso por polling) y luego se descarga. Mismo patrón de cola/estado que `downloads.py`.
"""
import os
import stat
import tempfile
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor


def _private_tmpdir():
    """Carpeta para los .zip. En Linux /tmp se comparte con los demás usuarios: una por usuario."""
    base = tempfile.gettempdir()
    if not hasattr(os, "getuid"):
        path = os.path.join(base, "bswm_exports")
        os.makedirs(path, exist_ok=True)
        return path
    path = os.path.join(base, f"bswm_exports_{os.getuid()}")
    os.makedirs(path, mode=0o700, exist_ok=True)
    info = os.lstat(path)
    if info.st_uid != os.getuid() or stat.S_ISLNK(info.st_mode):
        return tempfile.mkdtemp(prefix="bswm_exports_")
    return path


class _Job:
    __slots__ = ("id", "name", "owner", "files", "total", "done", "state", "error", "zip_path", "created")

    def __init__(self, jid, name, files, owner=None):
        self.id = jid
        self.owner = owner
        self.name = name
        self.files = files            # lista de (abs_path, arcname)
        self.total = len(files)
        self.done = 0
        self.state = "queued"         # queued | running | done | error
        self.error = ""
        self.zip_path = None
        self.created = time.time()

    def to_dict(self):
        return {"id": self.id, "name": self.name, "total": self.total, "done": self.done,
                "state": self.state, "error": self.error,
                "ready": self.state == "done" and bool(self.zip_path), "created": self.created}


class ExportManager:
    def __init__(self):
        self._jobs = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bs-zip")
        self._counter = 0
        try:
            self._tmpdir = _private_tmpdir()
            self._purge_old()
        except OSError:     # nunca debe impedir que se cargue el resto del nodo
            self._tmpdir = tempfile.gettempdir()

    def _purge_old(self, max_age=86400):
        """Borra exportaciones de sesiones anteriores."""
        try:
            for fn in os.listdir(self._tmpdir):
                full = os.path.join(self._tmpdir, fn)
                if fn.endswith(".zip") and time.time() - os.path.getmtime(full) > max_age:
                    os.remove(full)
        except OSError:
            pass

    def enqueue(self, name, files, owner=None):
        """`files` = lista de (abs_path, arcname). `owner`: usuario de ComfyUI. Devuelve el id del job."""
        with self._lock:
            self._counter += 1
            jid = f"zip{self._counter}"
            job = _Job(jid, name or "workflows", list(files), owner)
            self._jobs[jid] = job
        self._executor.submit(self._run, jid)
        return jid

    def get(self, jid, owner=None):
        with self._lock:
            job = self._jobs.get(jid)
            return job if job and (owner is None or job.owner == owner) else None

    def status(self, owner=None):
        with self._lock:
            jobs = [j for j in self._jobs.values() if owner is None or j.owner == owner]
            return [j.to_dict() for j in sorted(jobs, key=lambda j: j.created)]

    def clear_finished(self, owner=None):
        with self._lock:
            stale = [j for j in self._jobs.values() if j.state in ("done", "error")
                     and (owner is None or j.owner == owner)]
            for j in stale:
                if j.zip_path and os.path.exists(j.zip_path):
                    try:
                        os.remove(j.zip_path)
                    except OSError:
                        pass
            self._jobs = {k: v for k, v in self._jobs.items() if v not in stale}

    def _run(self, jid):
        with self._lock:
            job = self._jobs.get(jid)
        if job is None:
            return
        job.state = "running"
        safe = "".join(c for c in job.name if c.isalnum() or c in "-_") or "workflows"
        zip_path = os.path.join(self._tmpdir, f"{safe}_{jid}.zip")
        try:
            seen = set()
            # strict_timestamps=False: un archivo con fecha anterior a 1980 no debe hacer fallar todo.
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, strict_timestamps=False) as zf:
                for abs_path, arcname in job.files:
                    if os.path.isfile(abs_path):
                        # Un nombre no UTF-8 (Linux) no se puede guardar tal cual en un zip.
                        arc = arcname.encode("utf-8", "replace").decode("utf-8")
                        # Evitar nombres duplicados dentro del zip.
                        n = 1
                        base, ext = os.path.splitext(arc)
                        while arc in seen:
                            n += 1
                            arc = f"{base} ({n}){ext}"
                        seen.add(arc)
                        zf.write(abs_path, arc)
                    job.done += 1
            job.zip_path = zip_path
            job.state = "done"
        except Exception as exc:  # noqa: BLE001
            job.state = "error"
            job.error = str(exc)
            if os.path.exists(zip_path):
                try:
                    os.remove(zip_path)
                except OSError:
                    pass


# Instancia única usada por las rutas.
manager = ExportManager()
