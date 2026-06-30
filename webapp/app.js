// SPDX-License-Identifier: GPL-3.0-only
// Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
/* BS Workflow Manager — lógica de la mini-app (vanilla JS, sin build).
   Habla con la API JSON del backend en /bs_workflow_manager/api/... y, para abrir workflows en el
   canvas, con los puentes window.parent.bswmOpenWorkflow / bswmGetActiveWorkflow (mismo origen). */
"use strict";

const API = "/bs_workflow_manager/api";

// ---------- estado ----------
const state = {
  config: null,
  isUserRoot: true,
  general: { root: "", folders: [""], workflows: [] },
  genPath: "",              // carpeta actual en el explorador de la vista general
  genSel: new Set(),
  genLast: { v: null },     // última fila pulsada (selección por rango)
  projects: [],
  activeProject: null,      // id del proyecto activo (saves)
  selectedProject: null,    // id del proyecto seleccionado en la UI
  projPath: "",             // subcarpeta actual del proyecto (navegación)
  projSel: new Set(),
  projLast: { v: null },
  gitRepo: "studio",
  exportSeen: new Set(),    // jobs de export ya descargados
  pollTimer: null,
  lastOpened: null,         // {scope, rel|ref, pid?, name} del último workflow abierto desde el gestor
};

// ---------- i18n (EN por defecto + ES) ----------
const I18N = {
  en: {
    brand_link_title: "Go to bone-studio.com",
    tab_general: "General", tab_projects: "Projects", tab_git: "Git", tab_settings: "Settings",
    help_title: "Help", help_tooltip: "Help",
    btn_cancel: "Cancel", btn_accept: "Accept", btn_confirm: "Confirm", btn_save: "Save",
    btn_refresh: "Refresh", btn_delete: "Delete", btn_edit: "Edit",
    ph_filter_wf: "Search: multiple terms (e.g. wan video)",
    lbl_folder: "Folder", th_workflow: "Workflow", th_folder: "Folder", th_size: "Size",
    th_actions: "Actions", th_subfolder: "Subfolder",
    btn_new_folder: "New folder", btn_import: "Import…", btn_export_sel: "Export selected",
    sum_wf: "{n} workflows · {size}",
    act_open: "Open", act_rename: "Rename", act_move: "Move", act_dup: "Duplicate",
    act_export: "Export", act_addproj: "Add to project", act_remove: "Remove",
    folder_all: "All folders", folder_root: "(root)",
    h_exports: "Exports", btn_clear_finished: "Clear finished",
    h_projects: "Projects", btn_new_project: "New", p_empty: "Create or select a project.",
    btn_set_active: "Set active", btn_active: "Active ✓", btn_export_project: "Export",
    lbl_subfolders: "Subfolders:", btn_add_sub: "+ subfolder", sub_all: "All",
    btn_open_native: "Open",
    storage_virtual: "virtual", storage_folder: "folder",
    h_git: "Git", lbl_repo_target: "Repository",
    repo_studio: "Studio (workflows root)", repo_project: "Project: {name}",
    btn_git_init: "Init repo", btn_git_pull: "Pull", btn_git_push: "Push",
    ph_commit: "Commit message", btn_git_commit: "Commit all changes",
    ph_remote: "Remote URL (https://… or git@…)", btn_git_remote: "Set remote", btn_git_gh: "Create on GitHub",
    h_changes: "Pending changes", h_history: "History", h_git_jobs: "Git operations",
    git_off: "git is not installed — Git features are disabled. Install git to enable them.",
    git_ok: "git {gv}{gh}", git_gh_authed: " · gh {ghv} (authenticated)", git_gh_anon: " · gh {ghv} (not authenticated)",
    git_not_repo: "This folder is not a Git repository yet.",
    git_repo_info: "branch {branch} · {changes} change(s){remote}", git_remote_suffix: " · origin set",
    no_changes: "Working tree clean. ✓", no_history: "No commits yet.",
    h_root: "Workflows root", root_desc: "Folder the General view manages. Leave empty to use ComfyUI's own workflows folder (recommended: native open works).",
    ph_root: "(ComfyUI default)", btn_reset_default: "Reset to default",
    h_db: "Projects database", db_desc: "A single exportable JSON file. Export it for backup or to share project structure; import to restore or merge.",
    lbl_db_path: "Path:", btn_db_export: "Export DB", btn_db_import: "Import DB…", lbl_merge: "merge",
    st_open_from_comfy: "Open this panel from the ComfyUI sidebar to open workflows in the canvas.",
    st_loading: "Loading…", st_saved: "Saved.", st_done: "Done.",
    // forms
    f_new_folder: "New folder", f_folder_name: "Folder name (e.g. clients/pepe)",
    f_rename: "Rename workflow", f_new_name: "New name",
    f_duplicate: "Duplicate workflow", f_dup_name: "Name for the copy (optional)",
    f_new_project: "New project", f_edit_project: "Edit project",
    f_name: "Name", f_color: "Color", f_storage: "Storage", f_folder_path: "Folder path",
    f_git_mode: "Git mode", f_remote_url: "Remote URL (optional)", f_notes: "Notes",
    f_storage_virtual: "Virtual (tags only — file stays in the general folder)",
    f_storage_folder: "Folder-backed (files physically live in a folder)",
    f_git_none: "None", f_git_studio: "Studio repo (the workflows root)",
    f_git_dedicated: "Dedicated repo (this project's folder)", f_git_local: "Local repo (no remote)",
    f_add_sub: "New subfolder", f_sub_name: "Subfolder name",
    f_move_title: "Move to…", f_target_project: "Project", f_target_sub: "Subfolder",
    f_addproj_title: "Add to project", f_allow_multi: "Allow linking to several projects (same shared file)",
    f_export_name: "Export", f_gh_title: "Create GitHub repository", f_gh_name: "Repository name",
    f_gh_private: "Private", f_dup_target: "Duplicate into project",
    warn_shared: "This is the SAME file shared across projects — editing it affects all of them.",
    confirm_delete_wf: "Delete <b>{name}</b> from disk? This cannot be undone.",
    confirm_delete_folder: "Delete folder <b>{name}</b> and all workflows inside it?",
    confirm_delete_project: "Delete project <b>{name}</b>? (Files on disk are kept unless you tick below.)",
    confirm_delete_files: "Also delete the project's folder and its files from disk",
    confirm_remove_link: "Remove <b>{name}</b> from this project? (The file is kept.)",
    opt_delete_file: "Delete file from disk instead of just removing the link",
    none_selected: "Nothing selected.",
    st_opened: "Opened «{name}».", st_open_err: "Couldn't open: {e}",
    badge_shared: "shared", badge_missing: "missing",
  },
  es: {
    brand_link_title: "Ir a bone-studio.com",
    tab_general: "General", tab_projects: "Proyectos", tab_git: "Git", tab_settings: "Ajustes",
    help_title: "Ayuda", help_tooltip: "Ayuda",
    btn_cancel: "Cancelar", btn_accept: "Aceptar", btn_confirm: "Confirmar", btn_save: "Guardar",
    btn_refresh: "Refrescar", btn_delete: "Borrar", btn_edit: "Editar",
    ph_filter_wf: "Buscar: varios términos (p.ej. wan video)",
    lbl_folder: "Carpeta", th_workflow: "Workflow", th_folder: "Carpeta", th_size: "Tamaño",
    th_actions: "Acciones", th_subfolder: "Subcarpeta",
    btn_new_folder: "Nueva carpeta", btn_import: "Importar…", btn_export_sel: "Exportar selección",
    sum_wf: "{n} workflows · {size}",
    act_open: "Abrir", act_rename: "Renombrar", act_move: "Mover", act_dup: "Duplicar",
    act_export: "Exportar", act_addproj: "A proyecto", act_remove: "Quitar",
    folder_all: "Todas las carpetas", folder_root: "(raíz)",
    h_exports: "Exportaciones", btn_clear_finished: "Limpiar terminadas",
    h_projects: "Proyectos", btn_new_project: "Nuevo", p_empty: "Crea o selecciona un proyecto.",
    btn_set_active: "Marcar activo", btn_active: "Activo ✓", btn_export_project: "Exportar",
    lbl_subfolders: "Subcarpetas:", btn_add_sub: "+ subcarpeta", sub_all: "Todas",
    btn_open_native: "Abrir",
    storage_virtual: "virtual", storage_folder: "carpeta",
    h_git: "Git", lbl_repo_target: "Repositorio",
    repo_studio: "Estudio (raíz de workflows)", repo_project: "Proyecto: {name}",
    btn_git_init: "Crear repo", btn_git_pull: "Pull", btn_git_push: "Push",
    ph_commit: "Mensaje de commit", btn_git_commit: "Commit de todos los cambios",
    ph_remote: "URL del remoto (https://… o git@…)", btn_git_remote: "Fijar remoto", btn_git_gh: "Crear en GitHub",
    h_changes: "Cambios pendientes", h_history: "Historial", h_git_jobs: "Operaciones Git",
    git_off: "git no está instalado — las funciones Git están desactivadas. Instala git para activarlas.",
    git_ok: "git {gv}{gh}", git_gh_authed: " · gh {ghv} (autenticado)", git_gh_anon: " · gh {ghv} (sin autenticar)",
    git_not_repo: "Esta carpeta todavía no es un repositorio Git.",
    git_repo_info: "rama {branch} · {changes} cambio(s){remote}", git_remote_suffix: " · origin configurado",
    no_changes: "Árbol de trabajo limpio. ✓", no_history: "Aún no hay commits.",
    h_root: "Raíz de workflows", root_desc: "Carpeta que gestiona la vista General. Déjala vacía para usar la carpeta de workflows de ComfyUI (recomendado: la apertura nativa funciona).",
    ph_root: "(por defecto de ComfyUI)", btn_reset_default: "Volver a la de ComfyUI",
    h_db: "Base de datos de proyectos", db_desc: "Un único JSON exportable. Expórtalo como copia de seguridad o para compartir la estructura; impórtalo para restaurar o fusionar.",
    lbl_db_path: "Ruta:", btn_db_export: "Exportar BD", btn_db_import: "Importar BD…", lbl_merge: "fusionar",
    st_open_from_comfy: "Abre este panel desde la barra lateral de ComfyUI para abrir workflows en el canvas.",
    st_loading: "Cargando…", st_saved: "Guardado.", st_done: "Hecho.",
    f_new_folder: "Nueva carpeta", f_folder_name: "Nombre de carpeta (p.ej. clientes/pepe)",
    f_rename: "Renombrar workflow", f_new_name: "Nuevo nombre",
    f_duplicate: "Duplicar workflow", f_dup_name: "Nombre de la copia (opcional)",
    f_new_project: "Nuevo proyecto", f_edit_project: "Editar proyecto",
    f_name: "Nombre", f_color: "Color", f_storage: "Almacenamiento", f_folder_path: "Ruta de carpeta",
    f_git_mode: "Modo Git", f_remote_url: "URL del remoto (opcional)", f_notes: "Notas",
    f_storage_virtual: "Virtual (solo etiquetas — el archivo queda en la carpeta general)",
    f_storage_folder: "Con carpeta (los archivos viven físicamente en una carpeta)",
    f_git_none: "Ninguno", f_git_studio: "Repo de estudio (la raíz de workflows)",
    f_git_dedicated: "Repo dedicado (la carpeta del proyecto)", f_git_local: "Repo local (sin remoto)",
    f_add_sub: "Nueva subcarpeta", f_sub_name: "Nombre de la subcarpeta",
    f_move_title: "Mover a…", f_target_project: "Proyecto", f_target_sub: "Subcarpeta",
    f_addproj_title: "Añadir a proyecto", f_allow_multi: "Permitir vincular a varios proyectos (mismo archivo compartido)",
    f_export_name: "Exportar", f_gh_title: "Crear repositorio en GitHub", f_gh_name: "Nombre del repositorio",
    f_gh_private: "Privado", f_dup_target: "Duplicar en el proyecto",
    warn_shared: "Es el MISMO archivo compartido entre proyectos — editarlo afecta a todos.",
    confirm_delete_wf: "¿Borrar <b>{name}</b> del disco? No se puede deshacer.",
    confirm_delete_folder: "¿Borrar la carpeta <b>{name}</b> y todos los workflows que contiene?",
    confirm_delete_project: "¿Borrar el proyecto <b>{name}</b>? (Los archivos en disco se conservan salvo que marques abajo.)",
    confirm_delete_files: "Borrar también la carpeta del proyecto y sus archivos del disco",
    confirm_remove_link: "¿Quitar <b>{name}</b> de este proyecto? (El archivo se conserva.)",
    opt_delete_file: "Borrar el archivo del disco en lugar de solo quitar el vínculo",
    none_selected: "No hay nada seleccionado.",
    st_opened: "Abierto «{name}».", st_open_err: "No se pudo abrir: {e}",
    badge_shared: "compartido", badge_missing: "no existe",
  },
};

// Claves añadidas (explorador, menú contextual, traspaso, Git bloqueado).
Object.assign(I18N.en, {
  btn_from_comfy: "From ComfyUI…",
  hint_select: "Click to select · Ctrl/⌘-click multi · Shift-click range · double-click to open · right-click for actions",
  crumb_root: "workflows", sel_count: "{n} selected",
  p_empty_title: "No project selected",
  ctx_open: "Open", ctx_rename: "Rename", ctx_move: "Move…", ctx_dup: "Duplicate…",
  ctx_addproj: "Add to project…", ctx_export: "Export", ctx_delete: "Delete",
  ctx_remove_link: "Remove from project", ctx_open_folder: "Open folder",
  ctx_new_sub: "New subfolder…", ctx_rename_folder: "Rename folder…",
  ctx_export_folder: "Export folder", ctx_delete_folder: "Delete folder",
  ctx_new_folder: "New folder…", ctx_from_comfy: "Transfer from ComfyUI…",
  ctx_head_one: "{name}", ctx_head_many: "{n} workflows",
  f_rename_folder: "Rename folder", f_into_folder: "Into folder (optional)",
  tr_title: "Transfer from ComfyUI", tr_desc: "Pick the user workflows you want to copy into your own folder. ComfyUI's template workflows are not listed.",
  tr_filter: "Filter by name…", tr_move: "Move (remove from ComfyUI's folder)", tr_all: "All", tr_none_sel: "None",
  tr_empty: "No workflows found in ComfyUI's folder.",
  tr_same: "Your workflows root IS ComfyUI's folder. Set a dedicated folder in Settings first, then transfer.",
  tr_result: "Transferred {n}, skipped {s}.", tr_go: "Transfer {n}",
  git_blocked_default: "You're using ComfyUI's own workflows folder — Git is disabled for safety. Set a dedicated workflows folder in Settings to enable versioning.",
  git_blocked_foreign: "This folder is inside ComfyUI's Git repository — Git is disabled to avoid conflicts. Set a dedicated workflows folder in Settings.",
  go_settings: "Open Settings",
  btn_save_canvas: "Save canvas…", f_save_canvas: "Save current canvas", f_save_name: "Save as (name)",
  f_overwrite: "Overwrite if it already exists",
  st_no_canvas: "Couldn't read the ComfyUI canvas. Open this panel from the ComfyUI sidebar.",
  st_saved_to: "Saved «{name}».",
  // explorador de carpetas del servidor
  btn_browse: "Browse…", fb_title: "Choose a folder on the ComfyUI server",
  fb_roots: "Server roots", fb_new_folder: "New folder here", fb_select: "Select this folder",
  fb_up: "Up", fb_empty: "(no subfolders)", fb_new_name: "New folder name",
  lbl_server_path: "Path on the ComfyUI server",
  // subcarpetas (picker)
  sub_root: "(root)", sub_new: "＋ New subfolder…", f_new_sub_under: "New subfolder (under {where})",
  // guardar en proyecto
  btn_save_into: "Save to project", btn_save_into_general: "Save to folder", btn_save_as: "Save as…",
  st_save_native_hint: "Tip: ComfyUI's own Save (Ctrl+S) writes to ComfyUI's folder. Use this button to save into the manager.",
});
Object.assign(I18N.es, {
  btn_from_comfy: "Desde ComfyUI…",
  hint_select: "Click para seleccionar · Ctrl/⌘-click varios · Shift-click rango · doble click para abrir · botón derecho para acciones",
  crumb_root: "workflows", sel_count: "{n} seleccionados",
  p_empty_title: "Ningún proyecto seleccionado",
  ctx_open: "Abrir", ctx_rename: "Renombrar", ctx_move: "Mover…", ctx_dup: "Duplicar…",
  ctx_addproj: "Añadir a proyecto…", ctx_export: "Exportar", ctx_delete: "Borrar",
  ctx_remove_link: "Quitar del proyecto", ctx_open_folder: "Abrir carpeta",
  ctx_new_sub: "Nueva subcarpeta…", ctx_rename_folder: "Renombrar carpeta…",
  ctx_export_folder: "Exportar carpeta", ctx_delete_folder: "Borrar carpeta",
  ctx_new_folder: "Nueva carpeta…", ctx_from_comfy: "Traspasar desde ComfyUI…",
  ctx_head_one: "{name}", ctx_head_many: "{n} workflows",
  f_rename_folder: "Renombrar carpeta", f_into_folder: "En la carpeta (opcional)",
  tr_title: "Traspasar desde ComfyUI", tr_desc: "Elige los workflows de usuario que quieres copiar a tu propia carpeta. Los workflows de plantilla de ComfyUI no aparecen.",
  tr_filter: "Filtrar por nombre…", tr_move: "Mover (quitar de la carpeta de ComfyUI)", tr_all: "Todos", tr_none_sel: "Ninguno",
  tr_empty: "No se encontraron workflows en la carpeta de ComfyUI.",
  tr_same: "Tu raíz de workflows ES la carpeta de ComfyUI. Define primero una carpeta propia en Ajustes y luego traspasa.",
  tr_result: "Traspasados {n}, omitidos {s}.", tr_go: "Traspasar {n}",
  git_blocked_default: "Estás usando la carpeta de workflows de ComfyUI — Git está desactivado por seguridad. Define una carpeta propia en Ajustes para activar el versionado.",
  git_blocked_foreign: "Esta carpeta está dentro del repositorio Git de ComfyUI — Git está desactivado para evitar conflictos. Define una carpeta de workflows propia en Ajustes.",
  go_settings: "Abrir Ajustes",
  btn_save_canvas: "Guardar lienzo…", f_save_canvas: "Guardar el lienzo actual", f_save_name: "Guardar como (nombre)",
  f_overwrite: "Sobrescribir si ya existe",
  st_no_canvas: "No se pudo leer el lienzo de ComfyUI. Abre este panel desde la barra lateral de ComfyUI.",
  st_saved_to: "Guardado «{name}».",
  // explorador de carpetas del servidor
  btn_browse: "Examinar…", fb_title: "Elige una carpeta en el servidor de ComfyUI",
  fb_roots: "Raíces del servidor", fb_new_folder: "Nueva carpeta aquí", fb_select: "Seleccionar esta carpeta",
  fb_up: "Subir", fb_empty: "(sin subcarpetas)", fb_new_name: "Nombre de la carpeta nueva",
  lbl_server_path: "Ruta en el servidor de ComfyUI",
  // subcarpetas (picker)
  sub_root: "(raíz)", sub_new: "＋ Nueva subcarpeta…", f_new_sub_under: "Nueva subcarpeta (dentro de {where})",
  // guardar en proyecto
  btn_save_into: "Guardar en proyecto", btn_save_into_general: "Guardar en carpeta", btn_save_as: "Guardar como…",
  st_save_native_hint: "Nota: el Guardar propio de ComfyUI (Ctrl+S) escribe en la carpeta de ComfyUI. Usa este botón para guardar en el gestor.",
});

const HELP = {
  en: `
    <p><b>Bone-Studio Workflow Manager</b> organizes your ComfyUI workflows for production from a single panel.</p>
    <h4>General</h4>
    <p>A folder manager over your ComfyUI workflows folder (configurable in <b>Settings</b>). <b>Open</b> a
    workflow in the canvas, <b>rename</b>, <b>move</b> between folders, <b>duplicate</b>, <b>delete</b>,
    <b>export</b>, or <b>add it to a project</b>. Tick rows and <b>Export selected</b> to get a .zip.</p>
    <h4>Projects</h4>
    <p>A layer of your own (an exportable internal database) that links workflows to <b>projects</b> and
    <b>subfolders</b> — independent of where files live on disk. A project is either <b>virtual</b> (tags only)
    or <b>folder-backed</b> (its workflows physically live in a folder). By default a workflow belongs to one
    project; you can opt into sharing the same file across projects (it warns you, since edits propagate).
    <b>Duplicate</b> makes an independent copy.</p>
    <h4>Git</h4>
    <p>Optional version control. Pick a repository (the <b>studio</b> root or a project's folder), <b>init</b>,
    <b>commit</b>, set a <b>remote</b> or <b>create a GitHub repo</b> (needs <code>gh</code>), <b>push/pull</b>,
    browse <b>history</b>. Requires <code>git</code> installed on the system (we never install it).</p>
    <p class="muted">Switch language with EN/ES (top right). A Bone-Studio tool —
    <a href="https://bone-studio.com" target="_blank" rel="noopener noreferrer">bone-studio.com</a>.</p>
  `,
  es: `
    <p><b>Bone-Studio Workflow Manager</b> organiza tus workflows de ComfyUI para producción desde un solo panel.</p>
    <h4>General</h4>
    <p>Un gestor de carpetas sobre tu carpeta de workflows de ComfyUI (configurable en <b>Ajustes</b>).
    <b>Abre</b> un workflow en el canvas, <b>renómbralo</b>, <b>muévelo</b> entre carpetas, <b>duplícalo</b>,
    <b>bórralo</b>, <b>expórtalo</b> o <b>añádelo a un proyecto</b>. Marca filas y <b>Exporta la selección</b>
    para obtener un .zip.</p>
    <h4>Proyectos</h4>
    <p>Una capa propia (una base de datos interna exportable) que vincula workflows a <b>proyectos</b> y
    <b>subcarpetas</b>, independiente de dónde estén los archivos en disco. Un proyecto es <b>virtual</b> (solo
    etiquetas) o <b>con carpeta</b> (sus workflows viven físicamente en una carpeta). Por defecto un workflow
    pertenece a un único proyecto; puedes activar compartir el mismo archivo entre proyectos (te avisa, porque
    los cambios se propagan). <b>Duplicar</b> crea una copia independiente.</p>
    <h4>Git</h4>
    <p>Control de versiones opcional. Elige un repositorio (la raíz de <b>estudio</b> o la carpeta de un
    proyecto), <b>inicialízalo</b>, haz <b>commit</b>, fija un <b>remoto</b> o <b>crea un repo en GitHub</b>
    (necesita <code>gh</code>), <b>push/pull</b>, consulta el <b>historial</b>. Requiere <code>git</code>
    instalado en el sistema (nunca lo instalamos).</p>
    <p class="muted">Cambia el idioma con EN/ES (arriba a la derecha). Una herramienta de Bone-Studio —
    <a href="https://bone-studio.com" target="_blank" rel="noopener noreferrer">bone-studio.com</a>.</p>
  `,
};

let currentLang = (localStorage.getItem("bswm_lang") || "en").toLowerCase();
if (!I18N[currentLang]) currentLang = "en";

function t(key, vars) {
  let s = (I18N[currentLang] && I18N[currentLang][key]) || (I18N.en[key] != null ? I18N.en[key] : key);
  if (vars) for (const k in vars) s = s.split("{" + k + "}").join(vars[k]);
  return s;
}

function applyI18n() {
  document.documentElement.lang = currentLang;
  $$("[data-i18n]").forEach((n) => { n.textContent = t(n.getAttribute("data-i18n")); });
  $$("[data-i18n-ph]").forEach((n) => { n.setAttribute("placeholder", t(n.getAttribute("data-i18n-ph"))); });
  $$("[data-i18n-title]").forEach((n) => { n.setAttribute("title", t(n.getAttribute("data-i18n-title"))); });
}

function setLang(lang) {
  if (!I18N[lang]) return;
  currentLang = lang;
  localStorage.setItem("bswm_lang", lang);
  $$(".lang-btn").forEach((b) => b.classList.toggle("active", b.dataset.lang === lang));
  applyI18n();
  if (!$("#help-modal").classList.contains("hidden")) openHelp();
  rerenderActive();
}

// ---------- utilidades ----------
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined && v !== false) node.setAttribute(k, v);
  }
  for (const c of children) {
    if (c == null) continue;
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return node;
}

function humanSize(n) {
  n = Number(n || 0);
  const units = ["B", "KB", "MB", "GB", "TB", "PB"];
  let i = 0;
  while (Math.abs(n) >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return (i === 0 ? Math.round(n) : n.toFixed(1)) + " " + units[i];
}

function fmtDate(ts) {
  if (!ts) return "";
  try { return new Date(ts * 1000).toLocaleString(); } catch (e) { return ""; }
}

function matchTerms(haystack, query) {
  const terms = (query || "").toLowerCase().split(/[\s,]+/).filter(Boolean);
  if (!terms.length) return true;
  const h = String(haystack).toLowerCase();
  return terms.some((x) => h.includes(x));
}

async function getJSON(url) {
  const r = await fetch(url);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}
async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}

function setStatus(node, msg, kind = "") {
  if (!node) return;
  node.className = "status" + (kind ? " " + kind : "");
  node.innerHTML = msg || "";
}

// ---------- modal genérico (confirm + form) ----------
function showConfirm(title, bodyHTML, okLabel, danger = false) {
  okLabel = okLabel || t("btn_accept");
  return new Promise((resolve) => {
    const modal = $("#modal");
    $("#modal-title").textContent = title;
    $("#modal-body").innerHTML = bodyHTML;
    const ok = $("#modal-ok"), cancel = $("#modal-cancel");
    ok.textContent = okLabel;
    ok.className = "btn " + (danger ? "danger" : "primary");
    cancel.textContent = t("btn_cancel");
    modal.classList.remove("hidden");
    const close = (val) => {
      modal.classList.add("hidden");
      ok.removeEventListener("click", onOk); cancel.removeEventListener("click", onCancel);
      resolve(val);
    };
    const onOk = () => close(true), onCancel = () => close(false);
    ok.addEventListener("click", onOk); cancel.addEventListener("click", onCancel);
  });
}

// fields: [{key,label,type,value,placeholder,options,show(values)->bool,onchange}]
function showForm(title, fields, okLabel) {
  return new Promise((resolve) => {
    const modal = $("#modal");
    $("#modal-title").textContent = title;
    const body = $("#modal-body");
    body.innerHTML = "";
    const grid = el("div", { class: "form-grid" });
    const inputs = {};

    const readValues = () => {
      const v = {};
      for (const f of fields) {
        const rec = inputs[f.key];
        if (!rec) continue;
        v[f.key] = rec.type === "checkbox" ? rec.input.checked
          : (rec.type === "text" || rec.type === "textarea" || rec.type === "path" ? rec.input.value.trim() : rec.input.value);
      }
      return v;
    };
    const optionEls = (opts, selected) => (opts || []).map((o) =>
      el("option", { value: o.value, ...(o.value === selected ? { selected: "selected" } : {}) }, o.label));
    const resolveOptions = (f, vals) => (typeof f.options === "function" ? f.options(vals) : (f.options || []));
    // Selects con opciones dinámicas (función): se repueblan al cambiar otro campo.
    const rebuildDynamic = () => {
      const vals = readValues();
      for (const f of fields) {
        if (f.type === "select" && typeof f.options === "function") {
          const rec = inputs[f.key];
          const opts = resolveOptions(f, vals);
          const keep = rec.input.value;
          const sel = opts.some((o) => o.value === keep) ? keep : (opts[0] && opts[0].value);
          rec.input.innerHTML = "";
          optionEls(opts, sel).forEach((o) => rec.input.appendChild(o));
        }
      }
    };
    const refreshVisibility = () => {
      for (const f of fields) {
        const rec = inputs[f.key];
        if (rec && f.show) rec.wrap.classList.toggle("hidden", !f.show(readValues()));
      }
    };

    const initVals = {};
    for (const f of fields) if (f.value !== undefined) initVals[f.key] = f.value;

    for (const f of fields) {
      if (f.type === "html") { grid.appendChild(el("div", { html: f.html, class: f.cls || "" })); continue; }
      let input;
      if (f.type === "select") {
        input = el("select", {}, ...optionEls(resolveOptions(f, initVals), f.value));
      } else if (f.type === "textarea") {
        input = el("textarea", { placeholder: f.placeholder || "" }); input.value = f.value || "";
      } else if (f.type === "checkbox") {
        input = el("input", { type: "checkbox" }); input.checked = !!f.value;
      } else if (f.type === "color") {
        input = el("input", { type: "color", value: f.value || "#AC1F23" });
      } else {
        input = el("input", { type: "text", placeholder: f.placeholder || "", value: f.value || "" });
      }
      let wrap;
      if (f.type === "checkbox") {
        wrap = el("label", { class: "field inline" }, input, el("span", {}, f.label || f.key));
      } else if (f.type === "path") {
        const browse = el("button", { class: "btn small", type: "button", onclick: async () => {
          const picked = await browseServerFolder(input.value.trim());
          if (picked != null) { input.value = picked; refreshVisibility(); }
        } }, t("btn_browse"));
        wrap = el("label", { class: "field" }, el("span", {}, f.label || f.key),
          el("div", { class: "path-row" }, input, browse));
      } else {
        wrap = el("label", { class: "field" }, el("span", {}, f.label || f.key), input);
      }
      inputs[f.key] = { input, type: f.type, wrap };
      input.addEventListener("change", () => { rebuildDynamic(); refreshVisibility(); if (f.onchange) f.onchange(readValues(), inputs); });
      input.addEventListener("input", refreshVisibility);
      grid.appendChild(wrap);
    }
    body.appendChild(grid);
    rebuildDynamic();
    refreshVisibility();

    const ok = $("#modal-ok"), cancel = $("#modal-cancel");
    ok.textContent = okLabel || t("btn_accept");
    ok.className = "btn primary";
    cancel.textContent = t("btn_cancel");
    modal.classList.remove("hidden");
    const close = (val) => {
      modal.classList.add("hidden");
      ok.removeEventListener("click", onOk); cancel.removeEventListener("click", onCancel);
      resolve(val);
    };
    const onOk = () => close(readValues()), onCancel = () => close(null);
    ok.addEventListener("click", onOk); cancel.addEventListener("click", onCancel);
  });
}

// ---------- ayuda ----------
function openHelp() {
  $("#help-title").textContent = t("help_title");
  $("#help-body").innerHTML = HELP[currentLang] || HELP.en;
  $("#help-modal").classList.remove("hidden");
}
function closeHelp() { $("#help-modal").classList.add("hidden"); }

// ---------- explorador de carpetas del SERVIDOR ----------
// Devuelve una promesa con la ruta absoluta del servidor elegida, o null si se cancela.
function browseServerFolder(startPath) {
  return new Promise((resolve) => {
    const overlay = el("div", { class: "modal" });
    const card = el("div", { class: "modal-card fb-card" });
    overlay.appendChild(card);
    document.body.appendChild(overlay);
    let cur = startPath || "";
    const close = (val) => { overlay.remove(); resolve(val); };

    const render = async () => {
      card.innerHTML = "";
      card.appendChild(el("div", { class: "modal-title" }, t("fb_title")));
      let data;
      try {
        data = await getJSON(`${API}/fs/list?path=${encodeURIComponent(cur)}`);
      } catch (e) {
        cur = "";
        try { data = await getJSON(`${API}/fs/list?path=`); }
        catch (e2) { card.appendChild(el("div", { class: "status error" }, e2.message)); return; }
      }

      const head = el("div", { class: "fb-head" },
        el("span", { class: "fb-path" }, data.is_root_list ? t("fb_roots") : data.path));
      if (!data.is_root_list) {
        head.appendChild(el("button", { class: "btn small", onclick: () => { cur = data.parent || ""; render(); } }, "↑ " + t("fb_up")));
      }
      card.appendChild(head);

      const list = el("div", { class: "fb-list" });
      if (!data.dirs.length) list.appendChild(el("div", { class: "muted", style: "padding:8px" }, t("fb_empty")));
      for (const d of data.dirs) {
        list.appendChild(el("div", { class: "fb-row", ondblclick: () => { cur = d.path; render(); } },
          el("span", { class: "ico" }, "📁"),
          el("span", { class: "fb-name", onclick: () => { cur = d.path; render(); } }, d.name)));
      }
      card.appendChild(list);

      if (!data.is_root_list) {
        const newInput = el("input", { type: "text", placeholder: t("fb_new_name"), style: "flex:1" });
        const newBtn = el("button", { class: "btn small", onclick: async () => {
          const name = newInput.value.trim(); if (!name) return;
          try { await postJSON(`${API}/fs/mkdir`, { path: data.path, name }); newInput.value = ""; render(); }
          catch (e) { alert(e.message); }
        } }, t("fb_new_folder"));
        card.appendChild(el("div", { class: "fb-newrow" }, newInput, newBtn));
      }

      const actions = el("div", { class: "modal-actions" },
        el("button", { class: "btn", onclick: () => close(null) }, t("btn_cancel")));
      const selBtn = el("button", { class: "btn primary", onclick: () => close(data.path || null) }, t("fb_select"));
      if (data.is_root_list) selBtn.disabled = true;
      actions.appendChild(selBtn);
      card.appendChild(actions);
    };
    overlay.addEventListener("click", (e) => { if (e.target === overlay) close(null); });
    render();
  });
}

// ---------- menú contextual ----------
function closeContextMenu() {
  if (window.__ctx) { window.__ctx.remove(); window.__ctx = null; }
}
// items: [{label, danger, disabled, onClick} | {sep:true} | {head:"..."}]
function showContextMenu(x, y, items) {
  closeContextMenu();
  const menu = el("div", { class: "ctx-menu" });
  for (const it of items) {
    if (!it) continue;
    if (it.sep) { menu.appendChild(el("div", { class: "ctx-sep" })); continue; }
    if (it.head) { menu.appendChild(el("div", { class: "ctx-head" }, it.head)); continue; }
    const mi = el("div", { class: "ctx-item" + (it.danger ? " danger" : "") + (it.disabled ? " disabled" : "") }, it.label);
    if (!it.disabled) mi.addEventListener("click", () => { closeContextMenu(); it.onClick(); });
    menu.appendChild(mi);
  }
  document.body.appendChild(menu);
  const r = menu.getBoundingClientRect();
  menu.style.left = Math.max(4, Math.min(x, window.innerWidth - r.width - 8)) + "px";
  menu.style.top = Math.max(4, Math.min(y, window.innerHeight - r.height - 8)) + "px";
  window.__ctx = menu;
}
document.addEventListener("click", closeContextMenu);
document.addEventListener("scroll", closeContextMenu, true);
window.addEventListener("blur", closeContextMenu);
window.addEventListener("resize", closeContextMenu);

// Selección estilo explorador de archivos sobre una lista ordenada de claves (`order`).
// `sel` es un Set; `lastRef` un objeto {v} con la última clave pulsada (para Shift-rango).
function handleRowClick(e, key, order, sel, lastRef, onChange) {
  const isMeta = e.ctrlKey || e.metaKey;
  const isShift = e.shiftKey;
  if (isShift && lastRef.v != null && order.includes(lastRef.v)) {
    const a = order.indexOf(lastRef.v), b = order.indexOf(key);
    const [lo, hi] = a < b ? [a, b] : [b, a];
    if (!isMeta) sel.clear();
    for (let i = lo; i <= hi; i++) sel.add(order[i]);
  } else if (isMeta) {
    if (sel.has(key)) sel.delete(key); else sel.add(key);
    lastRef.v = key;
  } else {
    sel.clear(); sel.add(key); lastRef.v = key;
  }
  onChange();
}

// ---------- arrastrar y soltar (mover a subcarpeta) ----------
const dragState = { refs: [] };
function makeDraggable(tr, key, sel, onChange) {
  tr.setAttribute("draggable", "true");
  tr.addEventListener("dragstart", (e) => {
    if (!sel.has(key)) { sel.clear(); sel.add(key); if (onChange) onChange(); }
    dragState.refs = [...sel];
    e.dataTransfer.effectAllowed = "move";
    try { e.dataTransfer.setData("text/plain", dragState.refs.join("\n")); } catch (_) {}
  });
}
function makeDropTarget(node, onDrop) {
  node.addEventListener("dragover", (e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; node.classList.add("drop-hover"); });
  node.addEventListener("dragleave", () => node.classList.remove("drop-hover"));
  node.addEventListener("drop", (e) => {
    e.preventDefault(); node.classList.remove("drop-hover");
    if (dragState.refs.length) onDrop(dragState.refs.slice());
    dragState.refs = [];
  });
}

// ---------- abrir workflow (puente con ComfyUI) ----------
async function openWorkflow({ fetchUrl, name, storePath, statusNode }) {
  const bridge = window.parent && window.parent.bswmOpenWorkflow;
  if (typeof bridge !== "function") {
    setStatus(statusNode, t("st_open_from_comfy"), "error");
    return;
  }
  const res = await bridge({ fetchUrl, name, storePath });
  if (res && res.ok) setStatus(statusNode, t("st_opened", { name }), "ok");
  else setStatus(statusNode, t("st_open_err", { e: (res && res.error) || "?" }), "error");
}

// ============================================================
//  VISTA GENERAL
// ============================================================
async function loadConfig() {
  state.config = await getJSON(`${API}/config`);
  const a = (state.config.workflows_root || "").toLowerCase();
  const b = (state.config.user_workflows_root || "").toLowerCase();
  state.isUserRoot = a === b;
}

function storePathFor(rel, underUserRoot) {
  // Solo podemos abrir de forma nativa rastreada si el archivo cuelga de user/<u>/workflows.
  if (state.isUserRoot && underUserRoot !== false) return "workflows/" + rel;
  return null;
}

async function loadGeneral() {
  const status = $("#g-status");
  setStatus(status, t("st_loading"));
  try {
    state.general = await getJSON(`${API}/workflows/list`);
    state.genSel = new Set();
    state.genLast = { v: null };
    if (state.genPath && !state.general.folders.includes(state.genPath)) state.genPath = "";
    renderGeneral();
    setStatus(status, "", "");
  } catch (e) {
    setStatus(status, e.message, "error");
  }
}

// Subcarpetas directas de `path`.
function genChildFolders(path) {
  const prefix = path ? path + "/" : "";
  const set = new Set();
  for (const f of state.general.folders) {
    if (f === "" || !f.startsWith(prefix)) continue;
    const first = f.slice(prefix.length).split("/")[0];
    if (first) set.add(prefix + first);
  }
  return [...set].sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
}

// Nº de workflows dentro de `path` (recursivo) — para el contador de carpeta.
function countInFolder(path) {
  const prefix = path + "/";
  return state.general.workflows.filter((w) => w.folder === path || w.folder.startsWith(prefix)).length;
}

function renderCrumbs() {
  const box = $("#g-crumbs");
  box.innerHTML = "";
  const root = el("span", { class: "crumb" + (state.genPath === "" ? " current" : ""), onclick: () => navigateTo("") }, t("crumb_root"));
  makeDropTarget(root, (refs) => moveGeneralRefsTo(refs, ""));
  box.appendChild(root);
  let acc = "";
  (state.genPath ? state.genPath.split("/") : []).forEach((p, idx, arr) => {
    box.appendChild(el("span", { class: "sep" }, "/"));
    acc = acc ? acc + "/" + p : p;
    const cur = acc;
    const crumb = el("span", { class: "crumb" + (idx === arr.length - 1 ? " current" : ""), onclick: () => navigateTo(cur) }, p);
    makeDropTarget(crumb, (refs) => moveGeneralRefsTo(refs, cur));
    box.appendChild(crumb);
  });
}

async function moveGeneralRefsTo(refs, folder) {
  refs = refs.filter((r) => {
    const w = state.general.workflows.find((x) => x.rel === r);
    return w && w.folder !== folder;     // ignora los que ya están en destino
  });
  if (!refs.length) return;
  await apiThen($("#g-status"), async () => {
    for (const rel of refs) await postJSON(`${API}/workflows/move`, { rel, dest_folder: folder });
  }, loadGeneral);
}

function navigateTo(path) {
  state.genPath = path;
  state.genSel.clear();
  state.genLast = { v: null };
  renderGeneral();
}

function renderGeneral() {
  renderCrumbs();
  const body = $("#g-body");
  body.innerHTML = "";
  const q = $("#g-filter").value.trim();
  const searching = !!q;

  let folders = [], files;
  if (searching) {
    files = state.general.workflows.filter((w) => matchTerms(w.rel, q));
  } else {
    folders = genChildFolders(state.genPath);
    files = state.general.workflows.filter((w) => w.folder === state.genPath);
  }

  for (const f of folders) {
    const name = f.split("/").pop();
    const tr = el("tr", {
      class: "row-folder",
      ondblclick: () => navigateTo(f),
      oncontextmenu: (e) => { e.preventDefault(); folderMenu(e, f); },
    },
      el("td", { class: "c-file" }, el("div", { class: "nm" }, el("span", { class: "ico" }, "📁"), el("span", {}, name))),
      el("td", { class: "c-size muted" }, String(countInFolder(f))),
    );
    tr.addEventListener("click", () => navigateTo(f));
    makeDropTarget(tr, (refs) => moveGeneralRefsTo(refs, f));
    body.appendChild(tr);
  }

  const order = files.map((w) => w.rel);
  let bytes = 0;
  for (const w of files) {
    bytes += w.size;
    const nm = el("div", { class: "nm" }, el("span", { class: "ico" }, "📄"));
    if (searching && w.folder) nm.appendChild(el("span", { class: "sub" }, w.folder + "/"));
    nm.appendChild(el("span", {}, w.name));
    const tr = el("tr", { class: "row-file" + (state.genSel.has(w.rel) ? " selected" : "") },
      el("td", { class: "c-file" }, nm),
      el("td", { class: "c-size" }, humanSize(w.size)),
    );
    tr.addEventListener("click", (e) => handleRowClick(e, w.rel, order, state.genSel, state.genLast, renderGeneral));
    tr.addEventListener("dblclick", () => openGeneral(w));     // doble click → abre en ComfyUI
    tr.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      if (!state.genSel.has(w.rel)) { state.genSel.clear(); state.genSel.add(w.rel); state.genLast.v = w.rel; renderGeneral(); }
      fileMenu(e);
    });
    makeDraggable(tr, w.rel, state.genSel, renderGeneral);
    body.appendChild(tr);
  }

  $("#g-summary").textContent = t("sum_wf", { n: files.length, size: humanSize(bytes) });
  $("#g-selinfo").textContent = state.genSel.size ? t("sel_count", { n: state.genSel.size }) : "";
}

function selectedGeneral() {
  return state.general.workflows.filter((w) => state.genSel.has(w.rel));
}

function fileMenu(e) {
  const files = selectedGeneral();
  const refs = files.map((f) => f.rel);
  const single = files.length === 1 ? files[0] : null;
  showContextMenu(e.clientX, e.clientY, [
    { head: single ? single.name : t("ctx_head_many", { n: files.length }) },
    single ? { label: t("ctx_open"), onClick: () => openGeneral(single) } : null,
    single ? { label: t("ctx_rename"), onClick: () => renameGeneral(single) } : null,
    { label: t("ctx_move"), onClick: () => moveGeneralMany(refs) },
    single ? { label: t("ctx_dup"), onClick: () => duplicateGeneral(single) } : null,
    { label: t("ctx_addproj"), onClick: () => addToProject(refs) },
    { label: t("ctx_export"), onClick: () => exportRefs(refs, single ? single.name.replace(/\.json$/, "") : "workflows") },
    { sep: true },
    { label: t("ctx_delete"), danger: true, onClick: () => deleteGeneralMany(files) },
  ]);
}

function folderMenu(e, folder) {
  showContextMenu(e.clientX, e.clientY, [
    { head: folder.split("/").pop() },
    { label: t("ctx_open_folder"), onClick: () => navigateTo(folder) },
    { label: t("ctx_new_sub"), onClick: () => newFolderIn(folder) },
    { label: t("ctx_rename_folder"), onClick: () => renameFolderGeneral(folder) },
    { label: t("ctx_export_folder"), onClick: () => exportFolderGeneral(folder) },
    { sep: true },
    { label: t("ctx_delete_folder"), danger: true, onClick: () => deleteFolderGeneral(folder) },
  ]);
}

function openGeneral(w) {
  state.lastOpened = { scope: "general", rel: w.rel, name: w.name };
  openWorkflow({
    fetchUrl: `${API}/workflows/content?rel=${encodeURIComponent(w.rel)}`,
    name: w.name, storePath: storePathFor(w.rel, true), statusNode: $("#g-status"),
  });
}

// Guardado rápido (vista General): sobrescribe el workflow abierto desde el gestor; si no hay, "Guardar como".
async function saveIntoGeneral() {
  const lo = state.lastOpened;
  if (lo && lo.scope === "general" && lo.rel) {
    const ser = window.parent && window.parent.bswmSerializeGraph;
    const data = typeof ser === "function" ? ser() : null;
    if (!data) { setStatus($("#g-status"), t("st_no_canvas"), "error"); return; }
    try {
      const r = await postJSON(`${API}/workflows/import`, { name: lo.rel, content: data, overwrite: true });
      setStatus($("#g-status"), t("st_saved_to", { name: r.rel }), "ok");
      await loadGeneral();
    } catch (e) { setStatus($("#g-status"), e.message, "error"); }
    return;
  }
  return saveCanvasGeneral();
}

// Guarda el lienzo actual de ComfyUI dentro de la carpeta del gestor (Guardar como).
async function saveCanvasGeneral() {
  const ser = window.parent && window.parent.bswmSerializeGraph;
  const data = typeof ser === "function" ? ser() : null;
  if (!data) { setStatus($("#g-status"), t("st_no_canvas"), "error"); return; }
  const def = (state.lastOpened && state.lastOpened.scope === "general") ? state.lastOpened.name : "";
  const folderOpts = state.general.folders.map((f) => ({ value: f, label: f === "" ? t("folder_root") : f }));
  const v = await showForm(t("f_save_canvas"), [
    { key: "name", label: t("f_save_name"), type: "text", value: def, placeholder: "workflow.json" },
    { key: "folder", label: t("th_folder"), type: "select", value: state.genPath, options: folderOpts },
    { key: "overwrite", label: t("f_overwrite"), type: "checkbox", value: false },
  ], t("btn_save"));
  if (!v || !v.name) return;
  const rel = v.folder ? v.folder + "/" + v.name : v.name;
  try {
    const r = await postJSON(`${API}/workflows/import`, { name: rel, content: data, overwrite: v.overwrite });
    setStatus($("#g-status"), t("st_saved_to", { name: r.rel }), "ok");
    await loadGeneral();
  } catch (e) { setStatus($("#g-status"), e.message, "error"); }
}

async function renameGeneral(w) {
  const v = await showForm(t("f_rename"), [{ key: "name", label: t("f_new_name"), type: "text", value: w.name }], t("btn_confirm"));
  if (!v || !v.name) return;
  await apiThen($("#g-status"), () => postJSON(`${API}/workflows/rename`, { rel: w.rel, new_name: v.name }), loadGeneral);
}

async function moveGeneralMany(refs) {
  if (!refs.length) return;
  const opts = state.general.folders.map((f) => ({ value: f, label: f === "" ? t("folder_root") : f }));
  const v = await showForm(t("f_move_title"), [
    { key: "folder", label: t("th_folder"), type: "select", value: state.genPath, options: opts },
  ], t("btn_confirm"));
  if (!v) return;
  await apiThen($("#g-status"), async () => {
    for (const rel of refs) await postJSON(`${API}/workflows/move`, { rel, dest_folder: v.folder });
  }, loadGeneral);
}

async function duplicateGeneral(w) {
  const v = await showForm(t("f_duplicate"), [{ key: "name", label: t("f_dup_name"), type: "text", value: "", placeholder: w.name }], t("btn_confirm"));
  if (!v) return;
  await apiThen($("#g-status"), () => postJSON(`${API}/workflows/duplicate`, { rel: w.rel, new_name: v.name || null }), loadGeneral);
}

async function deleteGeneralMany(files) {
  if (!files.length) return;
  const msg = files.length === 1
    ? t("confirm_delete_wf", { name: files[0].name })
    : t("confirm_delete_wf", { name: files.length + " workflows" });
  const ok = await showConfirm(t("btn_delete"), msg, t("btn_delete"), true);
  if (!ok) return;
  await apiThen($("#g-status"), async () => {
    for (const f of files) await postJSON(`${API}/workflows/delete`, { rel: f.rel });
  }, loadGeneral);
}

async function newFolderIn(parent) {
  const v = await showForm(t("f_new_folder"), [{ key: "folder", label: t("f_folder_name"), type: "text", value: "" }], t("btn_confirm"));
  if (!v || !v.folder) return;
  const folder = parent ? parent + "/" + v.folder : v.folder;
  await apiThen($("#g-status"), () => postJSON(`${API}/workflows/mkdir`, { folder }), loadGeneral);
}

async function renameFolderGeneral(folder) {
  const v = await showForm(t("f_rename_folder"), [{ key: "name", label: t("f_new_name"), type: "text", value: folder.split("/").pop() }], t("btn_confirm"));
  if (!v || !v.name) return;
  await apiThen($("#g-status"), async () => {
    const res = await postJSON(`${API}/workflows/rename-folder`, { folder, new_name: v.name });
    if (state.genPath === folder || state.genPath.startsWith(folder + "/")) state.genPath = res.folder;
  }, loadGeneral);
}

function exportFolderGeneral(folder) {
  postJSON(`${API}/export`, { mode: "general_folder", folder }).then(startExportPolling).catch((e) => alert(e.message));
}

async function deleteFolderGeneral(folder) {
  const ok = await showConfirm(t("ctx_delete_folder"), t("confirm_delete_folder", { name: folder }), t("btn_delete"), true);
  if (!ok) return;
  await apiThen($("#g-status"), async () => {
    await postJSON(`${API}/workflows/delete-folder`, { folder });
    if (state.genPath === folder || state.genPath.startsWith(folder + "/")) state.genPath = folder.includes("/") ? folder.split("/").slice(0, -1).join("/") : "";
  }, loadGeneral);
}

// ---------- traspaso desde la carpeta de ComfyUI ----------
async function transferFromComfy() {
  let data;
  try { data = await getJSON(`${API}/comfy/list`); } catch (e) { alert(e.message); return; }
  if (data.same_as_root) { alert(t("tr_same")); return; }
  const all = data.workflows;
  if (!all.length) { alert(t("tr_empty")); return; }

  const sel = new Set();
  const modal = $("#modal");
  $("#modal-title").textContent = t("tr_title");
  const body = $("#modal-body");
  body.innerHTML = "";
  body.appendChild(el("div", { class: "muted", style: "margin-bottom:8px" }, t("tr_desc")));
  const filter = el("input", { type: "text", placeholder: t("tr_filter") });
  const list = el("div", { class: "pick-list" });
  const dest = el("input", { type: "text", placeholder: "(root)" });
  const move = el("input", { type: "checkbox" });
  const ok = $("#modal-ok"), cancel = $("#modal-cancel");
  const updateGo = () => { ok.textContent = t("tr_go", { n: sel.size }); ok.disabled = sel.size === 0; };
  const render = () => {
    list.innerHTML = "";
    for (const w of all) {
      if (!matchTerms(w.rel, filter.value)) continue;
      const cb = el("input", { type: "checkbox" });
      cb.checked = sel.has(w.rel);
      cb.addEventListener("change", () => { if (cb.checked) sel.add(w.rel); else sel.delete(w.rel); updateGo(); });
      const row = el("div", { class: "pick-row" }, cb,
        el("span", { class: "pk-name" }, w.rel), el("span", { class: "pk-size" }, humanSize(w.size)));
      row.addEventListener("click", (e) => { if (e.target !== cb) { cb.checked = !cb.checked; cb.dispatchEvent(new Event("change")); } });
      list.appendChild(row);
    }
  };
  filter.addEventListener("input", render);
  body.appendChild(el("div", { class: "pick-toolbar" }, filter,
    el("button", { class: "btn small", onclick: () => { all.forEach((w) => { if (matchTerms(w.rel, filter.value)) sel.add(w.rel); }); render(); updateGo(); } }, t("tr_all")),
    el("button", { class: "btn small", onclick: () => { sel.clear(); render(); updateGo(); } }, t("tr_none_sel"))));
  body.appendChild(list);
  body.appendChild(el("label", { class: "field" }, el("span", {}, t("f_into_folder")), dest));
  body.appendChild(el("label", { class: "field inline" }, move, el("span", {}, t("tr_move"))));
  render();
  ok.className = "btn primary"; cancel.textContent = t("btn_cancel");
  updateGo();
  modal.classList.remove("hidden");
  const close = () => { modal.classList.add("hidden"); ok.disabled = false; ok.removeEventListener("click", onOk); cancel.removeEventListener("click", onCancel); };
  const onOk = async () => {
    const refs = [...sel];
    close();
    try {
      const res = await postJSON(`${API}/comfy/transfer`, { refs, dest_folder: dest.value.trim(), move: move.checked });
      setStatus($("#g-status"), t("tr_result", { n: res.copied.length, s: res.skipped.length }), "ok");
      await loadGeneral();
    } catch (e) { setStatus($("#g-status"), e.message, "error"); }
  };
  const onCancel = () => close();
  ok.addEventListener("click", onOk); cancel.addEventListener("click", onCancel);
}

// Opciones de subcarpeta de un proyecto para un <select>: (raíz) + existentes + "＋ nueva…".
function subfolderOptions(p) {
  const opts = [{ value: "", label: t("sub_root") }];
  if (p) for (const s of p.subfolders) opts.push({ value: s, label: s });
  opts.push({ value: "__new__", label: t("sub_new") });
  return opts;
}
// Campo "subfolder" (select dependiente de `pidKey`) + campo "new_sub" (texto, visible si __new__).
function subfolderFields(pidKey, initialSub) {
  return [
    { key: "subfolder", label: t("f_target_sub"), type: "select", value: initialSub || "",
      options: (vals) => subfolderOptions(state.projects.find((p) => p.id === vals[pidKey])) },
    { key: "new_sub", label: t("f_sub_name"), type: "text", value: "", placeholder: "imagen/v01",
      show: (vals) => vals.subfolder === "__new__" },
  ];
}
function resolveSub(v) { return v.subfolder === "__new__" ? (v.new_sub || "") : v.subfolder; }

// ---------- añadir a proyecto (desde general) ----------
async function addToProject(refs) {
  refs = Array.isArray(refs) ? refs : [refs];
  if (!refs.length) return;
  if (!state.projects.length) {
    await refreshProjects();
    if (!state.projects.length) { alert(t("p_empty")); return; }
  }
  const projOpts = state.projects.map((p) => ({ value: p.id, label: p.name }));
  const target = state.activeProject || state.projects[0].id;
  const v = await showForm(t("f_addproj_title"), [
    { key: "pid", label: t("f_target_project"), type: "select", value: target, options: projOpts },
    ...subfolderFields("pid", ""),
    { key: "allow_multi", label: t("f_allow_multi"), type: "checkbox", value: false },
  ], t("btn_confirm"));
  if (!v) return;
  const subfolder = resolveSub(v);
  const errs = [];
  for (const rel of refs) {
    try {
      await postJSON(`${API}/projects/add-current`, { pid: v.pid, rel, subfolder, allow_multi: v.allow_multi });
    } catch (e) { errs.push(`${rel.split("/").pop()}: ${e.message}`); }
  }
  await refreshProjects();
  if (errs.length) setStatus($("#g-status"), errs[0], "error");
  else setStatus($("#g-status"), t("st_done"), "ok");
}

// helper: ejecuta una llamada y refresca, mostrando errores en `node`
async function apiThen(node, fn, after) {
  try { await fn(); if (after) await after(); setStatus(node, t("st_done"), "ok"); }
  catch (e) { setStatus(node, e.message, "error"); }
}

// ============================================================
//  VISTA PROYECTOS
// ============================================================
async function refreshProjects() {
  const data = await getJSON(`${API}/projects`);
  state.projects = data.projects;
  state.activeProject = data.active_project;
  const valid = (id) => !!(id && state.projects.find((p) => p.id === id));
  if (!valid(state.selectedProject)) {
    const remembered = localStorage.getItem("bswm_last_project");
    state.selectedProject = valid(remembered) ? remembered
      : (valid(state.activeProject) ? state.activeProject : (state.projects[0] && state.projects[0].id) || null);
  }
  renderProjectList();
  renderProjectDetail();
}

function selectProject(id) {
  state.selectedProject = id;
  state.projPath = "";
  state.projSel.clear();
  state.projLast = { v: null };
  try { localStorage.setItem("bswm_last_project", id); } catch (e) {}
  renderProjectList();
  renderProjectDetail();
}

function renderProjectList() {
  const box = $("#p-list");
  box.innerHTML = "";
  if (!state.projects.length) { box.appendChild(el("div", { class: "empty" }, t("p_empty"))); return; }
  for (const p of state.projects) {
    const item = el("div", { class: "proj-item" + (p.id === state.selectedProject ? " active" : "") , onclick: () => selectProject(p.id) },
      el("span", { class: "dot", style: `background:${p.color}` }),
      el("span", { class: "p-name" }, p.name),
      p.id === state.activeProject ? el("span", { class: "star", title: "active" }, "★") : null,
      el("span", { class: "p-count" }, String(p.count)),
    );
    box.appendChild(item);
  }
}

function currentProject() {
  return state.projects.find((p) => p.id === state.selectedProject) || null;
}

function renderProjectDetail() {
  const p = currentProject();
  $("#p-empty").classList.toggle("hidden", !!p);
  $("#p-content").classList.toggle("hidden", !p);
  if (!p) return;

  $("#p-dot").style.background = p.color;
  $("#p-title").textContent = p.name;
  $("#p-notes").textContent = p.notes || "";
  $("#p-storage-badge").innerHTML = "";
  $("#p-storage-badge").appendChild(el("span", { class: "badge " + (p.storage === "folder" ? "folder" : "virtual") },
    p.storage === "folder" ? t("storage_folder") : t("storage_virtual")));

  const activeBtn = $("#p-active-btn");
  activeBtn.textContent = p.id === state.activeProject ? t("btn_active") : t("btn_set_active");
  activeBtn.classList.toggle("primary", p.id === state.activeProject);

  if (!p.subfolders.includes(state.projPath)) state.projPath = "";
  renderProjCrumbs(p);
  renderProjectTable(p);
}

function renderProjCrumbs(p) {
  const box = $("#p-crumbs");
  box.innerHTML = "";
  const root = el("span", { class: "crumb" + (state.projPath === "" ? " current" : ""), onclick: () => setProjPath("") }, p.name);
  makeDropTarget(root, (refs) => moveProjectRefsTo(p, refs, ""));
  box.appendChild(root);
  let acc = "";
  (state.projPath ? state.projPath.split("/") : []).forEach((part, idx, arr) => {
    box.appendChild(el("span", { class: "sep" }, "/"));
    acc = acc ? acc + "/" + part : part;
    const cur = acc;
    const crumb = el("span", { class: "crumb" + (idx === arr.length - 1 ? " current" : ""), onclick: () => setProjPath(cur) }, part);
    makeDropTarget(crumb, (refs) => moveProjectRefsTo(p, refs, cur));
    box.appendChild(crumb);
  });
}

function setProjPath(path) {
  state.projPath = path;
  state.projSel.clear();
  state.projLast = { v: null };
  renderProjectDetail();
}

// Subcarpetas hijas directas de `path` dentro del proyecto.
function projChildFolders(p, path) {
  const prefix = path ? path + "/" : "";
  const set = new Set();
  for (const s of p.subfolders) {
    if (!s || !s.startsWith(prefix)) continue;
    const first = s.slice(prefix.length).split("/")[0];
    if (first) set.add(prefix + first);
  }
  return [...set].sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
}

function countProjFolder(p, path) {
  const prefix = path + "/";
  return p.items.filter((i) => i.subfolder === path || (i.subfolder || "").startsWith(prefix)).length;
}

function renderProjectTable(p) {
  const body = $("#p-body");
  body.innerHTML = "";
  const q = $("#p-filter").value.trim();
  const searching = !!q;

  let folders = [], items;
  if (searching) {
    items = p.items.filter((i) => matchTerms((i.alias || "") + " " + i.ref, q));
  } else {
    folders = projChildFolders(p, state.projPath);
    items = p.items.filter((i) => (i.subfolder || "") === state.projPath);
  }

  for (const f of folders) {
    const name = f.split("/").pop();
    const tr = el("tr", {
      class: "row-folder",
      ondblclick: () => setProjPath(f),
      oncontextmenu: (e) => { e.preventDefault(); projFolderMenu(e, p, f); },
    },
      el("td", { class: "c-file" }, el("div", { class: "nm" }, el("span", { class: "ico" }, "📁"), el("span", {}, name))),
      el("td", { class: "muted" }, ""),
      el("td", { class: "c-size muted" }, String(countProjFolder(p, f))),
    );
    tr.addEventListener("click", () => setProjPath(f));
    makeDropTarget(tr, (refs) => moveProjectRefsTo(p, refs, f));
    body.appendChild(tr);
  }

  const order = items.map((i) => i.ref);
  let bytes = 0;
  for (const i of items) {
    bytes += i.size;
    const nm = el("div", { class: "nm" }, el("span", { class: "ico" }, "📄"),
      searching && i.subfolder ? el("span", { class: "sub" }, i.subfolder + "/") : null,
      el("span", {}, i.name),
      i.shared ? el("span", { class: "badge shared", title: t("warn_shared") }, t("badge_shared")) : null,
      !i.exists ? el("span", { class: "badge missing" }, t("badge_missing")) : null,
    );
    const tr = el("tr", { class: "row-file" + (state.projSel.has(i.ref) ? " selected" : "") + (i.exists ? "" : " missing") },
      el("td", { class: "c-file" }, nm),
      el("td", { class: "muted" }, i.subfolder || t("folder_root")),
      el("td", { class: "c-size" }, humanSize(i.size)),
    );
    tr.addEventListener("click", (e) => handleRowClick(e, i.ref, order, state.projSel, state.projLast, () => renderProjectTable(p)));
    tr.addEventListener("dblclick", () => openProjectItem(p, i));     // doble click → abre en ComfyUI
    tr.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      if (!state.projSel.has(i.ref)) { state.projSel.clear(); state.projSel.add(i.ref); state.projLast.v = i.ref; renderProjectTable(p); }
      projItemMenu(e, p);
    });
    makeDraggable(tr, i.ref, state.projSel, () => renderProjectTable(p));
    body.appendChild(tr);
  }
  $("#p-summary").textContent = t("sum_wf", { n: items.length, size: humanSize(bytes) });
  $("#p-selinfo").textContent = state.projSel.size ? t("sel_count", { n: state.projSel.size }) : "";
}

function projFolderMenu(e, p, folder) {
  showContextMenu(e.clientX, e.clientY, [
    { head: folder.split("/").pop() },
    { label: t("ctx_open_folder"), onClick: () => setProjPath(folder) },
    { label: t("ctx_new_sub"), onClick: () => addSubfolderIn(p, folder) },
    { sep: true },
    { label: t("ctx_delete_folder"), danger: true, onClick: () => removeSubfolder(p, folder) },
  ]);
}

async function moveProjectRefsTo(p, refs, subfolder) {
  refs = refs.filter((ref) => {
    const it = p.items.find((x) => x.ref === ref);
    return it && (it.subfolder || "") !== subfolder;   // ignora los que ya están ahí
  });
  if (!refs.length) return;
  await apiThen($("#p-status"), async () => {
    for (const ref of refs) await postJSON(`${API}/projects/move`, { pid: p.id, ref, target_pid: p.id, target_subfolder: subfolder });
  }, refreshProjects);
}

async function addSubfolderIn(p, parent) {
  const v = await showForm(t("f_add_sub"), [{ key: "name", label: t("f_sub_name"), type: "text", value: "" }], t("btn_confirm"));
  if (!v || !v.name) return;
  const name = parent ? parent + "/" + v.name : v.name;
  await apiThen($("#p-status"), () => postJSON(`${API}/projects/subfolder/add`, { id: p.id, name }), refreshProjects);
}

function selectedItems(p) {
  return p.items.filter((i) => state.projSel.has(i.ref));
}

function projItemMenu(e, p) {
  const items = selectedItems(p);
  const refs = items.map((i) => i.ref);
  const single = items.length === 1 ? items[0] : null;
  const folder = p.storage === "folder";
  showContextMenu(e.clientX, e.clientY, [
    { head: single ? single.name : t("ctx_head_many", { n: items.length }) },
    single ? { label: t("ctx_open"), onClick: () => openProjectItem(p, single) } : null,
    single ? { label: t("ctx_rename"), onClick: () => renameProjectItem(p, single) } : null,
    { label: t("ctx_move"), onClick: () => moveProjectMany(p, refs) },
    single ? { label: t("ctx_dup"), onClick: () => duplicateProjectItem(p, single) } : null,
    { label: t("ctx_export"), onClick: () => exportProjectRefs(p, items) },
    { sep: true },
    folder
      ? { label: t("ctx_delete"), danger: true, onClick: () => deleteProjectFilesMany(p, items) }
      : { label: t("ctx_remove_link"), onClick: () => removeLinksMany(p, items) },
    folder ? null : { label: t("ctx_delete"), danger: true, onClick: () => deleteProjectFilesMany(p, items) },
  ]);
}

function openProjectItem(p, i) {
  state.lastOpened = { scope: "project", pid: p.id, ref: i.ref, name: i.name };
  const storePath = (state.isUserRoot && i.under_user_root && i.storage === "virtual") ? "workflows/" + i.ref : null;
  openWorkflow({
    fetchUrl: `${API}/projects/content?pid=${encodeURIComponent(p.id)}&ref=${encodeURIComponent(i.ref)}`,
    name: i.name, storePath, statusNode: $("#p-status"),
  });
}

// Guardado rápido (proyecto): sobrescribe el workflow abierto de este proyecto; si no hay, "Guardar como".
async function saveIntoProject(p) {
  const lo = state.lastOpened;
  if (lo && lo.scope === "project" && lo.pid === p.id && lo.ref) {
    const ser = window.parent && window.parent.bswmSerializeGraph;
    const data = typeof ser === "function" ? ser() : null;
    if (!data) { setStatus($("#p-status"), t("st_no_canvas"), "error"); return; }
    const ref = lo.ref;
    const sub = ref.includes("/") ? ref.slice(0, ref.lastIndexOf("/")) : "";
    const name = ref.split("/").pop();
    try {
      const r = await postJSON(`${API}/projects/save-canvas`, { pid: p.id, name, subfolder: sub, content: data, overwrite: true });
      setStatus($("#p-status"), t("st_saved_to", { name: r.ref }), "ok");
      await refreshProjects();
    } catch (e) { setStatus($("#p-status"), e.message, "error"); }
    return;
  }
  return saveCanvasProject(p);
}

// Guarda el lienzo actual de ComfyUI dentro del proyecto (en la subcarpeta actual).
async function saveCanvasProject(p) {
  const ser = window.parent && window.parent.bswmSerializeGraph;
  const data = typeof ser === "function" ? ser() : null;
  if (!data) { setStatus($("#p-status"), t("st_no_canvas"), "error"); return; }
  const def = (state.lastOpened && state.lastOpened.scope === "project" && state.lastOpened.pid === p.id) ? state.lastOpened.name : "";
  const v = await showForm(t("f_save_canvas"), [
    { key: "name", label: t("f_save_name"), type: "text", value: def, placeholder: "workflow.json" },
    { key: "subfolder", label: t("f_target_sub"), type: "select", value: state.projPath, options: subfolderOptions(p) },
    { key: "new_sub", label: t("f_sub_name"), type: "text", value: "", placeholder: "imagen/v01", show: (vv) => vv.subfolder === "__new__" },
    { key: "overwrite", label: t("f_overwrite"), type: "checkbox", value: false },
  ], t("btn_save"));
  if (!v || !v.name) return;
  try {
    const r = await postJSON(`${API}/projects/save-canvas`, { pid: p.id, name: v.name, subfolder: resolveSub(v), content: data, overwrite: v.overwrite });
    setStatus($("#p-status"), t("st_saved_to", { name: r.ref }), "ok");
    await refreshProjects();
  } catch (e) { setStatus($("#p-status"), e.message, "error"); }
}

async function renameProjectItem(p, i) {
  const v = await showForm(t("f_rename"), [{ key: "name", label: t("f_new_name"), type: "text", value: i.name }], t("btn_confirm"));
  if (!v || !v.name) return;
  await apiThen($("#p-status"), () => postJSON(`${API}/projects/rename`, { pid: p.id, ref: i.ref, new_name: v.name }), refreshProjects);
}

async function moveProjectMany(p, refs) {
  if (!refs.length) return;
  const projOpts = state.projects.map((x) => ({ value: x.id, label: x.name }));
  const v = await showForm(t("f_move_title"), [
    { key: "pid", label: t("f_target_project"), type: "select", value: p.id, options: projOpts },
    ...subfolderFields("pid", state.projPath),
  ], t("btn_confirm"));
  if (!v) return;
  const target_subfolder = resolveSub(v);
  await apiThen($("#p-status"), async () => {
    for (const ref of refs) await postJSON(`${API}/projects/move`, { pid: p.id, ref, target_pid: v.pid, target_subfolder });
  }, refreshProjects);
}

async function duplicateProjectItem(p, i) {
  const projOpts = state.projects.map((x) => ({ value: x.id, label: x.name }));
  const v = await showForm(t("f_duplicate"), [
    { key: "name", label: t("f_dup_name"), type: "text", value: "", placeholder: i.name },
    { key: "target_pid", label: t("f_dup_target"), type: "select", value: p.id, options: projOpts },
    ...subfolderFields("target_pid", i.subfolder),
  ], t("btn_confirm"));
  if (!v) return;
  const target_subfolder = resolveSub(v);
  await apiThen($("#p-status"), () => postJSON(`${API}/projects/duplicate`, {
    pid: p.id, ref: i.ref, new_name: v.name || null, target_pid: v.target_pid, target_subfolder,
  }), refreshProjects);
}

async function removeLinksMany(p, items) {
  if (!items.length) return;
  const name = items.length === 1 ? items[0].name : items.length + " workflows";
  const ok = await showConfirm(t("ctx_remove_link"), t("confirm_remove_link", { name }), t("btn_confirm"));
  if (!ok) return;
  await apiThen($("#p-status"), async () => {
    for (const i of items) if (i.link_id) await postJSON(`${API}/projects/unlink`, { link_id: i.link_id });
  }, refreshProjects);
}

async function deleteProjectFilesMany(p, items) {
  if (!items.length) return;
  const name = items.length === 1 ? items[0].name : items.length + " workflows";
  const ok = await showConfirm(t("btn_delete"), t("confirm_delete_wf", { name }), t("btn_delete"), true);
  if (!ok) return;
  await apiThen($("#p-status"), async () => {
    for (const i of items) await postJSON(`${API}/projects/delete-file`, { pid: p.id, ref: i.ref });
  }, refreshProjects);
}

async function removeSubfolder(p, s) {
  await apiThen($("#p-status"), () => postJSON(`${API}/projects/subfolder/remove`, { id: p.id, name: s }), refreshProjects);
}

// ---------- crear / editar proyecto ----------
async function projectForm(existing) {
  const isEdit = !!existing;
  const storageOpts = [
    { value: "virtual", label: t("f_storage_virtual") },
    { value: "folder", label: t("f_storage_folder") },
  ];
  const gitOpts = [
    { value: "none", label: t("f_git_none") },
    { value: "studio", label: t("f_git_studio") },
    { value: "dedicated", label: t("f_git_dedicated") },
    { value: "local", label: t("f_git_local") },
  ];
  const cur = existing || { name: "", color: "#AC1F23", storage: "virtual", folder: "", git: { mode: "none", remote_url: "" }, notes: "" };
  const fields = [
    { key: "name", label: t("f_name"), type: "text", value: cur.name },
    { key: "color", label: t("f_color"), type: "color", value: cur.color },
    { key: "storage", label: t("f_storage"), type: "select", value: cur.storage, options: storageOpts },
    { key: "folder", label: t("lbl_server_path"), type: "path", value: cur.folder || "", placeholder: "/path/on/server/projects/pepe", show: (v) => v.storage === "folder" },
    { key: "git_mode", label: t("f_git_mode"), type: "select", value: (cur.git || {}).mode || "none", options: gitOpts },
    { key: "remote_url", label: t("f_remote_url"), type: "text", value: (cur.git || {}).remote_url || "", placeholder: "git@… / https://…", show: (v) => v.git_mode === "dedicated" },
    { key: "notes", label: t("f_notes"), type: "textarea", value: cur.notes || "" },
  ];
  const v = await showForm(isEdit ? t("f_edit_project") : t("f_new_project"), fields, t("btn_save"));
  if (!v || !v.name) return;
  const payload = {
    name: v.name, color: v.color, storage: v.storage,
    // Solo enviamos carpeta si el almacenamiento es "folder"; así, al cambiar a virtual, la carpeta
    // (que queda oculta pero conserva su valor) no fuerza de nuevo el modo folder.
    folder: v.storage === "folder" ? v.folder : "",
    git: { mode: v.git_mode, remote_url: v.remote_url }, notes: v.notes,
  };
  try {
    if (isEdit) {
      await postJSON(`${API}/projects/update`, { id: existing.id, ...payload });
    } else {
      const res = await postJSON(`${API}/projects/create`, payload);
      state.selectedProject = res.project.id;
    }
    await refreshProjects();
  } catch (e) {
    setStatus($("#p-status"), e.message, "error");
    alert(e.message);
  }
}

async function deleteProject(p) {
  const v = await showForm(t("confirm_delete_project", { name: p.name }).replace(/<\/?b>/g, ""), [
    { key: "_", type: "html", html: `<div class="muted">${t("confirm_delete_project", { name: p.name })}</div>` },
    ...(p.storage === "folder" ? [{ key: "delete_files", label: t("confirm_delete_files"), type: "checkbox", value: false }] : []),
  ], t("btn_delete"));
  if (!v) return;
  await apiThen($("#p-status"), () => postJSON(`${API}/projects/delete`, { id: p.id, delete_files: !!v.delete_files }), async () => {
    state.selectedProject = null; await refreshProjects();
  });
}

async function toggleActive(p) {
  const id = p.id === state.activeProject ? null : p.id;
  await apiThen($("#p-status"), () => postJSON(`${API}/projects/active`, { id }), refreshProjects);
}

// ============================================================
//  EXPORTACIÓN (.zip en segundo plano)
// ============================================================
async function exportRefs(refs, name) {
  if (!refs.length) { alert(t("none_selected")); return; }
  try { await postJSON(`${API}/export`, { mode: "general_selection", refs }); startExportPolling(); }
  catch (e) { alert(e.message); }
}
async function exportProjectRefs(p, items) {
  if (!items.length) { alert(t("none_selected")); return; }
  try { await postJSON(`${API}/export`, { mode: "project_selection", pid: p.id, refs: items.map((i) => i.ref) }); startExportPolling(); }
  catch (e) { alert(e.message); }
}

function renderExportJobs(jobs) {
  const boxes = $$('[data-jobs="export"]');
  boxes.forEach((box) => {
    if (!jobs.length) { box.innerHTML = `<div class="muted">—</div>`; return; }
    box.innerHTML = "";
    for (const j of jobs) {
      const pct = j.total > 0 ? Math.min(100, (j.done / j.total) * 100) : (j.state === "done" ? 100 : 0);
      box.appendChild(el("div", { class: "job state-" + j.state },
        el("div", { class: "job-head" },
          el("span", { class: "state-pill" }, j.state),
          el("span", { class: "job-name" }, j.name + ".zip"),
          el("span", { class: "spacer" }),
          j.ready ? el("a", { class: "btn small primary", href: `${API}/export/download?id=${j.id}` }, "⬇") : null,
        ),
        el("div", { class: "job-meta" }, `${j.done}/${j.total}` + (j.error ? " · " + j.error : "")),
        el("div", { class: "bar" }, el("div", { style: `width:${pct}%` })),
      ));
      // Auto-descarga al quedar listo.
      if (j.ready && !state.exportSeen.has(j.id)) {
        state.exportSeen.add(j.id);
        const a = el("a", { href: `${API}/export/download?id=${j.id}` });
        document.body.appendChild(a); a.click(); a.remove();
      }
    }
  });
}

async function pollExportsOnce() {
  try {
    const { jobs } = await getJSON(`${API}/export/status`);
    renderExportJobs(jobs);
    return jobs.some((j) => j.state === "queued" || j.state === "running");
  } catch (e) { return false; }
}

function startExportPolling() {
  pollExportsOnce();
  if (state.pollTimer) return;
  state.pollTimer = setInterval(async () => {
    const active = await pollExportsOnce();
    if (!active) { clearInterval(state.pollTimer); state.pollTimer = null; }
  }, 1000);
}

// ============================================================
//  VISTA GIT
// ============================================================
function gitRepoOptions() {
  const sel = $("#git-repo");
  const prev = sel.value || state.gitRepo;
  sel.innerHTML = "";
  sel.appendChild(el("option", { value: "studio" }, t("repo_studio")));
  for (const p of state.projects) {
    if (p.storage === "folder") sel.appendChild(el("option", { value: p.id }, t("repo_project", { name: p.name })));
  }
  sel.value = [...sel.options].some((o) => o.value === prev) ? prev : "studio";
  state.gitRepo = sel.value;
}

async function loadGit() {
  if (!state.projects.length) { try { await refreshProjects(); } catch (e) {} }
  gitRepoOptions();
  const det = state.config && state.config.git;
  const banner = $("#git-banner");
  const available = det && det.git && det.git.available;
  $$("#view-git button").forEach((b) => { if (b.id !== "git-refresh") b.disabled = !available; });
  if (!available) {
    banner.className = "git-banner off";
    banner.textContent = t("git_off");
    $("#git-info").innerHTML = ""; $("#git-changes").innerHTML = ""; $("#git-log").innerHTML = "";
    return;
  }
  let gh = "";
  if (det.gh && det.gh.available) gh = t(det.gh.authed ? "git_gh_authed" : "git_gh_anon", { ghv: det.gh.version });
  banner.className = "git-banner ok";
  banner.textContent = t("git_ok", { gv: det.git.version, gh });
  await refreshGitInfo();
}

function setGitActionsDisabled(disabled) {
  $$("#view-git button").forEach((b) => { if (b.id !== "git-refresh") b.disabled = disabled; });
}

async function refreshGitInfo() {
  const repo = $("#git-repo").value;
  state.gitRepo = repo;
  setStatus($("#git-status"), t("st_loading"));
  try {
    const info = await getJSON(`${API}/git/info?repo=${encodeURIComponent(repo)}`);
    const kv = $("#git-info");
    kv.innerHTML = "";
    // Bloqueo de seguridad: carpeta propia de ComfyUI o dentro de su repositorio.
    if (info.git_blocked) {
      setGitActionsDisabled(true);
      $("#git-banner").className = "git-banner warn";
      $("#git-banner").textContent = t(info.is_comfy_default ? "git_blocked_default" : "git_blocked_foreign");
      kv.appendChild(el("span", { class: "muted" }, info.toplevel || info.repo));
      $("#git-changes").innerHTML = ""; $("#git-changes-sum").textContent = ""; $("#git-log").innerHTML = "";
      setStatus($("#git-status"), "", "");
      return;
    }
    setGitActionsDisabled(false);
    const det = state.config && state.config.git;
    if (det && det.git && det.git.available) {
      const gh = det.gh && det.gh.available ? t(det.gh.authed ? "git_gh_authed" : "git_gh_anon", { ghv: det.gh.version }) : "";
      $("#git-banner").className = "git-banner ok";
      $("#git-banner").textContent = t("git_ok", { gv: det.git.version, gh });
    }
    if (!info.is_repo) {
      kv.appendChild(el("span", {}, t("git_not_repo")));
      $("#git-changes").innerHTML = ""; $("#git-changes-sum").textContent = ""; $("#git-log").innerHTML = "";
      $("#git-init").disabled = false;
      setStatus($("#git-status"), "", "");
      return;
    }
    kv.appendChild(el("span", { html: `<b>${info.repo}</b>` }));
    kv.appendChild(el("span", {}, t("git_repo_info", {
      branch: info.branch || "?", changes: info.changes,
      remote: info.remote_url ? t("git_remote_suffix") : "",
    })));
    // cambios
    const ch = $("#git-changes");
    ch.innerHTML = "";
    if (!info.changes_list.length) ch.appendChild(el("div", { class: "muted" }, t("no_changes")));
    else for (const c of info.changes_list) ch.appendChild(el("div", { class: "ch" }, el("code", {}, c.code), el("span", {}, c.path)));
    $("#git-changes-sum").textContent = info.changes ? `${info.changes}` : "";
    if (info.remote_url) $("#git-remote-url").value = info.remote_url;
    await refreshGitLog();
    setStatus($("#git-status"), "", "");
  } catch (e) {
    setStatus($("#git-status"), e.message, "error");
  }
}

async function refreshGitLog() {
  const repo = $("#git-repo").value;
  try {
    const { log } = await getJSON(`${API}/git/log?repo=${encodeURIComponent(repo)}&n=40`);
    const box = $("#git-log");
    box.innerHTML = "";
    if (!log.length) { box.appendChild(el("div", { class: "muted" }, t("no_history"))); return; }
    for (const c of log) {
      box.appendChild(el("div", { class: "ch" },
        el("code", {}, c.short),
        el("span", {}, c.subject),
        el("span", { class: "muted", style: "margin-left:auto" }, `${c.author} · ${fmtDate(c.date)}`),
      ));
    }
  } catch (e) { /* silencioso */ }
}

async function gitRun(kind, opts) {
  try {
    await postJSON(`${API}/git/run`, { repo: $("#git-repo").value, kind, ...opts });
    startGitPolling();
  } catch (e) { setStatus($("#git-status"), e.message, "error"); }
}

function renderGitJobs(jobs) {
  const box = $("#git-jobs");
  if (!jobs.length) { box.innerHTML = `<div class="muted">—</div>`; return; }
  box.innerHTML = "";
  for (const j of jobs) {
    box.appendChild(el("div", { class: "job state-" + j.state },
      el("div", { class: "job-head" },
        el("span", { class: "state-pill" }, j.state),
        el("span", { class: "job-name" }, j.label),
        el("span", { class: "spacer" }),
      ),
      (j.error || j.log) ? el("div", { class: "job-meta" }, j.error || j.log) : null,
    ));
  }
}

async function pollGitOnce() {
  try {
    const { jobs } = await getJSON(`${API}/git/jobs`);
    renderGitJobs(jobs);
    return jobs.some((j) => j.state === "queued" || j.state === "running");
  } catch (e) { return false; }
}
let gitTimer = null;
function startGitPolling() {
  pollGitOnce();
  if (gitTimer) return;
  gitTimer = setInterval(async () => {
    const active = await pollGitOnce();
    if (!active) { clearInterval(gitTimer); gitTimer = null; await refreshGitInfo(); }
  }, 1200);
}

// ============================================================
//  VISTA AJUSTES
// ============================================================
function loadSettings() {
  $("#s-root").value = state.isUserRoot ? "" : (state.config.workflows_root || "");
  $("#s-db-path").textContent = state.config.db_path || "";
}

async function saveRoot(path) {
  await apiThen($("#s-root-status"), async () => { await postJSON(`${API}/config/root`, { path }); await loadConfig(); }, async () => {
    loadSettings(); await loadGeneral();
  });
}

// ============================================================
//  navegación / arranque
// ============================================================
function switchView(view) {
  $$(".tab").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  ["general", "projects", "git", "settings"].forEach((v) =>
    $("#view-" + v).classList.toggle("active", v === view));
  if (view === "general") loadGeneral();
  if (view === "projects") refreshProjects();
  if (view === "git") loadGit();
  if (view === "settings") loadSettings();
}

function rerenderActive() {
  const active = document.querySelector(".view.active");
  if (!active) return;
  if (active.id === "view-general") renderGeneral();
  if (active.id === "view-projects") { renderProjectList(); renderProjectDetail(); }
  if (active.id === "view-git") loadGit();
  if (active.id === "view-settings") loadSettings();
}

function wireEvents() {
  $$(".tab").forEach((b) => b.addEventListener("click", () => switchView(b.dataset.view)));
  $$(".lang-btn").forEach((b) => b.addEventListener("click", () => setLang(b.dataset.lang)));
  $("#help-btn").addEventListener("click", openHelp);
  $("#help-close").addEventListener("click", closeHelp);
  $("#help-modal").addEventListener("click", (e) => { if (e.target.id === "help-modal") closeHelp(); });

  // General
  $("#g-refresh").addEventListener("click", loadGeneral);
  $("#g-filter").addEventListener("input", () => { state.genSel.clear(); state.genLast = { v: null }; renderGeneral(); });
  $("#g-save-into").addEventListener("click", saveIntoGeneral);
  $("#g-save").addEventListener("click", saveCanvasGeneral);
  $("#g-newfolder").addEventListener("click", () => newFolderIn(state.genPath));
  $("#g-import").addEventListener("click", () => importFiles("general"));
  $("#g-from-comfy").addEventListener("click", transferFromComfy);
  $("#g-export-sel").addEventListener("click", () => exportRefs([...state.genSel], "workflows"));

  // Projects
  $("#p-new").addEventListener("click", () => projectForm(null));
  $("#p-empty-new").addEventListener("click", () => projectForm(null));
  $("#p-edit").addEventListener("click", () => { const p = currentProject(); if (p) projectForm(p); });
  $("#p-delete").addEventListener("click", () => { const p = currentProject(); if (p) deleteProject(p); });
  $("#p-active-btn").addEventListener("click", () => { const p = currentProject(); if (p) toggleActive(p); });
  $("#p-save-into").addEventListener("click", () => { const p = currentProject(); if (p) saveIntoProject(p); });
  $("#p-save").addEventListener("click", () => { const p = currentProject(); if (p) saveCanvasProject(p); });
  $("#p-add-sub").addEventListener("click", () => { const p = currentProject(); if (p) addSubfolderIn(p, state.projPath); });
  $("#p-export").addEventListener("click", async () => {
    const p = currentProject(); if (!p) return;
    try { await postJSON(`${API}/export`, { mode: "project", pid: p.id }); startExportPolling(); } catch (e) { alert(e.message); }
  });
  $("#p-export-sel").addEventListener("click", () => {
    const p = currentProject(); if (!p) return;
    exportProjectRefs(p, p.items.filter((i) => state.projSel.has(i.ref)));
  });
  $("#p-filter").addEventListener("input", () => { const p = currentProject(); if (p) { state.projSel.clear(); state.projLast = { v: null }; renderProjectTable(p); } });

  // Git
  $("#git-repo").addEventListener("change", refreshGitInfo);
  $("#git-refresh").addEventListener("click", async () => { await loadConfig(); loadGit(); });
  $("#git-init").addEventListener("click", () => gitRun("init", {}));
  $("#git-commit").addEventListener("click", () => gitRun("commit", { message: $("#git-commit-msg").value }));
  $("#git-remote").addEventListener("click", () => gitRun("remote", { url: $("#git-remote-url").value }));
  $("#git-push").addEventListener("click", () => gitRun("push", {}));
  $("#git-pull").addEventListener("click", () => gitRun("pull", {}));
  $("#git-gh").addEventListener("click", gitCreateGitHub);
  $("#git-clear").addEventListener("click", async () => { await postJSON(`${API}/git/clear`, {}); pollGitOnce(); });

  // export "clear finished"
  $$(".export-clear").forEach((b) => b.addEventListener("click", async () => {
    await postJSON(`${API}/export/clear`, {}); state.exportSeen.clear(); pollExportsOnce();
  }));

  // Settings
  $("#s-root-browse").addEventListener("click", async () => {
    const picked = await browseServerFolder($("#s-root").value.trim());
    if (picked != null) $("#s-root").value = picked;
  });
  $("#s-root-save").addEventListener("click", () => saveRoot($("#s-root").value.trim()));
  $("#s-root-reset").addEventListener("click", () => saveRoot(""));
  $("#s-db-export").addEventListener("click", () => { window.location = `${API}/db/export`; });
  $("#s-db-import").addEventListener("click", () => importFiles("db"));

  $("#file-input").addEventListener("change", onFilesPicked);
}

// ---------- importación de archivos ----------
let importTarget = "general";
function importFiles(target) {
  importTarget = target;
  const inp = $("#file-input");
  inp.multiple = target !== "db";
  inp.click();
}
async function onFilesPicked(e) {
  const files = [...e.target.files];
  e.target.value = "";
  if (!files.length) return;
  if (importTarget === "db") {
    try {
      const data = JSON.parse(await files[0].text());
      await postJSON(`${API}/db/import`, { data, merge: $("#s-db-merge").checked });
      setStatus($("#s-db-status"), t("st_done"), "ok");
      await refreshProjects();
    } catch (err) { setStatus($("#s-db-status"), err.message, "error"); }
    return;
  }
  // importar workflows a la raíz general
  for (const f of files) {
    try {
      const content = await f.text();
      await postJSON(`${API}/workflows/import`, { name: f.name, content, overwrite: false });
    } catch (err) { setStatus($("#g-status"), `${f.name}: ${err.message}`, "error"); }
  }
  await loadGeneral();
}

async function gitCreateGitHub() {
  const v = await showForm(t("f_gh_title"), [
    { key: "name", label: t("f_gh_name"), type: "text", value: "" },
    { key: "private", label: t("f_gh_private"), type: "checkbox", value: true },
  ], t("btn_confirm"));
  if (!v || !v.name) return;
  gitRun("gh_create", { name: v.name, private: v.private, push: true });
}

async function init() {
  wireEvents();
  $$(".lang-btn").forEach((b) => b.classList.toggle("active", b.dataset.lang === currentLang));
  applyI18n();
  try { await loadConfig(); } catch (e) { /* seguimos; las vistas mostrarán errores */ }
  await loadGeneral();
}

init();
