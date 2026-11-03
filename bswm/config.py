# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Rutas y ajustes del Workflow Manager, por usuario de ComfyUI.

Los workflows viven SIEMPRE en la carpeta nativa de ComfyUI (`<user>/workflows`), que es la que
entiende su guardado y sus pestañas. Nuestros datos (config + BD de proyectos) están en `<user>/bswm/`.
Con `--multi-user`, el usuario de cada petición se fija con `set_request_user`.

`folder_paths` se importa de forma perezosa para poder testear este módulo sin ComfyUI (inyectando
un `folder_paths` falso en `sys.modules`).
"""
import contextvars
import os

from .util import load_json, save_json

DEFAULT_USER = "default"
DATA_SUBDIR = "bswm"

_request_user = contextvars.ContextVar("bswm_request_user", default=DEFAULT_USER)


def _fp():
    """Importa `folder_paths` (de ComfyUI) de forma perezosa."""
    import folder_paths
    return folder_paths


def set_request_user(user):
    """Fija el usuario de ComfyUI de la petición en curso."""
    return _request_user.set(user or DEFAULT_USER)


def current_user():
    return _request_user.get()


def _user_base():
    """Carpeta del usuario actual: `<user_directory>/<usuario>`."""
    fp = _fp()
    user = _request_user.get()
    getter = getattr(fp, "get_public_user_directory", None)
    base = getter(user) if getter else None
    return base or os.path.join(fp.get_user_directory(), user)


def data_dir():
    """Carpeta privada de este add-on (config + BD)."""
    return os.path.join(_user_base(), DATA_SUBDIR)


def config_path():
    return os.path.join(data_dir(), "config.json")


def comfy_workflows_root(create=True):
    """Carpeta de workflows nativa de ComfyUI: `<user>/workflows`."""
    root = os.path.abspath(os.path.join(_user_base(), "workflows"))
    if create:
        os.makedirs(root, exist_ok=True)
    return root


def comfy_code_dir():
    """Carpeta del propio ComfyUI (la de su repositorio). Puede estar lejos de `<user>/workflows`."""
    source = getattr(_fp(), "__file__", None)
    return os.path.dirname(os.path.abspath(source)) if source else None


def load():
    return load_json(config_path(), default={}) or {}


def save(cfg):
    save_json(config_path(), cfg)
    return cfg


def get_db_path():
    return os.path.abspath(load().get("db_path") or os.path.join(data_dir(), "projects.json"))


def legacy_root():
    """Raíz personalizada de versiones anteriores a la 1.1 que falta por migrar, si la hay."""
    return load().get("workflows_root")


def forget_legacy_root():
    """Se llama solo cuando la migración ya está guardada: si falla antes, se reintenta."""
    cfg = load()
    if cfg.pop("workflows_root", None) is not None:
        save(cfg)
