# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Exportación masiva de workflows a un .zip en segundo plano.

La exportación de un único workflow se sirve como descarga directa (ver routes). Para selecciones,
proyectos o carpetas completas, se construye un .zip en una carpeta temporal como *job* (con
progreso por polling) y luego se descarga. Mismo patrón de cola/estado que `downloads.py`.
"""
import os
import tempfile
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor


class _Job:
    __slots__ = ("id", "name", "files", "total", "done", "state", "error", "zip_path", "created")

    def __init__(self, jid, name, files):
        self.id = jid
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
        self._tmpdir = os.path.join(tempfile.gettempdir(), "bswm_exports")
        os.makedirs(self._tmpdir, exist_ok=True)

    def enqueue(self, name, files):
        """`files` = lista de (abs_path, arcname). Devuelve el id del job."""
        if not files:
            raise ValueError("No hay workflows que exportar.")
        with self._lock:
            self._counter += 1
            jid = f"zip{self._counter}"
            job = _Job(jid, name or "workflows", list(files))
            self._jobs[jid] = job
        self._executor.submit(self._run, jid)
        return jid

    def get(self, jid):
        with self._lock:
            return self._jobs.get(jid)

    def status(self):
        with self._lock:
            return [j.to_dict() for j in sorted(self._jobs.values(), key=lambda j: j.created)]

    def clear_finished(self):
        with self._lock:
            stale = [j for j in self._jobs.values() if j.state in ("done", "error")]
            for j in stale:
                if j.zip_path and os.path.exists(j.zip_path):
                    try:
                        os.remove(j.zip_path)
                    except OSError:
                        pass
            self._jobs = {k: v for k, v in self._jobs.items() if v.state in ("queued", "running")}

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
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for abs_path, arcname in job.files:
                    if os.path.isfile(abs_path):
                        arc = arcname
                        # Evitar nombres duplicados dentro del zip.
                        n = 1
                        base, ext = os.path.splitext(arcname)
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
