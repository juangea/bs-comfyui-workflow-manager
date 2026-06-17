# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Helper de tests: inyecta un `folder_paths` falso apuntando a un directorio temporal.

Cada llamada a `fresh_env()` crea un entorno aislado (nuevo directorio de usuario), de modo que la
configuración y la base de datos de proyectos empiezan vacías en cada test.
"""
import os
import sys
import tempfile
import types


def fresh_env():
    base = tempfile.mkdtemp(prefix="bswm_test_")
    user_dir = os.path.join(base, "user")
    os.makedirs(os.path.join(user_dir, "default", "workflows"), exist_ok=True)
    fp = types.ModuleType("folder_paths")
    fp.get_user_directory = lambda: user_dir
    sys.modules["folder_paths"] = fp
    return base
