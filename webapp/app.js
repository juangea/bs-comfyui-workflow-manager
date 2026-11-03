// SPDX-License-Identifier: GPL-3.0-only
// Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
/* BS Workflow Manager — lógica de la mini-app (vanilla JS, sin build).
   Un único árbol con proyectos y workflows. Habla con la API JSON del backend en
   /bs_workflow_manager/api/... y con las pestañas de ComfyUI mediante window.parent.bswmBridge. */
"use strict";

const API = "/bs_workflow_manager/api";

// ---------- i18n (EN por defecto + ES) ----------
const I18N = {
  en: {
    brand_link_title: "Go to bone-studio.com",
    tab_library: "Library", tab_git: "Git", tab_settings: "Settings",
    help_title: "Help", help_tooltip: "Help", aria_language: "Language", aria_close: "Close",
    btn_cancel: "Cancel", btn_accept: "Accept", btn_confirm: "Confirm", btn_refresh: "Refresh",
    btn_save: "Save", btn_save_project: "To project…", btn_save_project_tip: "Save this workflow into a project",
    btn_clear_selection: "Clear selection", btn_clear_finished: "Clear finished",
    ph_search: "Search workflows…",
    sb_no_active: "No workflow open", sb_comfy_only: "Saves to: ComfyUI workflows",
    sb_project: "Project: {project}", sb_project_folder: "Saves to: ComfyUI + {project} folder",
    sb_unsaved: "Not saved yet", sb_no_bridge: "Open this panel from the ComfyUI sidebar",
    h_projects: "Projects", h_workflows: "Workflows",
    empty_projects: "Group the workflows of each production. Drag workflows onto a project to add them.",
    empty_workflows: "No workflows here yet.", empty_search: "Nothing matches your search.",
    empty_project: "Empty. Drag workflows here.",
    btn_new_project: "New project",
    sel_count: "{n} selected",
    ctx_open: "Open", ctx_rename: "Rename…", ctx_move: "Move to…", ctx_dup: "Duplicate…",
    ctx_addproj: "Add to project…", ctx_export: "Export", ctx_download: "Download .json", ctx_delete: "Delete",
    ctx_remove_link: "Remove from project", ctx_new_sub: "New subfolder…", ctx_new_folder: "New folder…",
    ctx_import: "Import here…", ctx_edit: "Edit project…", ctx_git: "Git…", ctx_delete_project: "Delete project…",
    ctx_export_zip: "Export as .zip", ctx_head_many: "{n} workflows", ctx_more: "More actions",
    f_new_project: "New project", f_edit_project: "Edit project", f_name: "Name", f_color: "Color", f_notes: "Notes",
    f_own_folder: "Own folder on the ComfyUI server (optional)",
    f_own_folder_hint: "If set, every save also keeps a copy in this folder. Needed for Git.",
    f_rename: "Rename", f_new_name: "New name", f_new_folder: "New folder", f_folder_name: "Folder name",
    f_new_sub: "New subfolder", f_duplicate: "Duplicate workflow", f_copy_name: "Name of the copy",
    f_destination: "Destination", f_new_sub_opt: "New subfolder inside it (optional)",
    f_move_title: "Move to…", f_addproj_title: "Add to project", f_save_project_title: "Save to project",
    warn_shared: "It's the SAME file in several projects: editing it affects all of them. Use Duplicate for an independent copy.",
    confirm_share: "{message} Share the same file with this project too?",
    btn_share: "Share", btn_browse: "Browse…",
    confirm_delete_title: "Delete", confirm_delete_one: "Delete {name}? This can't be undone.",
    confirm_delete_many: "Delete {n} workflows? This can't be undone.",
    confirm_delete_folder: "Delete the workflows inside {name}? Other files are kept.",
    confirm_remove_sub: "Remove subfolder {name}? Its workflows move to the root of the project.",
    confirm_delete_project: "Delete project {name}?",
    opt_delete_files: "Also delete its workflows from disk (other files in the folder are kept)",
    opt_delete_files_tags: "Also delete its workflows from disk (those also in another project are kept)",
    st_done: "Done.", st_saved: "Saved {name}.", st_save_cancelled: "Not saved.",
    st_close_tabs: "Close the open tabs in this folder first: {files}", st_no_bridge: "Open this panel from the ComfyUI sidebar.",
    st_folder_kept: "Workflows deleted. The folder was kept because it contains other files.",
    fb_title: "Choose a folder on the ComfyUI server", fb_roots: "Server roots", fb_new_folder: "New folder here",
    fb_select: "Select this folder", fb_up: "Up", fb_empty: "(no subfolders)", fb_new_name: "New folder name",
    lbl_git_project: "Project", git_off: "git isn't installed on the system, so Git is disabled.",
    git_ok: "git {gv}{gh}", git_gh_authed: " · gh {ghv} (signed in)", git_gh_anon: " · gh {ghv} (not signed in)",
    git_no_projects: "Git works on a project's own folder. Give a project its own folder to use it.",
    git_blocked: "This folder is inside ComfyUI's own folders or Git repository, so Git is disabled to avoid conflicts.",
    git_error: "Git can't use this folder: {detail}",
    git_not_repo: "This folder isn't a Git repository yet.", git_folder_missing: "This folder doesn't exist on the server.",
    git_shared_repo: "Part of the shared repository at {top}. Commits only include this folder.",
    git_branch: "Branch {branch}", git_ahead: "{a} to push", git_behind: "{b} to pull",
    btn_git_init: "Create repository", btn_git_commit: "Commit", btn_git_pull: "Pull", btn_git_push: "Push",
    ph_commit: "What changed?", ph_remote: "Remote URL (https://… or git@…)",
    btn_git_remote: "Set remote", btn_git_gh: "Create on GitHub", btn_restore: "Restore",
    h_changes: "Pending changes", h_history: "History", h_git_jobs: "Git operations",
    no_changes: "No pending changes.", no_history: "No commits yet.",
    f_gh_title: "Create GitHub repository", f_gh_name: "Repository name", f_gh_private: "Private",
    confirm_restore: "Restore the workflows of this folder to commit {commit}? Uncommitted changes will be lost. Files added after that commit stay in the folder.",
    state_queued: "queued", state_running: "running", state_done: "done", state_error: "error",
    job_init: "Create repository", job_commit: "Commit", job_remote: "Set remote", job_push: "Push", job_pull: "Pull", job_restore: "Restore", job_gh_create: "Create on GitHub",
    h_view_options: "View", lbl_show_linked: "Also list project workflows under \"Workflows\"",
    h_storage: "Where workflows are saved",
    storage_desc: "Always in ComfyUI's workflows folder. If the project has its own folder, a copy is kept there too.",
    h_db: "Projects database", db_desc: "A single JSON file. Export it as a backup; import it to restore or merge.",
    btn_db_export: "Export", btn_db_import: "Import…", lbl_merge: "Merge with current",
    export_ready: "Ready",
    err_exists: "Already exists: {path}", err_not_found: "Not found: {path}",
    st_tab_changed: "The active tab changed, so nothing was saved.", st_save_failed: "It couldn't be saved. ComfyUI shows the reason.",
    btn_undo: "Undo", btn_collapse: "Collapse all", st_undone: "Undone.", st_undo_cancelled: "Undo cancelled.",
    key_canvas: "Canvas", tip_canvas: "Open it", tip_canvas_legend: "Drop on the canvas to open it",
    key_drop: "Drop", tip_title: "{what} → {to}", tip_title_idle: "{what}",
    tip_legend_plain: "Move between folders of this project", tip_legend_plain_general: "Move between folders, or add to a project",
    tip_legend_ctrl: "Add to another project too", tip_legend_shift: "Move to another project, leaving this one",
    tip_move: "Move here", tip_add: "Add to {to}", tip_add_also: "Add to {to} too, it stays in {from}",
    tip_copy: "Add a copy to {to}", tip_exclusive: "Move out of {from} into {to}", tip_exclusive_only: "Move only to {to}",
    tip_takeout: "Take out of {from}", tip_folder: "Move this folder here",
    tip_here: "Already here", tip_use_keys: "Hold {ctrl} to add or Shift to move", tip_use_shift: "Hold Shift to take it out",
    tip_already: "Already in this project", tip_only_projects: "Only works on projects", tip_folder_no: "Not possible here",
    tip_new_project: "new project", tip_its_project: "its project",
    hint_move: "Move", hint_add: "Add", hint_copy: "Copy", hint_out: "Take out", hint_no: "No", hint_import: "Import",
    st_moved: "Moved {what} to {to}.", st_added: "Added {what} to {to}.", st_copied: "Copied {what} to {to}.", st_taken: "Took {what} out of {from}.",
    also_in: "Also in: {projects}", confirm_delete_shared: "It's also in other projects and will disappear from them.",
  },
  es: {
    brand_link_title: "Ir a bone-studio.com",
    tab_library: "Biblioteca", tab_git: "Git", tab_settings: "Ajustes",
    help_title: "Ayuda", help_tooltip: "Ayuda", aria_language: "Idioma", aria_close: "Cerrar",
    btn_cancel: "Cancelar", btn_accept: "Aceptar", btn_confirm: "Confirmar", btn_refresh: "Refrescar",
    btn_save: "Guardar", btn_save_project: "A proyecto…", btn_save_project_tip: "Guardar este workflow en un proyecto",
    btn_clear_selection: "Quitar selección", btn_clear_finished: "Limpiar terminadas",
    ph_search: "Buscar workflows…",
    sb_no_active: "Ningún workflow abierto", sb_comfy_only: "Se guarda en: workflows de ComfyUI",
    sb_project: "Proyecto: {project}", sb_project_folder: "Se guarda en: ComfyUI + carpeta de {project}",
    sb_unsaved: "Sin guardar todavía", sb_no_bridge: "Abre este panel desde la barra lateral de ComfyUI",
    h_projects: "Proyectos", h_workflows: "Workflows",
    empty_projects: "Agrupa los workflows de cada producción. Arrastra workflows a un proyecto para añadirlos.",
    empty_workflows: "Todavía no hay workflows aquí.", empty_search: "Nada coincide con la búsqueda.",
    empty_project: "Vacío. Arrastra workflows aquí.",
    btn_new_project: "Nuevo proyecto",
    sel_count: "{n} seleccionados",
    ctx_open: "Abrir", ctx_rename: "Renombrar…", ctx_move: "Mover a…", ctx_dup: "Duplicar…",
    ctx_addproj: "Añadir a proyecto…", ctx_export: "Exportar", ctx_download: "Descargar .json", ctx_delete: "Borrar",
    ctx_remove_link: "Quitar del proyecto", ctx_new_sub: "Nueva subcarpeta…", ctx_new_folder: "Nueva carpeta…",
    ctx_import: "Importar aquí…", ctx_edit: "Editar proyecto…", ctx_git: "Git…", ctx_delete_project: "Borrar proyecto…",
    ctx_export_zip: "Exportar como .zip", ctx_head_many: "{n} workflows", ctx_more: "Más acciones",
    f_new_project: "Nuevo proyecto", f_edit_project: "Editar proyecto", f_name: "Nombre", f_color: "Color", f_notes: "Notas",
    f_own_folder: "Carpeta propia en el servidor de ComfyUI (opcional)",
    f_own_folder_hint: "Si la indicas, cada guardado deja también una copia en esta carpeta. Es necesaria para Git.",
    f_rename: "Renombrar", f_new_name: "Nuevo nombre", f_new_folder: "Nueva carpeta", f_folder_name: "Nombre de la carpeta",
    f_new_sub: "Nueva subcarpeta", f_duplicate: "Duplicar workflow", f_copy_name: "Nombre de la copia",
    f_destination: "Destino", f_new_sub_opt: "Subcarpeta nueva dentro (opcional)",
    f_move_title: "Mover a…", f_addproj_title: "Añadir a proyecto", f_save_project_title: "Guardar en proyecto",
    warn_shared: "Es el MISMO archivo en varios proyectos: editarlo afecta a todos. Usa Duplicar para una copia independiente.",
    confirm_share: "{message} ¿Compartir el mismo archivo también con este proyecto?",
    btn_share: "Compartir", btn_browse: "Examinar…",
    confirm_delete_title: "Borrar", confirm_delete_one: "¿Borrar {name}? No se puede deshacer.",
    confirm_delete_many: "¿Borrar {n} workflows? No se puede deshacer.",
    confirm_delete_folder: "¿Borrar los workflows de {name}? Los demás archivos se conservan.",
    confirm_remove_sub: "¿Quitar la subcarpeta {name}? Sus workflows pasan a la raíz del proyecto.",
    confirm_delete_project: "¿Borrar el proyecto {name}?",
    opt_delete_files: "Borrar también sus workflows del disco (los demás archivos de la carpeta se conservan)",
    opt_delete_files_tags: "Borrar también sus workflows del disco (se conservan los que estén en otro proyecto)",
    st_done: "Hecho.", st_saved: "Guardado {name}.", st_save_cancelled: "No se ha guardado.",
    st_close_tabs: "Cierra primero las pestañas abiertas de esta carpeta: {files}", st_no_bridge: "Abre este panel desde la barra lateral de ComfyUI.",
    st_folder_kept: "Workflows borrados. La carpeta se conserva porque contiene otros archivos.",
    fb_title: "Elige una carpeta en el servidor de ComfyUI", fb_roots: "Raíces del servidor", fb_new_folder: "Nueva carpeta aquí",
    fb_select: "Seleccionar esta carpeta", fb_up: "Subir", fb_empty: "(sin subcarpetas)", fb_new_name: "Nombre de la carpeta nueva",
    lbl_git_project: "Proyecto", git_off: "git no está instalado en el sistema, así que Git está desactivado.",
    git_ok: "git {gv}{gh}", git_gh_authed: " · gh {ghv} (con sesión)", git_gh_anon: " · gh {ghv} (sin sesión)",
    git_no_projects: "Git trabaja sobre la carpeta propia de un proyecto. Asigna una carpeta propia a un proyecto para usarlo.",
    git_blocked: "Esta carpeta está dentro de las carpetas o del repositorio Git de ComfyUI, así que Git está desactivado para evitar conflictos.",
    git_error: "Git no puede usar esta carpeta: {detail}",
    git_not_repo: "Esta carpeta todavía no es un repositorio Git.", git_folder_missing: "Esta carpeta no existe en el servidor.",
    git_shared_repo: "Forma parte del repositorio compartido de {top}. Los commits solo incluyen esta carpeta.",
    git_branch: "Rama {branch}", git_ahead: "{a} por subir", git_behind: "{b} por bajar",
    btn_git_init: "Crear repositorio", btn_git_commit: "Commit", btn_git_pull: "Pull", btn_git_push: "Push",
    ph_commit: "¿Qué ha cambiado?", ph_remote: "URL del remoto (https://… o git@…)",
    btn_git_remote: "Fijar remoto", btn_git_gh: "Crear en GitHub", btn_restore: "Restaurar",
    h_changes: "Cambios pendientes", h_history: "Historial", h_git_jobs: "Operaciones Git",
    no_changes: "No hay cambios pendientes.", no_history: "Aún no hay commits.",
    f_gh_title: "Crear repositorio en GitHub", f_gh_name: "Nombre del repositorio", f_gh_private: "Privado",
    confirm_restore: "¿Restaurar los workflows de esta carpeta al commit {commit}? Se perderán los cambios sin confirmar. Los archivos añadidos después de ese commit se quedan en la carpeta.",
    state_queued: "en cola", state_running: "en curso", state_done: "hecho", state_error: "error",
    job_init: "Crear repositorio", job_commit: "Commit", job_remote: "Fijar remoto", job_push: "Push", job_pull: "Pull", job_restore: "Restaurar", job_gh_create: "Crear en GitHub",
    h_view_options: "Vista", lbl_show_linked: "Mostrar también en \"Workflows\" los workflows de proyectos",
    h_storage: "Dónde se guardan los workflows",
    storage_desc: "Siempre en la carpeta de workflows de ComfyUI. Si el proyecto tiene carpeta propia, también se guarda una copia allí.",
    h_db: "Base de datos de proyectos", db_desc: "Un único archivo JSON. Expórtalo como copia de seguridad; impórtalo para restaurar o fusionar.",
    btn_db_export: "Exportar", btn_db_import: "Importar…", lbl_merge: "Fusionar con la actual",
    export_ready: "Listo",
    st_tab_changed: "La pestaña activa ha cambiado, así que no se ha guardado nada.", st_save_failed: "No se ha podido guardar. ComfyUI indica el motivo.",
    btn_undo: "Deshacer", btn_collapse: "Contraer todo", st_undone: "Deshecho.", st_undo_cancelled: "Se ha cancelado deshacer.",
    key_canvas: "Lienzo", tip_canvas: "Abrirlo", tip_canvas_legend: "Suelta en el lienzo para abrirlo",
    err_copy_changed: "La copia ha cambiado desde entonces, así que no se ha quitado: {path}",
    key_drop: "Soltar", tip_title: "{what} → {to}", tip_title_idle: "{what}",
    tip_legend_plain: "Mover entre carpetas de este proyecto", tip_legend_plain_general: "Mover entre carpetas o añadir a un proyecto",
    tip_legend_ctrl: "Añadir también a otro proyecto", tip_legend_shift: "Mover a otro proyecto, sacándolo de este",
    tip_move: "Mover aquí", tip_add: "Añadir a {to}", tip_add_also: "Añadir también a {to}, sigue en {from}",
    tip_copy: "Añadir una copia a {to}", tip_exclusive: "Sacar de {from} y mover a {to}", tip_exclusive_only: "Mover solo a {to}",
    tip_takeout: "Sacar de {from}", tip_folder: "Mover esta carpeta aquí",
    tip_here: "Ya está aquí", tip_use_keys: "Pulsa {ctrl} para añadir o Shift para mover", tip_use_shift: "Pulsa Shift para sacarlo",
    tip_already: "Ya está en este proyecto", tip_only_projects: "Solo funciona con proyectos", tip_folder_no: "Aquí no es posible",
    tip_new_project: "proyecto nuevo", tip_its_project: "su proyecto",
    hint_move: "Mover", hint_add: "Añadir", hint_copy: "Copiar", hint_out: "Sacar", hint_no: "No", hint_import: "Importar",
    st_moved: "{what} movido a {to}.", st_added: "{what} añadido a {to}.", st_copied: "{what} copiado a {to}.", st_taken: "{what} sacado de {from}.",
    also_in: "También en: {projects}", confirm_delete_shared: "También está en otros proyectos y desaparecerá de ellos.",
    err_folder_in_use: "Esta carpeta se solapa con la del proyecto {project}: {path}",
    err_folder_has_project: "Esta carpeta se solapa con el proyecto {project}, así que no se puede cambiar aquí.",
    err_bad_json: "No es un archivo de workflow válido: {name}",
    err_bad_path: "Ruta no permitida: {path}", err_outside_root: "La ruta queda fuera de la carpeta permitida: {path}",
    err_empty_name: "El nombre no puede estar vacío.", err_bad_name: "Nombre no válido: {name}",
    err_not_workflow: "No es un archivo de workflow: {path}", err_not_found: "No encontrado: {path}",
    err_exists: "Ya existe: {path}", err_same_folder: "El origen y el destino son el mismo.",
    err_root_forbidden: "No se puede hacer sobre la carpeta raíz.", err_folder_not_found: "Carpeta no encontrada: {path}",
    err_folder_absolute: "Usa una ruta absoluta del servidor de ComfyUI: {path}", err_folder_forbidden: "Esta carpeta no se puede usar para un proyecto: {path}",
    err_folder_unusable: "No se puede usar la carpeta en el servidor: {detail}", err_project_unknown: "Proyecto desconocido.",
    err_project_name_required: "El nombre del proyecto es obligatorio.", err_project_exists: "Ya existe un proyecto llamado {name}.",
    err_already_linked: "{file} ya pertenece al proyecto {project}.", err_not_linked: "Este workflow no está vinculado a ese proyecto.",
    err_bad_db: "No es una base de datos de proyectos válida.", err_nothing_to_export: "No hay nada que exportar.",
    err_export_not_ready: "La exportación no está lista.", err_missing_field: "Falta el campo: {field}",
    err_git_missing: "git no está instalado en este sistema.", err_git_no_folder: "Git necesita un proyecto con carpeta propia.",
    err_git_blocked: "Esta carpeta está dentro de las carpetas o del repositorio Git de ComfyUI, así que Git está desactivado para evitar conflictos.",
    err_git_bad_url: "URL de remoto no permitida: {url}", err_git_bad_name: "Nombre de repositorio no válido: {name}",
    err_git_bad_commit: "Commit no válido: {commit}", err_git_unknown_op: "Operación Git desconocida: {op}", err_unknown_user: "Usuario de ComfyUI desconocido.",
  },
};

const HELP = {
  en: `
    <p><b>Bone-Studio Workflow Manager</b> keeps your production workflows organized in one tree, right next to the canvas.</p>
    <h4>Open</h4>
    <p>Click a workflow to open it. If it already has a tab, you go to that tab and keep any unsaved changes. A dot marks open tabs; amber means unsaved changes.</p>
    <h4>Save</h4>
    <p>Saving always writes to ComfyUI's workflows folder, like its own Save. If the workflow belongs to a project with its own folder, a copy is also written there. This works the same with <b>Save</b> here, the save button in the top bar, <b>File &gt; Save</b> and <code>Ctrl+S</code>.</p>
    <h4>Projects</h4>
    <p>A project without its own folder only groups workflows: files stay where they are. A project with its own folder keeps its files in <code>workflows/&lt;project&gt;</code> and in that folder, which is chosen on the ComfyUI server.</p>
    <p>A workflow in several projects is the same file, so editing it affects all of them. Colored dots show the other projects it's in. Use <b>Duplicate</b> for an independent copy.</p>
    <h4>Drag and drop</h4>
    <p>A tip shows what will happen while you drag. You can drop on a folder, a project or any workflow in the place you want.</p>
    <p><b>Without keys:</b> moves between folders of the same project, or adds a workflow from <b>Workflows</b> to a project.<br><b>Ctrl/⌘:</b> also adds it to another project, and it stays in the first one. Between two projects with their own folder, the second one gets a copy.<br><b>Shift:</b> moves it to another project and takes it out of the first one, or takes it out of the project if you drop it on <b>Workflows</b>.</p>
    <p>Drop on the <b>Projects</b> heading to create a project with those workflows. Folders can also be dragged within their project. You can drag <code>.json</code> files from your computer to import them.</p>
    <p>Drag workflows onto the canvas to open them. After a move, <b>Undo</b> or <code>Ctrl+Z</code> reverts it.</p>
    <h4>Organize</h4>
    <p>Ctrl/⌘-click and Shift-click select several workflows. Right-click for more actions. <code>↑</code> <code>↓</code> move through the list, <code>Enter</code> opens, <code>F2</code> renames, <code>Del</code> deletes.</p>
    <h4>Git</h4>
    <p>Git works on a project's own folder and needs <code>git</code> installed on the server (<code>gh</code> for creating GitHub repositories). It's disabled for folders that belong to ComfyUI or its repository.</p>
    <p class="muted">A Bone-Studio tool — <a href="https://bone-studio.com" target="_blank" rel="noopener noreferrer">bone-studio.com</a>.</p>
  `,
  es: `
    <p><b>Bone-Studio Workflow Manager</b> mantiene tus workflows de producción organizados en un solo árbol, junto al lienzo.</p>
    <h4>Abrir</h4>
    <p>Haz clic en un workflow para abrirlo. Si ya tiene pestaña, vas a esa pestaña y conservas los cambios sin guardar. Un punto marca las pestañas abiertas; en ámbar, las que tienen cambios sin guardar.</p>
    <h4>Guardar</h4>
    <p>Guardar siempre escribe en la carpeta de workflows de ComfyUI, igual que su propio Guardar. Si el workflow pertenece a un proyecto con carpeta propia, también se escribe una copia allí. Funciona igual con <b>Guardar</b> aquí, el botón de guardar de la barra superior, <b>File &gt; Save</b> y <code>Ctrl+S</code>.</p>
    <h4>Proyectos</h4>
    <p>Un proyecto sin carpeta propia solo agrupa workflows: los archivos se quedan donde están. Un proyecto con carpeta propia guarda sus archivos en <code>workflows/&lt;proyecto&gt;</code> y en esa carpeta, que se elige en el servidor de ComfyUI.</p>
    <p>Un workflow en varios proyectos es el mismo archivo, así que editarlo afecta a todos. Los puntos de color indican en qué otros proyectos está. Usa <b>Duplicar</b> para una copia independiente.</p>
    <h4>Arrastrar y soltar</h4>
    <p>Mientras arrastras, un tip indica lo que va a pasar. Puedes soltar en una carpeta, un proyecto o cualquier workflow del sitio que quieras.</p>
    <p><b>Sin teclas:</b> mueve entre carpetas del mismo proyecto, o añade a un proyecto un workflow de <b>Workflows</b>.<br><b>Ctrl/⌘:</b> lo añade también a otro proyecto y sigue en el primero. Entre dos proyectos con carpeta propia, el segundo recibe una copia.<br><b>Shift:</b> lo mueve a otro proyecto y lo saca del primero, o lo saca del proyecto si lo sueltas en <b>Workflows</b>.</p>
    <p>Suelta sobre el título <b>Proyectos</b> para crear un proyecto con esos workflows. Las carpetas también se pueden arrastrar dentro de su proyecto. Puedes arrastrar archivos <code>.json</code> desde tu equipo para importarlos.</p>
    <p>Arrastra workflows al lienzo para abrirlos. Después de un movimiento, <b>Deshacer</b> o <code>Ctrl+Z</code> lo revierte.</p>
    <h4>Organizar</h4>
    <p>Ctrl/⌘-clic y Shift-clic seleccionan varios workflows. Usa el botón derecho para más acciones. <code>↑</code> <code>↓</code> recorren la lista, <code>Enter</code> abre, <code>F2</code> renombra, <code>Supr</code> borra.</p>
    <h4>Git</h4>
    <p>Git trabaja sobre la carpeta propia de un proyecto y necesita <code>git</code> instalado en el servidor (<code>gh</code> para crear repositorios en GitHub). Está desactivado en carpetas que pertenecen a ComfyUI o a su repositorio.</p>
    <p class="muted">Una herramienta de Bone-Studio — <a href="https://bone-studio.com" target="_blank" rel="noopener noreferrer">bone-studio.com</a>.</p>
  `,
};

function storageGet(key, fallback) {
  try {
    const v = localStorage.getItem(key);
    return v === null ? fallback : v;
  } catch (e) { return fallback; }
}
function storageSet(key, value) {
  try { localStorage.setItem(key, value); } catch (e) { /* almacenamiento bloqueado */ }
}

let currentLang = storageGet("bswm_lang", "en").toLowerCase();
if (!I18N[currentLang]) currentLang = "en";

function t(key, vars) {
  let s = (I18N[currentLang] && I18N[currentLang][key]) || (I18N.en[key] != null ? I18N.en[key] : key);
  if (vars) for (const k in vars) s = s.split("{" + k + "}").join(vars[k]);
  return s;
}

// ---------- estado ----------
const state = {
  tree: { projects: [], workflows: [], folders: [], comfy_root: "" },
  config: null,
  expanded: new Set(loadJSON("bswm_expanded", ["sec:projects", "sec:workflows"])),
  selection: new Set(),
  lastClicked: null,
  order: [],                 // claves de archivos visibles, en orden (selección por rango)
  items: new Map(),          // clave -> item
  tab: { active: null, open: [], dirty: 0 },
  lastActive: null,
  lastProject: storageGet("bswm_last_project", ""),
  showLinked: storageGet("bswm_show_linked", "0") === "1",
  gitProject: null,
  openClick: 0,
  gitRefresh: 0,
  gitShown: null,
  exportPending: new Set(),
  exportTimer: null,
  gitTimer: null,
  importTarget: null,
  drag: null,                // {kind:"files", items, label} | {kind:"folder", pid, folder, label}
  dragSource: null,
  dragKey: "",
  dropNode: null,
  expandTimer: null,
  editing: false,
  renderPending: false,
  pathProjects: new Map(),   // ruta -> proyectos en los que está
  undo: null,                // movimientos que puede revertir "Deshacer"
  pressed: false,            // botón del ratón pulsado: el árbol no se repinta hasta soltarlo
};

function loadJSON(key, fallback) {
  try { return JSON.parse(storageGet(key, "")) || fallback; } catch (e) { return fallback; }
}

function bridge() {
  try {
    const b = window.parent && window.parent !== window ? window.parent.bswmBridge : null;
    return b && b.available() ? b : null;
  } catch (e) { return null; }
}

// ---------- utilidades ----------
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined && v !== false) node.setAttribute(k, v);
  }
  for (const c of children) {
    if (c == null || c === false) continue;
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return node;
}

const SVG_NS = "http://www.w3.org/2000/svg";
const ICONS = {
  chevron: "M9 6l6 6-6 6",
  folder: "M4 5h5l2 2h9a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z",
  file: "M6 3h8l5 5v12a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM14 3v5h5",
  warn: "M12 4l9 16H3L12 4zM12 10v4M12 17v.5",
  collapse: "M7 4l5 5 5-5M7 20l5-5 5 5",
};
function icon(name, cls = "t-icon") {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("class", cls);
  const path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("d", ICONS[name]);
  svg.appendChild(path);
  return svg;
}

function fmtDate(ts) {
  if (!ts) return "";
  try { return new Date(ts * 1000).toLocaleString(); } catch (e) { return ""; }
}

function matchTerms(haystack, query) {
  const terms = (query || "").toLowerCase().split(/[\s,]+/).filter(Boolean);
  if (!terms.length) return true;
  const h = String(haystack).toLowerCase();
  return terms.every((x) => h.includes(x));
}

function headers(extra) {
  const h = { ...(extra || {}) };
  const user = storageGet("Comfy.userId", "");
  if (user) h["comfy-user"] = user;
  return h;
}

async function parseResponse(r) {
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const err = new Error(data.error || `HTTP ${r.status}`);
    err.code = data.code;
    err.params = data.params;
    throw err;
  }
  return data;
}
async function getJSON(url) {
  return parseResponse(await fetch(url, { headers: headers() }));
}
async function postJSON(url, body) {
  return parseResponse(await fetch(url, {
    method: "POST",
    headers: headers({ "Content-Type": "application/json" }),
    body: JSON.stringify(body || {}),
  }));
}
function errText(e) {
  if (e && e.code && I18N[currentLang]["err_" + e.code]) return t("err_" + e.code, e.params);
  return (e && e.message) || String(e);
}

async function download(url, name) {
  const r = await fetch(url, { headers: headers() });
  if (!r.ok) await parseResponse(r);
  const blobUrl = URL.createObjectURL(await r.blob());
  const a = el("a", { href: blobUrl, download: name });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(blobUrl), 30000);
}

let statusTimer = null;
function setStatus(msg, kind = "") {
  const node = $("#status");
  node.className = "status" + (kind ? " " + kind : "");
  node.title = msg || "";
  node.replaceChildren(...(msg ? [el("span", { class: "status-text" }, msg)] : []));
  clearTimeout(statusTimer);
  if (msg && kind !== "error") statusTimer = setTimeout(() => setStatus(""), 4000);
}
function setNodeStatus(node, msg, kind = "") {
  node.className = "status" + (kind ? " " + kind : "");
  node.textContent = msg || "";
}

// Ejecuta una operación, muestra errores y refresca el árbol y las pestañas.
async function run(fn, doneMessage) {
  state.undo = null;
  try {
    const result = await fn();
    await refresh();
    setStatus(doneMessage === undefined ? t("st_done") : doneMessage, "ok");
    return result;
  } catch (e) {
    setStatus(errText(e), "error");
    await refresh().catch(() => {});
    return undefined;
  }
}

// ---------- modales ----------
let dismissActiveModal = null;

function setPageInert(value) {
  $$(".topbar, .savebar, #status, .view").forEach((n) => { n.inert = value; });
}

function openModal(title, onSubmit, okLabel, okClass) {
  // Nunca dos a la vez: el anterior se da por cancelado, y su "Aceptar" no puede quedar activo.
  if (dismissActiveModal) dismissActiveModal();
  const modal = $("#modal");
  const form = $("#modal-form");
  const ok = $("#modal-ok");
  const cancel = $("#modal-cancel");
  $("#modal-title").textContent = title;
  ok.textContent = okLabel || t("btn_accept");
  ok.className = "btn " + (okClass || "primary");
  cancel.textContent = t("btn_cancel");
  modal.classList.remove("hidden");
  const close = () => {
    modal.classList.add("hidden");
    form.removeEventListener("submit", submit);
    cancel.removeEventListener("click", dismiss);
    document.removeEventListener("keydown", onKey, true);
    dismissActiveModal = null;
    setPageInert(false);
    $("#tree").focus();
  };
  const submit = (e) => { e.preventDefault(); close(); onSubmit(true); };
  const dismiss = () => { close(); onSubmit(false); };
  const onKey = (e) => {
    // No cerrar si hay un explorador de carpetas encima.
    if (e.key === "Escape" && !$(".fb-overlay")) { e.preventDefault(); dismiss(); }
  };
  form.addEventListener("submit", submit);
  cancel.addEventListener("click", dismiss);
  document.addEventListener("keydown", onKey, true);
  dismissActiveModal = dismiss;
  setPageInert(true);
}

function showConfirm(title, message, okLabel, danger = false, extra = null) {
  closeContextMenu();
  return new Promise((resolve) => {
    const body = $("#modal-body");
    body.innerHTML = "";
    body.appendChild(el("p", { class: "modal-text" }, message));
    if (extra) body.appendChild(extra);
    openModal(title, resolve, okLabel, danger ? "danger" : "primary");
    $("#modal-cancel").focus();
  });
}

// fields: [{key,label,type,value,placeholder,options,hint}]
function showForm(title, fields, okLabel) {
  closeContextMenu();
  return new Promise((resolve) => {
    const body = $("#modal-body");
    body.innerHTML = "";
    const grid = el("div", { class: "form-grid" });
    const inputs = {};
    let first = null;

    for (const f of fields) {
      if (f.type === "text-note") { grid.appendChild(el("p", { class: "modal-text muted" }, f.text)); continue; }
      let input;
      if (f.type === "select") {
        input = el("select");
        for (const o of f.options || []) {
          const opt = el("option", { value: o.value }, o.label);
          if (o.value === f.value) opt.selected = true;
          input.appendChild(opt);
        }
      } else if (f.type === "textarea") {
        input = el("textarea", { placeholder: f.placeholder || "" });
        input.value = f.value || "";
      } else if (f.type === "checkbox") {
        input = el("input", { type: "checkbox" });
        input.checked = !!f.value;
      } else if (f.type === "color") {
        input = el("input", { type: "color" });
        input.value = f.value || "#AC1F23";
      } else {
        input = el("input", { type: "text", placeholder: f.placeholder || "" });
        input.value = f.value || "";
      }
      inputs[f.key] = input;
      if (!first && (f.type === undefined || f.type === "text" || f.type === "path")) first = input;
      let wrap;
      if (f.type === "checkbox") {
        wrap = el("label", { class: "field inline" }, input, el("span", {}, f.label));
      } else if (f.type === "path") {
        const browse = el("button", {
          class: "btn small", type: "button",
          onclick: async () => {
            const picked = await browseServerFolder(input.value.trim());
            if (picked != null) input.value = picked;
          },
        }, t("btn_browse"));
        wrap = el("div", { class: "field" }, el("span", {}, f.label), el("div", { class: "path-row" }, input, browse));
      } else {
        wrap = el("label", { class: "field" }, el("span", {}, f.label), input);
      }
      grid.appendChild(wrap);
      if (f.hint) grid.appendChild(el("div", { class: "field-hint" }, f.hint));
    }
    body.appendChild(grid);

    openModal(title, (accepted) => {
      if (!accepted) return resolve(null);
      const v = {};
      for (const f of fields) {
        const input = inputs[f.key];
        if (!input) continue;
        v[f.key] = f.type === "checkbox" ? input.checked
          : (f.type === "select" || f.type === "color") ? input.value : input.value.trim();
      }
      resolve(v);
    }, okLabel);
    if (first) { first.focus(); first.select(); }
  });
}

// Selector de destino: un único desplegable con proyectos, subcarpetas y carpetas de Workflows.
function destinationOptions({ projectsOnly = false } = {}) {
  const opts = [];
  const indent = (depth) => "   ".repeat(depth);
  const addFolders = (pid, folders) => {
    for (const f of [...folders].sort((a, b) => a.localeCompare(b))) {
      const parts = f.split("/");
      opts.push({ value: JSON.stringify([pid, f]), label: indent(parts.length) + parts[parts.length - 1] });
    }
  };
  for (const p of state.tree.projects) {
    opts.push({ value: JSON.stringify([p.id, ""]), label: "● " + p.name });
    addFolders(p.id, p.subfolders);
  }
  if (!projectsOnly) {
    opts.push({ value: JSON.stringify([null, ""]), label: t("h_workflows") });
    addFolders(null, state.tree.folders);
  }
  return opts;
}
function destinationFields(value, options) {
  return [
    { key: "dest", label: t("f_destination"), type: "select", value, options: destinationOptions(options) },
    { key: "new_sub", label: t("f_new_sub_opt"), type: "text", value: "" },
  ];
}
function readDestination(v) {
  const [pid, folder] = JSON.parse(v.dest);
  const sub = (v.new_sub || "").replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
  return { pid, folder: sub ? (folder ? folder + "/" + sub : sub) : folder };
}
function defaultDestination(projectsOnly) {
  const p = state.tree.projects.find((x) => x.id === state.lastProject) || state.tree.projects[0];
  if (p) return JSON.stringify([p.id, ""]);
  return projectsOnly ? "" : JSON.stringify([null, ""]);
}

// ---------- ayuda ----------
function openHelp() {
  $("#help-title").textContent = t("help_title");
  $("#help-body").innerHTML = HELP[currentLang] || HELP.en;
  $("#help-modal").classList.remove("hidden");
  setPageInert(true);
}
function closeHelp() {
  $("#help-modal").classList.add("hidden");
  setPageInert(false);
  $("#tree").focus();
}

// ---------- explorador de carpetas del SERVIDOR ----------
function browseServerFolder(startPath) {
  return new Promise((resolve) => {
    const overlay = el("div", { class: "modal fb-overlay" });
    const card = el("div", { class: "modal-card fb-card" });
    overlay.appendChild(card);
    document.body.appendChild(overlay);
    let cur = startPath || "";
    $("#modal").inert = true;
    const close = (val) => {
      overlay.remove();
      $("#modal").inert = false;
      document.removeEventListener("keydown", onKey, true);
      resolve(val);
    };
    const onKey = (e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(null); } };
    document.addEventListener("keydown", onKey, true);

    const render = async () => {
      let data;
      try {
        data = await getJSON(`${API}/fs/list?path=${encodeURIComponent(cur)}`);
      } catch (e) {
        cur = "";
        try { data = await getJSON(`${API}/fs/list?path=`); }
        catch (e2) {
          card.replaceChildren(el("div", { class: "modal-body" }, errText(e2)), el("div", { class: "modal-actions" },
            el("button", { class: "btn", type: "button", onclick: () => close(null) }, t("btn_cancel"))));
          return;
        }
      }
      card.innerHTML = "";
      card.appendChild(el("div", { class: "modal-title" }, t("fb_title")));
      const head = el("div", { class: "fb-head" },
        el("span", { class: "fb-path" }, data.is_root_list ? t("fb_roots") : data.path));
      if (!data.is_root_list) {
        head.appendChild(el("button", { class: "btn small", type: "button", onclick: () => { cur = data.parent || ""; render(); } }, "↑ " + t("fb_up")));
      }
      card.appendChild(head);

      const list = el("div", { class: "fb-list" });
      if (!data.dirs.length) list.appendChild(el("div", { class: "muted", style: "padding:8px" }, t("fb_empty")));
      for (const d of data.dirs) {
        list.appendChild(el("div", { class: "fb-row", onclick: () => { cur = d.path; render(); } },
          icon("folder"), el("span", { class: "grow" }, d.name)));
      }
      card.appendChild(list);

      if (!data.is_root_list) {
        const newInput = el("input", { type: "text", placeholder: t("fb_new_name") });
        card.appendChild(el("div", { class: "fb-newrow" }, newInput,
          el("button", {
            class: "btn small", type: "button",
            onclick: async () => {
              const name = newInput.value.trim();
              if (!name) return;
              try {
                const res = await postJSON(`${API}/fs/mkdir`, { path: data.path, name });
                cur = res.path;
                render();
              } catch (e) { setNodeStatus(errNode, errText(e), "error"); }
            },
          }, t("fb_new_folder"))));
      }
      const errNode = el("div", { class: "status" });
      card.appendChild(errNode);
      const selBtn = el("button", { class: "btn primary", type: "button", onclick: () => close(data.path || null) }, t("fb_select"));
      if (data.is_root_list) selBtn.disabled = true;
      card.appendChild(el("div", { class: "modal-actions" },
        el("button", { class: "btn", type: "button", onclick: () => close(null) }, t("btn_cancel")), selBtn));
    };
    render();
  });
}

// ---------- menú contextual ----------
function closeContextMenu() {
  if (window.__ctx) { window.__ctx.remove(); window.__ctx = null; }
}
// items: [{label, danger, onClick} | {sep:true} | {head:"..."}]
function showContextMenu(x, y, items) {
  closeContextMenu();
  const menu = el("div", { class: "ctx-menu", role: "menu" });
  for (const it of items) {
    if (!it) continue;
    if (it.sep) { menu.appendChild(el("div", { class: "ctx-sep" })); continue; }
    if (it.head) { menu.appendChild(el("div", { class: "ctx-head" }, it.head)); continue; }
    menu.appendChild(el("div", {
      class: "ctx-item" + (it.danger ? " danger" : ""), role: "menuitem",
      onclick: () => { closeContextMenu(); it.onClick(); },
    }, it.label));
  }
  document.body.appendChild(menu);
  const r = menu.getBoundingClientRect();
  menu.style.left = Math.max(4, Math.min(x, window.innerWidth - r.width - 8)) + "px";
  menu.style.top = Math.max(4, Math.min(y, window.innerHeight - r.height - 8)) + "px";
  window.__ctx = menu;
}
document.addEventListener("click", closeContextMenu);
document.addEventListener("scroll", (e) => {
  if (!(window.__ctx && window.__ctx.contains(e.target))) closeContextMenu();
}, true);
window.addEventListener("blur", closeContextMenu);
window.addEventListener("resize", closeContextMenu);

// ============================================================
//  ÁRBOL
// ============================================================
function saveExpanded() {
  storageSet("bswm_expanded", JSON.stringify([...state.expanded]));
}
function toggleExpanded(key) {
  if (state.expanded.has(key)) state.expanded.delete(key); else state.expanded.add(key);
  saveExpanded();
  renderTree();
}

function makeRow({ cls, depth, label, sub, leading, twisty, open, trailing, onclick, onmenu, title }) {
  const row = el("div", { class: "t-row " + (cls || "") + (open ? " open" : ""), style: `--depth:${depth}`, title: title || null });
  row.appendChild(twisty ? el("span", { class: "t-twisty" }, icon("chevron", "")) : el("span", { class: "t-twisty" }));
  if (leading) row.appendChild(leading);
  row.appendChild(el("span", { class: "t-name" }, sub ? el("span", { class: "t-sub" }, sub) : null, label));
  for (const node of trailing || []) if (node) row.appendChild(node);
  if (onclick) row.addEventListener("click", onclick);
  if (onmenu) {
    row.addEventListener("contextmenu", (e) => { e.preventDefault(); e.stopPropagation(); onmenu(e.clientX, e.clientY); });
    row.appendChild(el("button", {
      class: "t-more", type: "button", title: t("ctx_more"), "aria-label": t("ctx_more"),
      onclick: (e) => {
        e.stopPropagation();
        const r = e.currentTarget.getBoundingClientRect();
        onmenu(r.left, r.bottom);
      },
    }, "⋯"));
  }
  return row;
}

function fileRow(item, depth, showFolder) {
  const key = item.key;
  state.items.set(key, item);
  state.order.push(key);
  const marks = [el("span", { class: "t-tab" })];
  const others = (state.pathProjects.get(item.path) || []).filter((p) => p.id !== item.pid);
  if (others.length) {
    const title = t("also_in", { projects: others.map((p) => p.name).join(", ") }) + " " + t("warn_shared");
    for (const p of others) marks.push(el("span", { class: "t-mini-dot", style: `background:${p.color}`, title }));
  }
  const row = makeRow({
    cls: "file" + (item.exists === false ? " missing" : ""),
    depth,
    label: item.name.replace(/\.json$/i, ""),
    sub: showFolder && item.folder ? item.folder + "/" : null,
    leading: icon("file"),
    trailing: marks,
    title: item.path,
    onclick: (e) => onFileClick(e, item),
    onmenu: (x, y) => fileMenu(x, y, item),
  });
  row.dataset.key = key;
  row.dataset.path = item.path;
  row.__drop = { pid: item.pid, folder: item.folder };
  row.setAttribute("draggable", "true");
  row.__dragData = () => {
    if (!state.selection.has(key)) {
      state.selection = new Set([key]);
      state.lastClicked = key;
      updateSelectionUI();
    }
    const items = [...state.selection].map((k) => state.items.get(k)).filter(Boolean);
    return { kind: "files", items, label: whatLabel(items) };
  };
  row.addEventListener("dragstart", (e) => {
    if (state.editing) return;      // es el texto del campo de renombrar, no la fila
    beginDrag(e, row.__dragData(), row);
  });
  return row;
}

// Pinta un nivel (carpetas + archivos) de un proyecto o de "Workflows".
function renderLevel(box, ctx, folder, depth, query) {
  const prefix = folder ? folder + "/" : "";
  const children = new Set();
  for (const f of ctx.folders) {
    if (f.startsWith(prefix)) {
      const first = f.slice(prefix.length).split("/")[0];
      if (first) children.add(prefix + first);
    }
  }
  const countIn = (path) => ctx.files.filter((i) => i.folder === path || i.folder.startsWith(path + "/")).length;
  for (const f of [...children].sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()))) {
    const n = countIn(f);
    if (query && !n) continue;
    const key = `${ctx.key}/${f}`;
    const open = query ? true : state.expanded.has(key);
    const target = { pid: ctx.pid, folder: f };
    const row = makeRow({
      cls: "folder", depth, label: f.split("/").pop(), leading: icon("folder"), twisty: true, open,
      trailing: [n ? el("span", { class: "t-count" }, String(n)) : null],
      onclick: () => { if (!query) toggleExpanded(key); },
      onmenu: (x, y) => folderMenu(x, y, ctx, f),
    });
    row.__drop = target;
    if (!open && !query) row.__expand = key;
    row.dataset.folderKey = key;
    row.setAttribute("draggable", "true");
    row.__dragData = () => ({ kind: "folder", pid: ctx.pid, folder: f, label: f.split("/").pop() });
    row.addEventListener("dragstart", (e) => {
      if (state.editing) return;
      beginDrag(e, row.__dragData(), row);
    });
    box.appendChild(row);
    if (open) renderLevel(box, ctx, f, depth + 1, query);
  }
  for (const item of ctx.files) {
    if (item.folder === folder) box.appendChild(fileRow(item, depth, false));
  }
}

function renderTree() {
  // Repintar entre pulsar y soltar perdería el clic o el arrastre de la fila que se está pulsando.
  if (state.editing || state.pressed) { state.renderPending = true; return; }
  const box = $("#tree");
  const scroll = box.scrollTop;
  // El navegador pierde el fin del arrastre si desaparece su origen: se conserva oculto hasta entonces.
  const source = state.drag ? state.dragSource : null;
  for (const child of [...box.children]) {
    if (child === source) child.classList.add("hidden");
    else child.remove();
  }
  state.dropNode = null;
  state.dragKey = "";
  state.items = new Map();
  state.order = [];
  state.pathProjects = new Map();
  for (const p of state.tree.projects) {
    for (const i of p.items) {
      if (!state.pathProjects.has(i.path)) state.pathProjects.set(i.path, []);
      state.pathProjects.get(i.path).push(p);
    }
  }
  const query = $("#search").value.trim();
  const keep = (i) => !query || matchTerms(i.path, query);

  // --- Proyectos ---
  const secP = state.expanded.has("sec:projects") || !!query;
  const secPRow = makeRow({
    cls: "t-section", depth: 0, label: t("h_projects"), twisty: true, open: secP,
    trailing: [el("button", {
      class: "t-more t-add", type: "button", title: t("btn_new_project"), "aria-label": t("btn_new_project"),
      onclick: (e) => { e.stopPropagation(); projectForm(null); },
    }, "+")],
    onclick: () => { if (!query) toggleExpanded("sec:projects"); },
  });
  secPRow.__drop = { newProject: true, folder: "" };
  if (!secP) secPRow.__expand = "sec:projects";
  box.appendChild(secPRow);
  if (secP) {
    if (!state.tree.projects.length && !query) {
      const empty = el("div", { class: "t-empty" }, t("empty_projects"),
        el("button", { class: "btn small primary", type: "button", onclick: () => projectForm(null) }, t("btn_new_project")));
      empty.__drop = { newProject: true, folder: "" };
      box.appendChild(empty);
    }
    for (const p of state.tree.projects) {
      const nameMatch = query && matchTerms(p.name, query);
      const files = p.items
        .map((i) => ({ ...i, pid: p.id, key: `p:${p.id}:${i.path}` }))
        .filter((i) => nameMatch || keep(i));
      if (query && !nameMatch && !files.length) continue;
      const key = `p:${p.id}`;
      const open = query ? true : state.expanded.has(key);
      const trailing = [];
      if (p.folder && !p.folder_ok) trailing.push(el("span", { class: "t-badge warn", title: p.folder }, icon("warn", "")));
      else if (p.folder) trailing.push(el("span", { class: "t-badge", title: p.folder }, icon("folder", "")));
      trailing.push(el("span", { class: "t-count" }, String(p.items.length)));
      const row = makeRow({
        cls: "t-project", depth: 0, label: p.name, twisty: true, open,
        leading: el("span", { class: "t-dot", style: `background:${p.color}` }),
        trailing, title: p.notes || null,
        onclick: () => { rememberProject(p.id); if (!query) toggleExpanded(key); },
        onmenu: (x, y) => projectMenu(x, y, p),
      });
      row.__drop = { pid: p.id, folder: "" };
      if (!open && !query) row.__expand = key;
      box.appendChild(row);
      if (open) {
        const before = box.childElementCount;
        renderLevel(box, { key, pid: p.id, folders: p.subfolders, files }, "", 1, query);
        if (box.childElementCount === before) {
          const empty = el("div", { class: "t-empty" }, t("empty_project"));
          empty.__drop = { pid: p.id, folder: "" };
          box.appendChild(empty);
        }
      }
    }
  }

  // --- Workflows ---
  const secW = state.expanded.has("sec:workflows") || !!query;
  const wfs = state.tree.workflows
    .filter((w) => state.showLinked || !w.projects.length)
    .map((w) => ({ ...w, pid: null, key: `g:${w.path}` }))
    .filter(keep);
  const secRow = makeRow({
    cls: "t-section", depth: 0, label: t("h_workflows"), twisty: true, open: secW,
    trailing: [
      el("span", { class: "t-count" }, String(wfs.length)),
      el("button", {
        class: "t-more t-add", type: "button", title: t("f_new_folder"), "aria-label": t("f_new_folder"),
        onclick: (e) => { e.stopPropagation(); newFolderIn(null, ""); },
      }, "+"),
    ],
    onclick: () => { if (!query) toggleExpanded("sec:workflows"); },
    onmenu: (x, y) => workflowsMenu(x, y),
  });
  secRow.__drop = { pid: null, folder: "" };
  if (!secW) secRow.__expand = "sec:workflows";
  box.appendChild(secRow);
  if (secW) {
    const before = box.childElementCount;
    renderLevel(box, { key: "g", pid: null, folders: state.tree.folders, files: wfs }, "", 1, query);
    if (box.childElementCount === before) {
      const empty = el("div", { class: "t-empty" }, query ? t("empty_search") : t("empty_workflows"));
      empty.__drop = { pid: null, folder: "" };
      box.appendChild(empty);
    }
  }

  // La selección solo conserva lo que sigue existiendo.
  state.selection = new Set([...state.selection].filter((k) => state.items.has(k)));
  box.scrollTop = scroll;
  updateSelectionUI();
  updateTabMarks();
}

function flushRender() {
  if (state.renderPending && !state.editing && !state.pressed) {
    state.renderPending = false;
    renderTree();
  }
}

function updateSelectionUI() {
  $$(".t-row.file").forEach((r) => r.classList.toggle("selected", state.selection.has(r.dataset.key)));
  const n = state.selection.size;
  $("#selbar").classList.toggle("hidden", n < 2);
  $("#sel-count").textContent = t("sel_count", { n });
}

function updateTabMarks() {
  const open = new Map(state.tab.open.map((o) => [o.rel, o]));
  const active = state.tab.active && state.tab.active.rel;
  $$(".t-row.file").forEach((r) => {
    const tab = open.get(r.dataset.path);
    r.classList.toggle("tab-open", !!tab);
    r.classList.toggle("tab-modified", !!(tab && tab.modified));
    r.classList.toggle("active", r.dataset.path === active);
  });
}

function rememberProject(pid) {
  state.lastProject = pid;
  storageSet("bswm_last_project", pid);
}

// Proyecto al que pertenece una ruta. Si está compartida, el que tiene el archivo en su carpeta.
function projectOfPath(path) {
  const owners = state.tree.projects.filter((p) => p.items.some((i) => i.path === path));
  return owners.find((p) => p.folder) || owners[0] || null;
}

// Expande y muestra el workflow activo cuando cambia de pestaña.
function revealPath(path) {
  const p = projectOfPath(path);
  let changed = false;
  const expand = (k) => { if (!state.expanded.has(k)) { state.expanded.add(k); changed = true; } };
  let folder = "";
  if (p) {
    rememberProject(p.id);
    expand("sec:projects");
    expand(`p:${p.id}`);
    folder = (p.items.find((i) => i.path === path) || {}).folder || "";
    const parts = folder ? folder.split("/") : [];
    parts.forEach((_, i) => expand(`p:${p.id}/${parts.slice(0, i + 1).join("/")}`));
  } else if (state.tree.workflows.some((w) => w.path === path)) {
    expand("sec:workflows");
    const parts = path.split("/").slice(0, -1);
    parts.forEach((_, i) => expand(`g/${parts.slice(0, i + 1).join("/")}`));
  }
  if (changed) { saveExpanded(); renderTree(); }
  const row = $$(".t-row.file").find((r) => r.dataset.path === path);
  if (row) row.scrollIntoView({ block: "nearest" });
}

// ---------- clics ----------
function onFileClick(e, item) {
  const key = item.key;
  if (state.skipClick === key) return;    // ese clic solo ha cerrado el campo de renombrar
  if (e.shiftKey && state.lastClicked && state.order.includes(state.lastClicked)) {
    const a = state.order.indexOf(state.lastClicked);
    const b = state.order.indexOf(key);
    const [lo, hi] = a < b ? [a, b] : [b, a];
    if (!(e.ctrlKey || e.metaKey)) state.selection.clear();
    for (let i = lo; i <= hi; i++) state.selection.add(state.order[i]);
    updateSelectionUI();
    return;
  }
  if (e.ctrlKey || e.metaKey) {
    if (state.selection.has(key)) state.selection.delete(key); else state.selection.add(key);
    state.lastClicked = key;
    updateSelectionUI();
    return;
  }
  state.selection = new Set([key]);
  state.lastClicked = key;
  updateSelectionUI();
  openItem(item);
}

async function openItem(item) {
  if (item.exists === false) { setStatus(t("err_not_found", { path: item.path }), "error"); return; }
  const b = bridge();
  if (!b) { setStatus(t("st_no_bridge"), "error"); return; }
  if (item.pid) rememberProject(item.pid);
  const click = ++state.openClick;
  try {
    // Con pestaña abierta solo se cambia a ella: nunca se recarga desde el disco. Salvo que aún no esté
    // cargada (restaurada al arrancar): esa se leerá del disco, y debe ser la copia más reciente.
    if (!b.isOpen(item.path) || !b.isLoaded(item.path)) {
      await postJSON(`${API}/workflow/prepare-open`, { path: item.path });
      await b.sync();
    }
    // Si mientras tanto se ha hecho clic en otro, manda ese.
    if (click !== state.openClick) return;
    await b.open(item.path);
  } catch (e) {
    setStatus(errText(e), "error");
  }
}

// ---------- menús ----------
function selectedItemsFor(item) {
  if (!state.selection.has(item.key)) {
    state.selection = new Set([item.key]);
    state.lastClicked = item.key;
    updateSelectionUI();
  }
  return [...state.selection].map((k) => state.items.get(k)).filter(Boolean);
}

function fileMenu(x, y, item) {
  const items = selectedItemsFor(item);
  const single = items.length === 1 ? items[0] : null;
  const project = item.pid ? state.tree.projects.find((p) => p.id === item.pid) : null;
  const canUnlink = items.every((i) => {
    const p = i.pid && state.tree.projects.find((q) => q.id === i.pid);
    return p && !p.folder;
  });
  showContextMenu(x, y, [
    { head: single ? single.name : t("ctx_head_many", { n: items.length }) },
    single && { label: t("ctx_open"), onClick: () => openItem(single) },
    single && { label: t("ctx_rename"), onClick: () => renameItem(single) },
    { label: t("ctx_move"), onClick: () => moveDialog(items) },
    single && { label: t("ctx_dup"), onClick: () => duplicateItem(single, project) },
    state.tree.projects.some((p) => p.id !== item.pid) ? { label: t("ctx_addproj"), onClick: () => addToProjectDialog(items) } : null,
    canUnlink && { label: t("ctx_remove_link"), onClick: () => unlinkItems(items) },
    { sep: true },
    single && { label: t("ctx_download"), onClick: () => downloadItem(single) },
    { label: t("ctx_export_zip"), onClick: () => exportItems(items) },
    { sep: true },
    { label: t("ctx_delete"), danger: true, onClick: () => deleteItems(items) },
  ]);
}

function folderMenu(x, y, ctx, folder) {
  const project = ctx.pid ? state.tree.projects.find((p) => p.id === ctx.pid) : null;
  showContextMenu(x, y, [
    { head: folder.split("/").pop() },
    { label: t("ctx_new_sub"), onClick: () => newFolderIn(ctx.pid, folder) },
    { label: t("ctx_import"), onClick: () => importInto(ctx.pid, folder) },
    { label: t("ctx_rename"), onClick: () => renameFolder(ctx.pid, folder) },
    { label: t("ctx_export_zip"), onClick: () => startExport(ctx.pid ? { project: ctx.pid, folder } : { folder }) },
    { sep: true },
    { label: t("ctx_delete"), danger: true, onClick: () => deleteFolder(project, folder) },
  ]);
}

function workflowsMenu(x, y) {
  showContextMenu(x, y, [
    { label: t("ctx_new_folder"), onClick: () => newFolderIn(null, "") },
    { label: t("ctx_import"), onClick: () => importInto(null, "") },
    { label: t("ctx_export_zip"), onClick: () => startExport({ folder: "" }) },
  ]);
}

function projectMenu(x, y, p) {
  showContextMenu(x, y, [
    { head: p.name },
    { label: t("ctx_new_sub"), onClick: () => newFolderIn(p.id, "") },
    { label: t("ctx_import"), onClick: () => importInto(p.id, "") },
    { label: t("ctx_export_zip"), onClick: () => startExport({ project: p.id }) },
    p.folder && { label: t("ctx_git"), onClick: () => { state.gitProject = p.id; switchView("git"); } },
    { label: t("ctx_edit"), onClick: () => projectForm(p) },
    { sep: true },
    { label: t("ctx_delete_project"), danger: true, onClick: () => deleteProject(p) },
  ]);
}

// ---------- arrastrar y soltar ----------
// Sin tecla: mover dentro del mismo proyecto. Ctrl: incluir también en otro. Shift: pasarlo a otro.
const CTRL_LABEL = /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘" : "Ctrl";
const DROP_MODES = [["plain", null], ["ctrl", CTRL_LABEL], ["shift", "Shift"]];
const CANVAS_DRAG_TYPE = "application/x-bswm-workflows";   // lo recoge comfy_ext.js al soltar en el lienzo
const ROW_DRAG_TYPE = "application/x-bswm-row";

function projectById(pid) {
  return state.tree.projects.find((p) => p.id === pid) || null;
}
function folderOwner(path) {
  return state.tree.projects.find((p) => p.prefix && path.startsWith(p.prefix + "/")) || null;
}
function whatLabel(items) {
  return items.length === 1 ? items[0].name.replace(/\.json$/i, "") : t("ctx_head_many", { n: items.length });
}
function dropMode(e) {
  if (e.ctrlKey || e.metaKey) return "ctrl";
  return e.shiftKey ? "shift" : "plain";
}
function hasFiles(e) {
  return !state.drag && e.dataTransfer && [...e.dataTransfer.types].includes("Files");
}

// Qué hará soltar un workflow en un destino con cada tecla. null = no se puede.
function resolveDrop(item, target, mode) {
  if (!target.newProject && item.pid === target.pid) {
    if (item.folder === target.folder || mode === "ctrl") return null;
    return "move";
  }
  if (!target.newProject && !target.pid) return mode === "shift" ? "takeout" : null;
  if (mode === "plain") return item.pid ? null : "add";
  if (mode === "shift") return "exclusive";
  const tgt = target.newProject ? null : projectById(target.pid);
  const owner = folderOwner(item.path);
  return tgt && tgt.folder && owner && owner.id !== tgt.id ? "copy" : "add";
}

function canDropFolder(drag, target) {
  if (target.newProject || drag.pid !== target.pid) return false;
  if (target.folder === drag.folder || target.folder.startsWith(drag.folder + "/")) return false;
  const parent = drag.folder.includes("/") ? drag.folder.slice(0, drag.folder.lastIndexOf("/")) : "";
  return target.folder !== parent;
}

function targetLabel(target) {
  if (target.newProject) return t("tip_new_project");
  const p = target.pid ? projectById(target.pid) : null;
  const base = p ? p.name : t("h_workflows");
  return target.folder ? `${base} / ${target.folder}` : base;
}

function sourceLabel(items) {
  const pids = new Set(items.map((i) => i.pid));
  const p = pids.size === 1 ? projectById(items[0].pid) : null;
  return p ? p.name : t("tip_its_project");
}

// Plan de una tecla sobre un destino: {op, text}. Sin operación, `text` explica el motivo.
function dropPlan(target, mode) {
  const drag = state.drag;
  if (drag.kind === "folder") {
    const ok = canDropFolder(drag, target);
    return { op: ok ? "move" : null, text: t(ok ? "tip_folder" : "tip_folder_no") };
  }
  const allowed = drag.items.filter((i) => resolveDrop(i, target, mode));
  if (!allowed.length) return { op: null, text: dropReason(drag.items[0], target, mode) };
  const op = resolveDrop(allowed[0], target, mode);
  const to = targetLabel(target);
  const from = sourceLabel(allowed);
  const inProject = allowed.some((i) => i.pid);
  const text = {
    move: t("tip_move"),
    add: t(inProject ? "tip_add_also" : "tip_add", { to, from }),
    copy: t("tip_copy", { to }),
    exclusive: inProject ? t("tip_exclusive", { from, to }) : t("tip_exclusive_only", { to }),
    takeout: t("tip_takeout", { from }),
  }[op];
  const count = allowed.length < drag.items.length ? ` (${allowed.length}/${drag.items.length})` : "";
  return { op, text: text + count };
}

function dropReason(item, target, mode) {
  if (!target.newProject && item.pid === target.pid) {
    if (item.folder === target.folder) return t("tip_here");
    return t(target.pid ? "tip_already" : "tip_only_projects");
  }
  if (mode === "ctrl") return t("tip_only_projects");
  if (!target.newProject && !target.pid) return t("tip_use_shift");
  return t("tip_use_keys", { ctrl: CTRL_LABEL });
}

function renderDragTip(target, mode) {
  const drag = state.drag;
  const key = JSON.stringify([target, mode, currentLang]);
  const tip = $("#drag-tip");
  tip.classList.remove("hidden");
  if (key === state.dragKey) return;
  state.dragKey = key;
  tip.replaceChildren(el("div", { class: "dt-title" }, target
    ? t("tip_title", { what: drag.label, to: targetLabel(target) })
    : t("tip_title_idle", { what: drag.label })));
  const inProject = drag.kind === "files" && drag.items.some((i) => i.pid);
  for (const [m, label] of DROP_MODES) {
    if (drag.kind === "folder" && m !== "plain") continue;
    let text;
    let op = "legend";
    if (target) {
      const plan = dropPlan(target, m);
      text = plan.text;
      op = plan.op;
    } else if (drag.kind === "folder") {
      text = t("tip_folder");
    } else {
      text = t(m === "plain" ? (inProject ? "tip_legend_plain" : "tip_legend_plain_general")
        : m === "ctrl" ? "tip_legend_ctrl" : "tip_legend_shift");
    }
    const cls = "dt-row" + (m === mode || drag.kind === "folder" ? " active" : "") + (op ? "" : " off");
    tip.appendChild(el("div", { class: cls }, el("kbd", {}, label || t("key_drop")), el("span", {}, text)));
  }
  if (!target && drag.kind === "files" && !shiftDrag) {
    tip.appendChild(el("div", { class: "dt-row" }, el("kbd", {}, t("key_canvas")), el("span", {}, t("tip_canvas_legend"))));
  }
}

// El cursor ha salido del panel: al soltar en el lienzo se abre.
function renderCanvasTip() {
  const tip = $("#drag-tip");
  if (!state.drag || state.drag.kind !== "files") { tip.classList.add("hidden"); return; }
  state.dragKey = "canvas";
  tip.classList.remove("hidden");
  tip.replaceChildren(el("div", { class: "dt-title" }, state.drag.label),
    el("div", { class: "dt-row active" }, el("kbd", {}, t("key_canvas")), el("span", {}, t("tip_canvas"))));
}

function beginDrag(e, drag, source) {
  closeContextMenu();
  state.pressed = false;
  state.drag = drag;
  state.dragSource = source;
  state.dragKey = "";
  e.dataTransfer.effectAllowed = "copyMove";
  // Un tipo propio y no texto: soltar en un campo de texto (de aquí o de ComfyUI) no debe escribir nada.
  e.dataTransfer.setData(ROW_DRAG_TYPE, drag.label);
  if (drag.kind === "files") {
    const paths = drag.items.filter((i) => i.exists !== false).map((i) => i.path);
    if (paths.length) e.dataTransfer.setData(CANVAS_DRAG_TYPE, JSON.stringify(paths));
  }
  const ghost = el("div", { class: "drag-ghost" }, drag.label);
  document.body.appendChild(ghost);
  e.dataTransfer.setDragImage(ghost, -12, 10);
  // Tocar el DOM durante dragstart puede cancelar el arrastre: se hace justo después.
  setTimeout(() => {
    ghost.remove();
    if (state.drag) renderDragTip(null, dropMode(e));
  }, 0);
}

function clearDropNode() {
  clearTimeout(state.expandTimer);
  state.expandTimer = null;
  if (state.dropNode) {
    state.dropNode.classList.remove("drop-hover", "drop-add", "drop-no");
    delete state.dropNode.dataset.hint;
  }
  state.dropNode = null;
}

function endDrag() {
  clearDropNode();
  $("#drag-tip").classList.add("hidden");
  if (state.dragSource && state.dragSource.classList.contains("hidden")) state.dragSource.remove();
  state.drag = null;
  state.dragSource = null;
  state.dragKey = "";
  flushRender();
}

function dropTargetAt(e) {
  if (!e.target) return { node: null, target: null };
  const node = e.target.nodeType === 1 ? e.target : e.target.parentElement;
  if (node === $("#tree")) return { node: null, target: { pid: null, folder: "" } };
  const row = node && node.closest(".t-row, .t-empty");
  return row && row.__drop ? { node: row, target: row.__drop } : { node: null, target: null };
}

function markDropNode(node, kind, hint) {
  if (state.dropNode !== node) {
    clearDropNode();
    state.dropNode = node;
    if (node && node.__expand) {
      const key = node.__expand;
      state.expandTimer = setTimeout(() => {
        state.expanded.add(key);
        saveExpanded();
        renderTree();
      }, 700);
    }
  }
  if (!node) return;
  node.classList.add("drop-hover");
  node.classList.toggle("drop-add", kind === "add");
  node.classList.toggle("drop-no", kind === "no");
  node.dataset.hint = hint;
}

const DROP_HINTS = { move: "hint_move", add: "hint_add", copy: "hint_copy", exclusive: "hint_move", takeout: "hint_out" };

function onDragOver(e) {
  const { node, target } = dropTargetAt(e);
  if (!state.drag) {
    if (!hasFiles(e)) return;
    const allowed = target && !target.newProject;
    if (allowed) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
    }
    markDropNode(allowed ? node : null, "add", t("hint_import"));
    return;
  }
  const mode = dropMode(e);
  autoScrollTree(e);
  placeDragTip(e);
  renderDragTip(target, mode);
  if (!target) { markDropNode(null); return; }
  const plan = dropPlan(target, mode);
  if (plan.op) {
    e.preventDefault();
    e.dataTransfer.dropEffect = mode === "ctrl" && state.drag.kind !== "folder" ? "copy" : "move";
  } else {
    e.dataTransfer.dropEffect = "none";
  }
  const kind = !plan.op ? "no" : (plan.op === "add" || plan.op === "copy") ? "add" : "move";
  markDropNode(node, kind, t(plan.op ? DROP_HINTS[plan.op] : "hint_no"));
}

function onDragLeave(e) {
  if (e.relatedTarget && $("#tree").contains(e.relatedTarget)) return;
  clearDropNode();
  if (state.drag) { state.dragKey = ""; renderDragTip(null, dropMode(e)); }
}

async function onDrop(e) {
  e.preventDefault();
  $("#tree").focus();
  const { target } = dropTargetAt(e);
  const drag = state.drag;
  const mode = dropMode(e);
  const files = drag ? [] : [...e.dataTransfer.files];
  endDrag();
  if (!target) return;
  if (files.length) { if (!target.newProject) await importFiles(files, target); return; }
  if (!drag) return;
  if (drag.kind === "folder") await moveFolderTo(drag, target);
  else await dropItems(drag.items, target, mode);
}

// Chromium no inicia el arrastre nativo si Shift ya estaba pulsado al pulsar el ratón (lo toma por
// extender una selección). En ese caso la fila se arrastra con eventos de ratón, por el mismo camino.
let shiftDrag = null;       // { x, y, row, active, timer, last }
let ignoreClick = false;

function shiftDragEvent() {
  const m = shiftDrag.last;
  return {
    target: document.elementFromPoint(m.clientX, m.clientY),
    clientX: m.clientX, clientY: m.clientY,
    ctrlKey: m.ctrlKey, metaKey: m.metaKey, shiftKey: m.shiftKey,
    preventDefault() {},
    dataTransfer: {},
  };
}

function shiftDragTick() {
  const e = shiftDragEvent();
  if (e.target && $("#tree").contains(e.target)) { onDragOver(e); return; }
  clearDropNode();
  renderDragTip(null, dropMode(e));
}

// `drop`: soltar en el destino. Si no, se cancela; `cancelClick`: el botón sigue pulsado y, al soltarlo, el
// clic que genere el navegador tampoco debe contar.
function endShiftDrag(drop, cancelClick = false) {
  const s = shiftDrag;
  if (!s) return;
  if (s.active && cancelClick) ignoreClick = true;
  clearInterval(s.timer);
  document.body.classList.remove("shift-drag");
  if (s.active && drop) {
    const e = shiftDragEvent();
    shiftDrag = null;
    onDrop(e);
    return;
  }
  shiftDrag = null;
  if (s.active) endDrag();
}

function shiftDragKeys(e) {
  if (!shiftDrag) return;
  shiftDrag.last = { clientX: shiftDrag.last.clientX, clientY: shiftDrag.last.clientY, ctrlKey: e.ctrlKey, metaKey: e.metaKey, shiftKey: e.shiftKey };
}

function installShiftDrag() {
  $("#tree").addEventListener("mousedown", (e) => {
    if (e.button !== 0 || !e.shiftKey || state.editing || e.target.closest("button")) return;
    const row = e.target.closest(".t-row");
    if (row && row.__dragData) shiftDrag = { x: e.clientX, y: e.clientY, row, active: false, timer: null, last: e };
  });
  document.addEventListener("mousemove", (e) => {
    const s = shiftDrag;
    if (!s) return;
    if (!(e.buttons & 1)) { endShiftDrag(false); return; }
    s.last = e;
    if (s.active) return;
    if (Math.hypot(e.clientX - s.x, e.clientY - s.y) < 5) return;
    s.active = true;
    closeContextMenu();
    state.pressed = false;
    state.drag = s.row.__dragData();
    state.dragSource = null;
    state.dragKey = "";
    document.body.classList.add("shift-drag");
    s.timer = setInterval(shiftDragTick, 50);
    shiftDragTick();
  });
  document.addEventListener("mouseup", () => {
    if (!shiftDrag) {
      if (ignoreClick) setTimeout(() => { ignoreClick = false; }, 0);
      return;
    }
    if (shiftDrag.active) {
      ignoreClick = true;     // el clic que sigue a soltar no es un clic en la fila
      setTimeout(() => { ignoreClick = false; }, 0);
    }
    endShiftDrag(true);
  });
  document.addEventListener("click", (e) => {
    if (!ignoreClick) return;
    ignoreClick = false;
    e.stopPropagation();
    e.preventDefault();
  }, true);
  document.addEventListener("keydown", (e) => {
    if (shiftDrag && shiftDrag.active && e.key === "Escape") {
      e.stopPropagation();
      e.preventDefault();
      endShiftDrag(false, true);
      return;
    }
    shiftDragKeys(e);
  }, true);
  document.addEventListener("keyup", shiftDragKeys, true);
  // Otros navegadores sí lo inician: si llega antes gana el nativo; si llega después, se descarta.
  document.addEventListener("dragstart", (e) => {
    if (!shiftDrag) return;
    if (shiftDrag.active) {
      e.preventDefault();
      e.stopPropagation();
    } else {
      endShiftDrag(false);
    }
  }, true);
  window.addEventListener("blur", () => endShiftDrag(false));
}

// El tip no debe tapar el sitio al que se apunta: va en el extremo contrario al cursor.
function placeDragTip(e) {
  const tip = $("#drag-tip");
  const h = window.innerHeight;
  if (e.clientY > h * 0.62) tip.classList.add("top");
  else if (e.clientY < h * 0.38) tip.classList.remove("top");
}

function autoScrollTree(e) {
  const tree = $("#tree");
  const r = tree.getBoundingClientRect();
  if (e.clientY < r.top + 24) tree.scrollTop -= 8;
  else if (e.clientY > r.bottom - 24) tree.scrollTop += 8;
}

function expandTarget(target) {
  if (target.pid) {
    rememberProject(target.pid);
    state.expanded.add("sec:projects");
    state.expanded.add(`p:${target.pid}`);
  } else {
    state.expanded.add("sec:workflows");
  }
  const parts = target.folder ? target.folder.split("/") : [];
  parts.forEach((_, i) => {
    const path = parts.slice(0, i + 1).join("/");
    state.expanded.add(target.pid ? `p:${target.pid}/${path}` : `g/${path}`);
  });
  saveExpanded();
}

async function dropItems(items, target, mode) {
  if (target.newProject) {
    const pid = await projectForm(null);
    if (!pid) return;
    target = { pid, folder: "" };
  }
  const allowed = items.filter((i) => resolveDrop(i, target, mode));
  if (!allowed.length) { setStatus(dropReason(items[0], target, mode)); return; }
  const firstOp = resolveDrop(allowed[0], target, mode);
  const from = sourceLabel(allowed);
  const entries = [];
  const tgt = target.pid ? projectById(target.pid) : null;
  // El mismo archivo seleccionado en dos proyectos: a una carpeta solo se puede llevar una vez.
  const list = tgt && tgt.folder ? uniqueByPath(allowed) : allowed;
  const done = await run(async () => {
    for (const item of list) {
      const op = resolveDrop(item, target, mode);
      if (op === "add" && mode === "plain") {
        entries.push(await addOne(item, target));
      } else if (op === "add" || op === "copy") {
        entries.push(await moveWithTabs("add-to-project", { path: item.path, project: target.pid, folder: target.folder, allow_multi: true }));
      } else {
        entries.push(await moveWithTabs("move", {
          path: item.path, from_project: item.pid, to_project: target.pid, folder: target.folder,
          exclusive: op === "exclusive" && !item.pid,
        }));
      }
    }
    expandTarget(target);
    return true;
  }, "");
  const message = { add: "st_added", copy: "st_copied", takeout: "st_taken" }[firstOp] || "st_moved";
  offerUndo(entries, done ? t(message, { what: whatLabel(allowed), to: targetLabel(target), from }) : null);
}

async function moveFolderTo(drag, target) {
  if (!canDropFolder(drag, target)) return;
  if (blockedByOpenTabs(drag.pid ? projectById(drag.pid) : null, drag.folder)) return;
  const name = drag.folder.split("/").pop();
  const dest = target.folder ? `${target.folder}/${name}` : name;
  const done = await run(async () => {
    await moveFolderRequest(drag.pid, drag.folder, dest);
    expandTarget(target);
    return true;
  }, "");
  if (done) {
    offerUndo([{ folder: true, pid: drag.pid, from: drag.folder, to: dest }], t("st_moved", { what: name, to: targetLabel(target) }));
  }
}

// ---------- operaciones sobre workflows ----------
// Si el workflow tiene pestaña, se mueve primero con ComfyUI para que la pestaña lo siga.
async function moveWithTabs(route, body) {
  const plan = await postJSON(`${API}/workflow/${route}`, { ...body, dry_run: true });
  const b = bridge();
  const general_moved = !!(b && plan.new !== plan.old && b.isOpen(plan.old));
  if (general_moved) await b.renameOpen(plan.old, plan.new);
  try {
    return await postJSON(`${API}/workflow/${route}`, { ...body, general_moved });
  } catch (e) {
    // La pestaña vuelve a donde estaba: el archivo y los proyectos no deben quedar a medias.
    if (general_moved) await b.renameOpen(plan.new, plan.old).catch(console.error);
    throw e;
  }
}

async function moveItems(items, target) {
  const entries = [];
  const tgt = target.pid ? projectById(target.pid) : null;
  const list = tgt && tgt.folder ? uniqueByPath(items) : items;
  const done = await run(async () => {
    for (const item of list) {
      if (item.pid === target.pid && item.folder === target.folder) continue;
      if (!item.pid && target.pid) {
        entries.push(await addOne(item, target));
      } else {
        entries.push(await moveWithTabs("move", { path: item.path, from_project: item.pid, to_project: target.pid, folder: target.folder }));
      }
    }
    if (target.pid) { rememberProject(target.pid); state.expanded.add(`p:${target.pid}`); saveExpanded(); }
    return true;
  }, "");
  offerUndo(entries, done ? t("st_done") : null);
}

// Permite revertir lo último que se ha movido, también si la operación se quedó a medias.
function offerUndo(entries, message) {
  const valid = entries.filter(Boolean);
  state.undo = valid.length ? valid : null;
  // Sin mensaje, la operación ha fallado y se mantiene el error, con la opción de revertir lo hecho.
  if (message) setStatus(valid.length ? message : "", "ok");
  if (!state.undo) return;
  $("#status").appendChild(el("button", { class: "status-undo", type: "button", title: "Ctrl+Z", onclick: performUndo }, t("btn_undo")));
  if (message) {
    clearTimeout(statusTimer);
    statusTimer = setTimeout(() => setStatus(""), 15000);
  }
}

async function performUndo() {
  const entries = state.undo;
  if (!entries) return;
  $("#tree").focus();
  for (const e of entries) {
    if (e.folder && blockedByOpenTabs(e.pid ? projectById(e.pid) : null, e.to)) {
      offerUndo(entries, null);     // al cerrar esas pestañas se puede volver a intentar
      return;
    }
  }
  const b = bridge();
  const pending = [...entries];
  await run(async () => {
    while (pending.length) {
      const e = pending[pending.length - 1];
      if (e.folder) {
        await moveFolderRequest(e.pid, e.to, e.from);
      } else {
        // Antes de cerrar la pestaña de la copia: el servidor puede negarse a borrarla.
        if (e.copied) await postJSON(`${API}/workflow/undo-move`, { old: e.old, new: e.new, copied: e.copied, copied_mtime: e.copied_mtime, dry_run: true });
        if (e.copied && b && !(await b.closeForDelete(e.copied))) throw new Error(t("st_undo_cancelled"));
        await moveWithTabs("undo-move", {
          old: e.old, new: e.new, links: e.links, copied: e.copied, copied_mtime: e.copied_mtime,
        });
      }
      pending.pop();
    }
  }, t("st_undone"));
  // Lo que no se haya podido revertir se puede reintentar.
  if (pending.length) offerUndo(pending, null);
}

// Añade un workflow a un proyecto; si ya está en otro, ofrece compartir el mismo archivo.
async function addOne(item, target) {
  const body = { path: item.path, project: target.pid, folder: target.folder };
  try {
    return await moveWithTabs("add-to-project", body);
  } catch (e) {
    if (e.code !== "already_linked") throw e;
    const ok = await showConfirm(t("f_addproj_title"), t("confirm_share", { message: errText(e) }) + " " + t("warn_shared"), t("btn_share"));
    return ok ? moveWithTabs("add-to-project", { ...body, allow_multi: true }) : null;
  }
}

async function moveDialog(items) {
  const first = items[0];
  const v = await showForm(t("f_move_title"), destinationFields(JSON.stringify([first.pid, first.folder])), t("btn_confirm"));
  if (v) await moveItems(items, destinationTarget(v));
}
function destinationTarget(v) { return readDestination(v); }

async function addToProjectDialog(items) {
  const v = await showForm(t("f_addproj_title"), destinationFields(defaultDestination(true), { projectsOnly: true }), t("btn_confirm"));
  if (v) await dropItems(items, destinationTarget(v), "ctrl");
}

async function unlinkItems(items) {
  await run(async () => {
    for (const i of items) await postJSON(`${API}/workflow/remove-from-project`, { project: i.pid, path: i.path });
  });
}

// Edita un nombre dentro de la propia fila. Devuelve el texto, o null si se cancela.
function inlineEdit(row, value) {
  return new Promise((resolve) => {
    const name = row.querySelector(".t-name");
    const saved = [...name.childNodes];
    const input = el("input", { class: "t-edit", type: "text", spellcheck: "false" });
    input.value = value;
    name.replaceChildren(input);
    row.setAttribute("draggable", "false");
    state.editing = true;
    let done = false;
    const finish = (result) => {
      if (done) return;
      done = true;
      state.editing = false;
      name.replaceChildren(...saved);
      row.setAttribute("draggable", "true");
      resolve(result);
      flushRender();
    };
    input.addEventListener("keydown", (e) => {
      e.stopPropagation();
      if (e.key === "Enter") { e.preventDefault(); finish(input.value.trim()); $("#tree").focus(); }
      else if (e.key === "Escape") { e.preventDefault(); finish(null); $("#tree").focus(); }
    });
    input.addEventListener("blur", () => {
      if (state.pressed) state.skipClick = row.dataset.key || null;
      finish(input.value.trim());
    });
    for (const type of ["click", "dblclick", "mousedown", "contextmenu"]) {
      input.addEventListener(type, (e) => e.stopPropagation());
    }
    input.focus();
    input.select();
  });
}

async function askNewName(row, current) {
  if (row) return inlineEdit(row, current);
  const v = await showForm(t("f_rename"), [{ key: "name", label: t("f_new_name"), value: current }], t("btn_confirm"));
  return v ? v.name : null;
}

async function renameItem(item) {
  const current = item.name.replace(/\.json$/i, "");
  const name = await askNewName($$(".t-row.file").find((r) => r.dataset.key === item.key && !r.classList.contains("hidden")), current);
  if (!name || name === current) return;
  const res = await run(() => moveWithTabs("rename", { path: item.path, new_name: name }));
  // Si se ha salido del campo pulsando otra fila, la selección ya es esa.
  if (res && !state.selection.size) {
    const key = item.pid ? `p:${item.pid}:${res.new}` : `g:${res.new}`;
    state.selection = new Set([key]);
    state.lastClicked = key;
    updateSelectionUI();
  }
}

async function duplicateItem(item, project) {
  const fields = [
    { key: "name", label: t("f_copy_name"), value: item.name.replace(/\.json$/i, "") + " copy" },
    ...destinationFields(JSON.stringify([project ? project.id : null, item.folder])),
  ];
  const v = await showForm(t("f_duplicate"), fields, t("btn_confirm"));
  if (!v) return;
  const dest = readDestination(v);
  await run(() => postJSON(`${API}/workflow/duplicate`, {
    path: item.path, project: dest.pid, folder: dest.folder, new_name: v.name || null,
  }));
}

function uniqueByPath(items) {
  return [...new Map(items.map((i) => [i.path, i])).values()];
}

async function deleteItems(selected) {
  const items = uniqueByPath(selected);
  let msg = items.length === 1 ? t("confirm_delete_one", { name: items[0].name }) : t("confirm_delete_many", { n: items.length });
  const shared = items.some((i) => (state.pathProjects.get(i.path) || []).some((p) => p.id !== i.pid));
  if (shared) msg += " " + t("confirm_delete_shared");
  const ok = await showConfirm(t("confirm_delete_title"), msg, t("ctx_delete"), true);
  if (!ok) return;
  const b = bridge();
  let removed = 0;
  await run(async () => {
    for (const i of items) {
      if (b && !(await b.closeForDelete(i.path))) continue;
      await postJSON(`${API}/workflow/delete`, { path: i.path });
      removed++;
    }
  }, "");
  if (removed) setStatus(t("st_done"), "ok");
}

function downloadItem(item) {
  download(`${API}/workflow/download?path=${encodeURIComponent(item.path)}`, item.name)
    .catch((e) => setStatus(errText(e), "error"));
}

// ---------- carpetas ----------
async function newFolderIn(pid, parent) {
  const v = await showForm(pid ? t("f_new_sub") : t("f_new_folder"), [{ key: "name", label: t("f_folder_name"), value: "" }], t("btn_confirm"));
  if (!v || !v.name) return;
  const full = parent ? parent + "/" + v.name : v.name;
  state.expanded.add(pid ? `p:${pid}` : "sec:workflows");
  if (parent) state.expanded.add(pid ? `p:${pid}/${parent}` : `g/${parent}`);
  saveExpanded();
  await run(() => (pid
    ? postJSON(`${API}/project/subfolder/add`, { id: pid, name: full })
    : postJSON(`${API}/folder/create`, { folder: full })));
}

function comfyFolder(project, folder) {
  return project ? (project.prefix ? project.prefix + "/" + folder : null) : folder;
}

function blockedByOpenTabs(project, folder) {
  const b = bridge();
  const base = comfyFolder(project, folder);
  const open = b && base ? b.openUnder(base) : [];
  if (open.length) {
    setStatus(t("st_close_tabs", { files: open.map((f) => f.split("/").pop()).join(", ") }), "error");
    return true;
  }
  return false;
}

async function renameFolder(pid, folder) {
  const project = pid ? state.tree.projects.find((p) => p.id === pid) : null;
  if (blockedByOpenTabs(project, folder)) return;
  const name = folder.split("/").pop();
  const key = pid ? `p:${pid}/${folder}` : `g/${folder}`;
  const newName = await askNewName($$(".t-row.folder").find((r) => r.dataset.folderKey === key && !r.classList.contains("hidden")), name);
  if (!newName || newName === name) return;
  const parent = folder.includes("/") ? folder.slice(0, folder.lastIndexOf("/") + 1) : "";
  await run(() => moveFolderRequest(pid, folder, parent + newName));
}

function moveFolderRequest(pid, folder, dest) {
  return pid
    ? postJSON(`${API}/project/subfolder/rename`, { id: pid, old: folder, new: dest })
    : postJSON(`${API}/folder/move`, { folder, new_folder: dest });
}

async function deleteFolder(project, folder) {
  if (blockedByOpenTabs(project, folder)) return;
  const name = folder.split("/").pop();
  const labels = project && !project.folder
    ? t("confirm_remove_sub", { name })
    : t("confirm_delete_folder", { name });
  const ok = await showConfirm(t("confirm_delete_title"), labels, t("ctx_delete"), true);
  if (!ok) return;
  let message;
  await run(async () => {
    if (project) {
      await postJSON(`${API}/project/subfolder/remove`, { id: project.id, name: folder });
    } else {
      const res = await postJSON(`${API}/folder/delete`, { folder });
      if (!res.gone) message = t("st_folder_kept");
    }
  });
  if (message) setStatus(message, "ok");
}

// ---------- proyectos ----------
const PROJECT_COLORS = ["#AC1F23", "#D69A3C", "#4E8B6B", "#5E93B4", "#8E6BB0", "#C2628F", "#7C8A3A", "#B5763A"];

// Primer color de la paleta sin usar: así los proyectos se distinguen a simple vista.
function nextProjectColor() {
  const used = new Set(state.tree.projects.map((p) => p.color.toUpperCase()));
  return PROJECT_COLORS.find((c) => !used.has(c)) || PROJECT_COLORS[state.tree.projects.length % PROJECT_COLORS.length];
}

async function projectForm(existing) {
  const fields = [
    { key: "name", label: t("f_name"), value: existing ? existing.name : "" },
    { key: "color", label: t("f_color"), type: "color", value: existing ? existing.color : nextProjectColor() },
    { key: "folder", label: t("f_own_folder"), type: "path", value: existing ? existing.folder || "" : "",
      placeholder: "/mnt/projects/my-project", hint: t("f_own_folder_hint") },
    { key: "notes", label: t("f_notes"), type: "textarea", value: existing ? existing.notes : "" },
  ];
  const v = await showForm(existing ? t("f_edit_project") : t("f_new_project"), fields, t("btn_save"));
  if (!v) return null;
  if (existing && v.folder !== (existing.folder || "")) {
    const b = bridge();
    const open = b ? existing.items.filter((i) => b.isOpen(i.path)).map((i) => i.name) : [];
    if (open.length) {
      setStatus(t("st_close_tabs", { files: open.join(", ") }), "error");
      return null;
    }
  }
  let created = null;
  await run(async () => {
    if (existing) {
      await postJSON(`${API}/project/update`, { id: existing.id, ...v });
    } else {
      const res = await postJSON(`${API}/project/create`, v);
      created = res.project.id;
      rememberProject(created);
      state.expanded.add(`p:${created}`);
      state.expanded.add("sec:projects");
      saveExpanded();
    }
  });
  return created;
}

async function deleteProject(p) {
  const check = el("input", { type: "checkbox" });
  const shared = p.folder && p.items.some((i) => i.shared);
  const label = t(p.folder ? "opt_delete_files" : "opt_delete_files_tags") + (shared ? " " + t("confirm_delete_shared") : "");
  const extra = el("label", { class: "field inline" }, check, el("span", {}, label));
  const ok = await showConfirm(t("confirm_delete_title"), t("confirm_delete_project", { name: p.name }), t("ctx_delete"), true, extra);
  if (!ok) return;
  const b = bridge();
  const openFiles = b ? p.items.filter((i) => b.isOpen(i.path)).map((i) => i.name) : [];
  if (check.checked && openFiles.length) {
    setStatus(t("st_close_tabs", { files: openFiles.join(", ") }), "error");
    return;
  }
  await run(() => postJSON(`${API}/project/delete`, { id: p.id, delete_files: check.checked }));
}

// ---------- guardar ----------
function updateSaveBar() {
  const b = bridge();
  const a = state.tab.active;
  const save = $("#sb-save");
  const toProject = $("#sb-save-project");
  save.disabled = !b || !a;
  // Las pestañas de subgrafos no son archivos de la carpeta de workflows.
  toProject.disabled = !b || !a || (!a.temporary && !a.rel);
  $("#sb-mod").classList.toggle("hidden", !(a && a.modified));
  if (!b) {
    $("#sb-name").textContent = "";
    $("#sb-target").textContent = t("sb_no_bridge");
    return;
  }
  $("#sb-name").textContent = a ? a.name : t("sb_no_active");
  const target = $("#sb-target");
  if (!a) { target.textContent = ""; return; }
  if (a.temporary) { target.textContent = t("sb_unsaved"); return; }
  if (!a.rel) { target.textContent = ""; return; }
  const p = projectOfPath(a.rel);
  if (p && p.mirror) target.textContent = t("sb_project_folder", { project: p.name });
  else if (p) target.textContent = t("sb_project", { project: p.name });
  else target.textContent = t("sb_comfy_only");
}

async function saveActive() {
  const b = bridge();
  if (!b) return;
  try {
    const res = await b.save();
    if (res.temporary) { setStatus(t("st_save_cancelled")); return; }
    if (res.failed) { setStatus(t("st_save_failed"), "error"); return; }
    await refresh();
    setStatus(t("st_saved", { name: res.name }), "ok");
  } catch (e) {
    setStatus(errText(e), "error");
  }
}

// "A proyecto…": guarda el workflow activo dentro de un proyecto.
async function saveToProject() {
  const b = bridge();
  const a = state.tab.active;
  if (!b || !a) return;
  if (!state.tree.projects.length) {
    await projectForm(null);
    if (!state.tree.projects.length) return;
  }
  const fields = [];
  if (a.temporary) fields.push({ key: "name", label: t("f_name"), value: a.name.replace(/\.json$/i, "") });
  fields.push(...destinationFields(defaultDestination(true), { projectsOnly: true }));
  const v = await showForm(t("f_save_project_title"), fields, t("btn_save"));
  if (!v) return;
  const sameTab = () => {
    const now = b.getState().active;
    return now && now.rel === a.rel && now.name === a.name;
  };
  if (!sameTab()) {
    setStatus(t("st_tab_changed"), "error");
    return;
  }
  const dest = readDestination(v);
  const project = state.tree.projects.find((p) => p.id === dest.pid);
  await run(async () => {
    let rel;
    if (a.temporary) {
      const file = (v.name || a.name).replace(/\.json$/i, "") + ".json";
      const dir = project.folder ? [project.prefix, dest.folder].filter(Boolean).join("/") : "";
      rel = dir ? dir + "/" + file : file;
      // ComfyUI solo conoce su carpeta: el archivo puede existir ya solo en la del proyecto.
      await postJSON(`${API}/workflow/check-free`, { path: rel });
      if (!sameTab()) throw new Error(t("st_tab_changed"));
      try {
        await b.saveActiveAs(rel);
      } catch (e) {
        if (e.message === "exists") { const err = new Error(rel); err.code = "exists"; err.params = { path: rel }; throw err; }
        throw e;
      }
    } else {
      const res = await b.save();
      if (res.failed) throw new Error(t("st_save_failed"));
      rel = res.rel;
    }
    await addOne({ path: rel, name: rel.split("/").pop() }, { pid: dest.pid, folder: dest.folder });
    rememberProject(dest.pid);
    state.expanded.add(`p:${dest.pid}`);
    saveExpanded();
  });
}

// ---------- exportación (.zip en segundo plano) ----------
function exportItems(selected) {
  const items = uniqueByPath(selected);
  startExport({ paths: items.map((i) => i.path), name: items.length === 1 ? items[0].name.replace(/\.json$/i, "") : "workflows" });
}

async function startExport(body) {
  try {
    const { job } = await postJSON(`${API}/export`, body);
    state.exportPending.add(job);
    saveExportsPending();
    pollExports();
    watchExports();
  } catch (e) { setStatus(errText(e), "error"); }
}

function watchExports() {
  if (state.exportTimer) return;
  state.exportTimer = setInterval(async () => {
    if (!(await pollExports())) { clearInterval(state.exportTimer); state.exportTimer = null; }
  }, 800);
}

function saveExportsPending() {
  storageSet("bswm_exports_pending", JSON.stringify([...state.exportPending]));
}

// Cerrar el panel destruye el iframe: al volver a abrirlo sigue con las descargas que este navegador dejó
// pendientes, y solo con esas. Las de otro navegador del mismo usuario son suyas.
async function resumeExports() {
  try { state.exportPending = new Set(JSON.parse(storageGet("bswm_exports_pending", "[]"))); } catch (e) { /* se ignora */ }
  if (state.exportPending.size && await pollExports()) watchExports();
}

async function pollExports() {
  try {
    const { jobs } = await getJSON(`${API}/export/status`);
    const box = $("#exports");
    box.innerHTML = "";
    for (const j of jobs) {
      box.appendChild(el("div", { class: "export-job" + (j.state === "error" ? " error" : "") },
        el("span", { class: "grow" }, `${j.name}.zip · ${j.error || (j.ready ? t("export_ready") : `${j.done}/${j.total}`)}`)));
      if (j.ready && state.exportPending.delete(j.id)) {
        saveExportsPending();
        download(`${API}/export/download?id=${encodeURIComponent(j.id)}`, `${j.name}.zip`).catch((e) => setStatus(errText(e), "error"));
      }
    }
    // Las que han fallado, o ya no existen tras reiniciar el servidor, no van a poder descargarse.
    for (const id of [...state.exportPending]) {
      const job = jobs.find((j) => j.id === id);
      if (!job || job.state === "error") state.exportPending.delete(id);
    }
    saveExportsPending();
    const active = jobs.some((j) => j.state === "queued" || j.state === "running");
    if (!active && jobs.length) {
      if (jobs.every((j) => j.state !== "error")) setTimeout(clearExports, 4000);
      else box.appendChild(el("div", { class: "export-job" }, el("span", { class: "grow" }),
        el("button", { class: "btn small", type: "button", onclick: clearExports }, t("btn_clear_finished"))));
    }
    return active;
  } catch (e) { return false; }
}

async function clearExports() {
  // Las descargas ya están hechas: se pueden borrar los .zip temporales del servidor. No si ha
  // terminado otra que aún no se ha descargado: el siguiente sondeo se encargará de ella.
  try {
    const { jobs } = await getJSON(`${API}/export/status`);
    if (jobs.some((j) => j.state === "queued" || j.state === "running" || (j.ready && state.exportPending.has(j.id)))) return;
    await postJSON(`${API}/export/clear`, {});
  } catch (e) { /* silencioso */ }
  $("#exports").innerHTML = "";
}

// ---------- importación ----------
function importInto(pid, folder) {
  state.importTarget = { pid, folder };
  const inp = $("#file-input");
  inp.multiple = true;
  inp.click();
}

async function onFilesPicked(e) {
  const files = [...e.target.files];
  e.target.value = "";
  if (!files.length) return;
  const target = state.importTarget;
  state.importTarget = null;
  if (target === "db") {
    const node = $("#s-db-status");
    try {
      let data;
      try {
        data = JSON.parse(await files[0].text());
      } catch (e) {
        throw Object.assign(new Error("This isn't a valid projects database."), { code: "bad_db", params: {} });
      }
      await postJSON(`${API}/db/import`, { data, merge: $("#s-db-merge").checked });
      setNodeStatus(node, t("st_done"), "ok");
      await refresh();
    } catch (err) { setNodeStatus(node, errText(err), "error"); }
    return;
  }
  await importFiles(files, target);
}

async function importFiles(files, target) {
  await run(async () => {
    for (const f of files) {
      await postJSON(`${API}/workflow/import`, {
        name: f.name, content: await f.text(), project: target.pid, folder: target.folder,
      });
    }
    expandTarget(target);
  });
}

// ============================================================
//  GIT
// ============================================================
function gitProjects() {
  return state.tree.projects.filter((p) => p.folder);
}

async function loadGit() {
  await loadTree();
  const projects = gitProjects();
  const det = state.config && state.config.git;
  const banner = $("#git-banner");
  const available = !!(det && det.git && det.git.available);
  $("#git-body").classList.toggle("hidden", !available || !projects.length);
  if (!available) {
    banner.className = "banner off";
    banner.textContent = t("git_off");
    return;
  }
  if (!projects.length) {
    banner.className = "banner warn";
    banner.textContent = t("git_no_projects");
    return;
  }
  showGitOk();
  $("#git-gh").classList.toggle("hidden", !(det.gh && det.gh.available));

  const sel = $("#git-project");
  sel.innerHTML = "";
  for (const p of projects) sel.appendChild(el("option", { value: p.id }, p.name));
  if (projects.some((p) => p.id === state.gitProject)) sel.value = state.gitProject;
  state.gitProject = sel.value;
  await refreshGitInfo();
  pollGitOnce();
}

function showGitOk() {
  const det = state.config && state.config.git;
  if (!det || !det.git || !det.git.available) return;
  const gh = det.gh && det.gh.available ? t(det.gh.authed ? "git_gh_authed" : "git_gh_anon", { ghv: det.gh.version }) : "";
  const banner = $("#git-banner");
  banner.className = "banner ok";
  banner.textContent = t("git_ok", { gv: det.git.version, gh });
}

async function refreshGitInfo() {
  const pid = $("#git-project").value;
  // Lo de otro proyecto no puede seguir a la vista: sus botones actuarían sobre el seleccionado.
  if (pid !== state.gitShown) {
    for (const id of ["#git-info", "#git-changes", "#git-log"]) $(id).innerHTML = "";
    $("#git-changes-sum").textContent = "";
    $("#git-remote-url").value = "";
    $("#git-actions").classList.add("hidden");
  }
  state.gitShown = pid;
  state.gitProject = pid;
  const refreshId = ++state.gitRefresh;
  const status = $("#git-status");
  setNodeStatus(status, "");
  try {
    const info = await getJSON(`${API}/git/info?project=${encodeURIComponent(pid)}`);
    if (refreshId !== state.gitRefresh) return;     // ya se ha elegido otro proyecto
    const box = $("#git-info");
    box.innerHTML = "";
    box.appendChild(el("div", { class: "kv" }, el("b", {}, info.folder)));
    const banner = $("#git-banner");
    const blocked = info.blocked || !info.exists || !!info.error;
    if (info.error) {
      banner.className = "banner warn";
      banner.textContent = t("git_error", { detail: info.error });
    } else if (info.blocked) {
      banner.className = "banner warn";
      banner.textContent = t("git_blocked");
    } else if (!info.exists) {
      banner.className = "banner warn";
      banner.textContent = t("git_folder_missing");
    } else {
      showGitOk();
    }
    $("#git-actions").classList.toggle("hidden", blocked);
    $("#git-init").classList.toggle("hidden", blocked || info.is_repo);
    $("#git-repo-actions").classList.toggle("hidden", !info.is_repo);
    if (!info.is_repo) {
      if (!blocked) box.appendChild(el("div", { class: "muted" }, t("git_not_repo")));
      $("#git-changes").innerHTML = "";
      $("#git-changes-sum").textContent = "";
      $("#git-log").innerHTML = "";
      return;
    }
    const facts = [t("git_branch", { branch: info.branch || "?" })];
    if (info.ahead) facts.push(t("git_ahead", { a: info.ahead }));
    if (info.behind) facts.push(t("git_behind", { b: info.behind }));
    box.appendChild(el("div", { class: "muted" }, facts.join(" · ")));
    if (info.shared_repo) box.appendChild(el("div", { class: "muted" }, t("git_shared_repo", { top: info.toplevel })));
    $("#git-remote-url").value = info.remote_url || "";

    const ch = $("#git-changes");
    ch.innerHTML = "";
    if (!info.changes.length) ch.appendChild(el("div", { class: "muted" }, t("no_changes")));
    for (const c of info.changes) ch.appendChild(el("div", { class: "ch" }, el("code", {}, c.code), el("span", { class: "ch-text" }, c.path)));
    $("#git-changes-sum").textContent = info.changes.length ? String(info.changes.length) : "";

    const { log } = await getJSON(`${API}/git/log?project=${encodeURIComponent(pid)}&n=40`);
    if (refreshId !== state.gitRefresh) return;
    const logBox = $("#git-log");
    logBox.innerHTML = "";
    if (!log.length) logBox.appendChild(el("div", { class: "muted" }, t("no_history")));
    for (const c of log) {
      logBox.appendChild(el("div", { class: "ch", title: `${c.author} · ${fmtDate(c.date)}` },
        el("code", {}, c.short), el("span", { class: "ch-text" }, c.subject),
        el("button", { class: "btn small", type: "button", onclick: () => gitRestore(c) }, t("btn_restore"))));
    }
  } catch (e) {
    if (refreshId === state.gitRefresh) setNodeStatus(status, errText(e), "error");
  }
}

async function gitRestore(c) {
  const ok = await showConfirm(t("btn_restore"), t("confirm_restore", { commit: c.short }), t("btn_restore"), true);
  if (ok) gitRun("restore", { commit: c.hash });
}

// Restaurar o bajar cambios con la pestaña abierta: su siguiente guardado los pisaría.
function gitBlockedByTabs(kind) {
  if (kind !== "restore" && kind !== "pull") return false;
  const b = bridge();
  const p = projectById($("#git-project").value);
  const open = b && p && p.prefix ? b.openUnder(p.prefix) : [];
  if (!open.length) return false;
  setNodeStatus($("#git-status"), t("st_close_tabs", { files: open.map((f) => f.split("/").pop()).join(", ") }), "error");
  return true;
}

async function gitRun(kind, opts) {
  if (gitBlockedByTabs(kind)) return false;
  try {
    await postJSON(`${API}/git/run`, { project: $("#git-project").value, kind, ...opts });
    pollGitOnce();
    if (!state.gitTimer) {
      state.gitTimer = setInterval(async () => {
        if (!(await pollGitOnce())) {
          clearInterval(state.gitTimer);
          state.gitTimer = null;
          await refreshGitInfo();
        }
      }, 1000);
    }
    return true;
  } catch (e) {
    setNodeStatus($("#git-status"), errText(e), "error");
    return false;
  }
}

async function pollGitOnce() {
  try {
    const { jobs } = await getJSON(`${API}/git/jobs`);
    const box = $("#git-jobs");
    box.innerHTML = "";
    $("#git-jobs-panel").classList.toggle("hidden", !jobs.length);
    for (const j of jobs) {
      box.appendChild(el("div", { class: "job state-" + j.state },
        el("div", { class: "job-head" },
          el("span", { class: "state-pill" }, t("state_" + j.state)),
          el("span", { class: "job-name" }, t("job_" + j.kind))),
        (j.error || j.log) ? el("div", { class: "job-meta" }, j.error || j.log) : null));
    }
    return jobs.some((j) => j.state === "queued" || j.state === "running");
  } catch (e) { return false; }
}

async function gitCreateGitHub() {
  const pid = $("#git-project").value;
  const p = state.tree.projects.find((x) => x.id === pid);
  const v = await showForm(t("f_gh_title"), [
    { key: "name", label: t("f_gh_name"), value: p ? p.name.replace(/[^\w.-]+/g, "-") : "" },
    { key: "private", label: t("f_gh_private"), type: "checkbox", value: true },
  ], t("btn_confirm"));
  if (v && v.name) gitRun("gh_create", { name: v.name, private: v.private });
}

// ============================================================
//  AJUSTES
// ============================================================
function loadSettings() {
  $("#s-root").textContent = (state.config && state.config.comfy_root) || "";
  $("#s-db-path").textContent = (state.config && state.config.db_path) || "";
  $("#s-show-linked").checked = state.showLinked;
}

// ============================================================
//  navegación / arranque
// ============================================================
async function loadTree() {
  state.tree = await getJSON(`${API}/tree`);
  renderTree();
  updateSaveBar();
}

async function refresh() {
  const b = bridge();
  if (b) await b.sync();
  await loadTree();
}

function activeView() {
  const v = document.querySelector(".view.active");
  return v ? v.id.replace("view-", "") : "library";
}

function switchView(view) {
  $$(".tab").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === "view-" + view));
  if (view === "library") loadTree().catch((e) => setStatus(errText(e), "error"));
  if (view === "git") loadGit().catch((e) => setNodeStatus($("#git-status"), errText(e), "error"));
  if (view === "settings") loadSettings();
}

function applyI18n() {
  document.documentElement.lang = currentLang;
  $$("[data-i18n]").forEach((n) => { n.textContent = t(n.getAttribute("data-i18n")); });
  $$("[data-i18n-ph]").forEach((n) => { n.setAttribute("placeholder", t(n.getAttribute("data-i18n-ph"))); });
  $$("[data-i18n-title]").forEach((n) => {
    n.setAttribute("title", t(n.getAttribute("data-i18n-title")));
    if (n.hasAttribute("aria-label")) n.setAttribute("aria-label", n.getAttribute("title"));
  });
  $$("[data-i18n-aria]").forEach((n) => { n.setAttribute("aria-label", t(n.getAttribute("data-i18n-aria"))); });
}

function setLang(lang) {
  if (!I18N[lang]) return;
  currentLang = lang;
  storageSet("bswm_lang", lang);
  $$(".lang-btn").forEach((b) => b.classList.toggle("active", b.dataset.lang === lang));
  applyI18n();
  if (!$("#help-modal").classList.contains("hidden")) openHelp();
  renderTree();
  updateSaveBar();
  const view = activeView();
  if (view === "git") loadGit().catch(() => {});
}

// Sincroniza el árbol con las pestañas de ComfyUI.
function pollTabs() {
  const b = bridge();
  if (!b) { updateSaveBar(); return; }
  const tab = b.getState();
  const dirtyChanged = tab.dirty !== state.tab.dirty;
  const changed = JSON.stringify(tab) !== JSON.stringify(state.tab);
  state.tab = tab;
  if (dirtyChanged) {
    loadTree().catch(() => {});
  } else if (changed) {
    updateTabMarks();
    updateSaveBar();
  }
  const rel = tab.active && tab.active.rel;
  if (rel !== state.lastActive) {
    state.lastActive = rel;
    if (rel && !tab.active.temporary) revealPath(rel);
  }
  // Lo pedido desde el menú File espera: no debe descartar lo que se esté escribiendo en un diálogo.
  const busy = dismissActiveModal || $(".fb-overlay") || !$("#help-modal").classList.contains("hidden");
  const pending = busy ? null : b.takePending();
  if (pending === "save-to-project") { switchView("library"); saveToProject(); }
}

function moveCursor(step, extend) {
  if (!state.order.length) return;
  const at = state.order.indexOf(state.lastClicked);
  const next = at < 0 ? (step > 0 ? 0 : state.order.length - 1) : Math.max(0, Math.min(state.order.length - 1, at + step));
  const key = state.order[next];
  if (extend) state.selection.add(key); else state.selection = new Set([key]);
  state.lastClicked = key;
  updateSelectionUI();
  const row = $$(".t-row.file").find((r) => r.dataset.key === key && !r.classList.contains("hidden"));
  if (row) row.scrollIntoView({ block: "nearest" });
}

function onTreeKey(e) {
  if (e.target !== $("#tree")) return;
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
    e.preventDefault();
    performUndo();
    return;
  }
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    moveCursor(e.key === "ArrowDown" ? 1 : -1, e.shiftKey);
    return;
  }
  const items = [...state.selection].map((k) => state.items.get(k)).filter(Boolean);
  if (!items.length) return;
  if (e.key === "Delete") { e.preventDefault(); deleteItems(items); }
  else if (e.key === "F2" && items.length === 1) { e.preventDefault(); renameItem(items[0]); }
  else if (e.key === "Enter" && items.length === 1) { e.preventDefault(); openItem(items[0]); }
  else if (e.key === "Escape") { state.selection.clear(); updateSelectionUI(); }
}

function wireEvents() {
  $$(".tab").forEach((b) => b.addEventListener("click", () => switchView(b.dataset.view)));
  $$(".lang-btn").forEach((b) => b.addEventListener("click", () => setLang(b.dataset.lang)));
  $("#help-btn").addEventListener("click", openHelp);
  $("#help-close").addEventListener("click", closeHelp);
  $("#help-modal").addEventListener("click", (e) => { if (e.target.id === "help-modal") closeHelp(); });

  $("#sb-save").addEventListener("click", saveActive);
  $("#sb-save-project").addEventListener("click", saveToProject);
  $("#search").addEventListener("input", renderTree);
  $("#btn-refresh").addEventListener("click", () => refresh().catch((e) => setStatus(errText(e), "error")));
  $("#btn-collapse").appendChild(icon("collapse", ""));
  $("#btn-collapse").addEventListener("click", () => {
    state.expanded = new Set([...state.expanded].filter((k) => k.startsWith("sec:")));
    saveExpanded();
    renderTree();
  });
  $("#tree").addEventListener("keydown", onTreeKey);
  $("#tree").addEventListener("dragover", onDragOver);
  $("#tree").addEventListener("dragleave", onDragLeave);
  $("#tree").addEventListener("drop", onDrop);
  $("#tree").addEventListener("dragend", endDrag);
  installShiftDrag();
  // Un archivo soltado fuera de un destino no debe sustituir el panel.
  document.addEventListener("dragover", (e) => {
    if (e.defaultPrevented || !hasFiles(e)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "none";
  });
  document.addEventListener("drop", (e) => { if (hasFiles(e)) e.preventDefault(); });
  document.addEventListener("dragleave", (e) => { if (!e.relatedTarget) renderCanvasTip(); });
  // Al volver del lienzo por fuera del árbol, el tip ya no debe hablar del lienzo.
  document.addEventListener("dragover", (e) => {
    if (state.drag && !$("#tree").contains(e.target)) renderDragTip(null, dropMode(e));
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("#help-modal").classList.contains("hidden")) closeHelp();
  });
  // Los atajos de ComfyUI no llegan aquí: sin esto, el navegador abriría "Guardar página como".
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      if (!dismissActiveModal) saveActive();
    }
  }, true);
  document.addEventListener("mousedown", () => {
    endShiftDrag(false, true);     // otro botón durante el arrastre con Shift
    if (state.drag) endDrag();     // no hay ratón durante un arrastre: este ya terminó sin avisar
    state.pressed = true;
  }, true);
  document.addEventListener("mouseup", () => {
    state.pressed = false;
    setTimeout(() => {             // después del clic que sigue a este evento
      state.skipClick = null;
      flushRender();
    }, 0);
  }, true);
  // Con el menú nativo del navegador (fuera de las filas) puede no llegar el "mouseup".
  document.addEventListener("contextmenu", () => {
    state.pressed = false;
    setTimeout(flushRender, 0);
  }, true);
  // Cualquier arrastre nativo, también el de texto de un campo, termina sin "mouseup".
  document.addEventListener("dragstart", () => {
    state.pressed = false;
    state.skipClick = null;
  }, true);
  document.addEventListener("dragend", () => { setTimeout(flushRender, 0); }, true);
  window.addEventListener("blur", () => {
    state.pressed = false;
    flushRender();
  });

  const selected = () => [...state.selection].map((k) => state.items.get(k)).filter(Boolean);
  $("#sel-move").addEventListener("click", () => moveDialog(selected()));
  $("#sel-export").addEventListener("click", () => exportItems(selected()));
  $("#sel-delete").addEventListener("click", () => deleteItems(selected()));
  $("#sel-clear").addEventListener("click", () => { state.selection.clear(); updateSelectionUI(); });

  $("#git-project").addEventListener("change", refreshGitInfo);
  $("#git-init").addEventListener("click", () => gitRun("init", {}));
  $("#git-commit").addEventListener("click", async () => {
    if (await gitRun("commit", { message: $("#git-commit-msg").value })) $("#git-commit-msg").value = "";
  });
  $("#git-remote").addEventListener("click", () => gitRun("remote", { url: $("#git-remote-url").value }));
  $("#git-push").addEventListener("click", () => gitRun("push", {}));
  $("#git-pull").addEventListener("click", () => gitRun("pull", {}));
  $("#git-gh").addEventListener("click", gitCreateGitHub);
  $("#git-clear").addEventListener("click", async () => {
    try {
      await postJSON(`${API}/git/clear`, {});
      pollGitOnce();
    } catch (e) { setNodeStatus($("#git-status"), errText(e), "error"); }
  });

  $("#s-show-linked").addEventListener("change", (e) => {
    state.showLinked = e.target.checked;
    storageSet("bswm_show_linked", state.showLinked ? "1" : "0");
    renderTree();
  });
  $("#s-db-export").addEventListener("click", () => {
    download(`${API}/db/export`, "bswm_projects.json").catch((e) => setNodeStatus($("#s-db-status"), errText(e), "error"));
  });
  $("#s-db-import").addEventListener("click", () => {
    state.importTarget = "db";
    const inp = $("#file-input");
    inp.multiple = false;
    inp.click();
  });
  $("#file-input").addEventListener("change", onFilesPicked);
  window.addEventListener("focus", () => { if (activeView() === "library") loadTree().catch(() => {}); });
}

async function init() {
  wireEvents();
  $$(".lang-btn").forEach((b) => b.classList.toggle("active", b.dataset.lang === currentLang));
  applyI18n();
  try { state.config = await getJSON(`${API}/config`); } catch (e) { setStatus(errText(e), "error"); }
  try {
    await refresh();
  } catch (e) {
    setStatus(errText(e), "error");
  }
  setInterval(pollTabs, 700);
  pollTabs();
  resumeExports();
}

init();
