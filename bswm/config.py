# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Ajustes persistentes del Workflow Manager.

Guarda un pequeño `config.json` en nuestra carpeta de datos privada dentro del directorio de
usuario de ComfyUI (`<user>/default/bswm/`). Define:
  - `workflows_root` : raíz que explora la vista General (por defecto `<user>/default/workflows`).
  - `db_path`        : ubicación de la base de datos de proyectos (por defecto en la carpeta de datos).

`folder_paths` se importa de forma perezosa para poder testear este módulo sin ComfyUI (inyectando
un `folder_paths` falso en `sys.modules`).
"""
import os

from .util import load_json, save_json

DEFAULT_USER = "default"
DATA_SUBDIR = "bswm"


def _fp():
    """Importa `folder_paths` (de ComfyUI) de forma perezosa."""
    import folder_paths
    return folder_paths


def _user_base():
    """Carpeta del usuario por defecto: `<user_directory>/default`."""
    return os.path.join(_fp().get_user_directory(), DEFAULT_USER)


def data_dir():
    """Carpeta privada de este add-on (config + BD por defecto)."""
    return os.path.join(_user_base(), DATA_SUBDIR)


def config_path():
    return os.path.join(data_dir(), "config.json")


def default_workflows_root():
    """Carpeta de workflows nativa de ComfyUI: `<user>/default/workflows`."""
    return os.path.join(_user_base(), "workflows")


def default_db_path():
    return os.path.join(data_dir(), "projects.json")


def load():
    """Devuelve el dict de configuración (con valores por defecto rellenados)."""
    cfg = load_json(config_path(), default={}) or {}
    cfg.setdefault("workflows_root", None)   # None => usar default_workflows_root()
    cfg.setdefault("db_path", None)          # None => usar default_db_path()
    cfg.setdefault("studio_repo", {})        # ajustes del repo Git "de estudio" (raíz)
    return cfg


def save(cfg):
    save_json(config_path(), cfg)
    return cfg


def get_workflows_root(create=True):
    """Ruta absoluta de la raíz de workflows efectiva (config o por defecto)."""
    cfg = load()
    root = cfg.get("workflows_root") or default_workflows_root()
    root = os.path.abspath(root)
    if create:
        os.makedirs(root, exist_ok=True)
    return root


def set_workflows_root(path):
    """Fija una nueva raíz de workflows (None/'' => volver a la de ComfyUI)."""
    cfg = load()
    path = (path or "").strip()
    if not path:
        cfg["workflows_root"] = None
    else:
        abspath = os.path.abspath(path)
        if not os.path.isdir(abspath):
            raise ValueError(f"La carpeta no existe: {abspath}")
        cfg["workflows_root"] = abspath
    return save(cfg)


def get_db_path():
    cfg = load()
    return os.path.abspath(cfg.get("db_path") or default_db_path())


def set_db_path(path):
    cfg = load()
    path = (path or "").strip()
    cfg["db_path"] = os.path.abspath(path) if path else None
    return save(cfg)
