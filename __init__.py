# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""BS ComfyUI Workflow Manager — custom node de ComfyUI.

Gestor de workflows para producción, en una interfaz propia (pestaña en la barra lateral, dentro
de un iframe servido por este mismo add-on, para no depender del sistema de nodos y sobrevivir a
Nodes 2.0). Un solo árbol con dos secciones sobre la carpeta de workflows de ComfyUI:

  1. Workflows — explorador de carpetas: abrir, mover, renombrar, duplicar, borrar, exportar.
  2. Proyectos — capa propia (base de datos interna exportable) que agrupa workflows en proyectos
                y subcarpetas. Un proyecto puede tener carpeta propia, que recibe una copia de cada
                guardado y admite versionado Git (local o con remoto / GitHub vía `gh`).

Instalación: copia esta carpeta en ComfyUI/custom_nodes/ y reinicia ComfyUI. Solo stdlib;
las funciones Git usan el `git`/`gh` del sistema si están instalados (nunca los instalamos).
"""
import logging

# La UI se carga vía WEB_DIRECTORY (solo comfy_ext.js). La app real la sirve el backend.
WEB_DIRECTORY = "./web"

# No añadimos nodos al grafo: toda la funcionalidad vive en la interfaz propia.
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

# Registrar las rutas HTTP. Protegido para no tumbar ComfyUI si algo falla (p.ej. al testear
# este paquete fuera de ComfyUI, donde no existen `server`/`folder_paths`).
try:
    from .bswm import routes  # noqa: F401  (importar = registrar las rutas)
except Exception as exc:  # pragma: no cover
    logging.getLogger("BS_Workflow_Manager").warning(
        "[BS Workflow Manager] No se pudieron registrar las rutas HTTP: %s", exc
    )

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
