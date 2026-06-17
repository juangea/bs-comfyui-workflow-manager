# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Backend de BS ComfyUI Workflow Manager.

Submódulos:
  - util       : utilidades (seguridad de rutas, formato, slug, JSON atómico).
  - config     : ajustes persistentes (raíz de workflows, ubicación de la BD).
  - workflows  : capa de sistema de archivos sobre la raíz de workflows (listar/mover/...).
  - projects   : base de datos interna exportable (proyectos, vínculos, subcarpetas, Git por proyecto).
  - git_ops    : detección de git/gh y operaciones Git en segundo plano (jobs).
  - exporter   : empaquetado a .zip en segundo plano (export masivo / proyecto / carpeta).
  - routes     : registro de rutas HTTP en el PromptServer de ComfyUI.

Todo es stdlib pura para mantener compatibilidad Python 3.10–3.13 sin instalar nada. Las funciones
Git invocan el `git`/`gh` del sistema mediante subprocess (nunca los instalamos).
"""
