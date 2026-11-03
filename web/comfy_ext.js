// SPDX-License-Identifier: GPL-3.0-only
// Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
// BS Workflow Manager — integración con la interfaz de ComfyUI.
//
// Único .js que ComfyUI auto-carga (vía WEB_DIRECTORY). Hace cuatro cosas:
//   1. Registra una pestaña lateral con un <iframe> a /bs_workflow_manager/ (la app del gestor).
//   2. Registra el botón de guardar (barra superior) y "Save to Project…" (menú File).
//   3. Escucha los guardados de ComfyUI para actualizar la copia de la carpeta del proyecto. Así da
//      igual cómo se guarde (Ctrl+S, File > Save, nuestro botón): el comportamiento es siempre el mismo.
//   4. Abre los workflows que se arrastran desde el panel y se sueltan fuera de él, en el lienzo.
//
// La app del iframe (mismo origen) habla con ComfyUI mediante `window.parent.bswmBridge`.
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const APP_URL = "/bs_workflow_manager/";
const API = "/bs_workflow_manager/api";
const TAB_ID = "bs-workflow-manager";
const WORKFLOWS_DIR = "workflows/";
const CANVAS_DRAG_TYPE = "application/x-bswm-workflows";
const SIDEBAR_ICON = "bswm-sidebar-icon";
const DELETE_SETTLE_MS = 2000;

const TEXT = {
  en: {
    save: "Save workflow", save_short: "Save", save_to_project: "Save to Project…",
    tooltip: "BS Workflow Manager — organize your workflows by folders and projects",
    saved_mirror: "Also saved to the {project} project folder",
    mirror_failed: "Saved in ComfyUI, but the project folder couldn't be updated: {error}",
    open_failed: "{name} couldn't be opened.",
    err_folder_not_found: "Folder not found: {path}", err_not_found: "Not found: {path}", err_exists: "Already exists: {path}",
  },
  es: {
    save: "Guardar workflow", save_short: "Guardar", save_to_project: "Guardar en proyecto…",
    tooltip: "BS Workflow Manager — organiza tus workflows por carpetas y proyectos",
    saved_mirror: "Guardado también en la carpeta del proyecto {project}",
    mirror_failed: "Guardado en ComfyUI, pero no se pudo actualizar la carpeta del proyecto: {error}",
    open_failed: "No se ha podido abrir {name}.",
    err_folder_not_found: "Carpeta no encontrada: {path}", err_not_found: "No encontrado: {path}", err_exists: "Ya existe: {path}",
  },
};

function text(key, vars) {
  let lang = "en";
  try { lang = localStorage.getItem("bswm_lang") || "en"; } catch (e) { /* almacenamiento bloqueado */ }
  let s = (TEXT[lang] && TEXT[lang][key]) || TEXT.en[key] || key;
  for (const k in vars || {}) s = s.split("{" + k + "}").join(vars[k]);
  return s;
}

// Error del servidor en el idioma del panel, si está traducido.
function errorText(e) {
  const key = e && e.code ? "err_" + e.code : null;
  return key && TEXT.en[key] ? text(key, e.params) : String(e && e.message ? e.message : e);
}

function store() {
  return (app.extensionManager && app.extensionManager.workflow) || null;
}

function toast(severity, summary) {
  try {
    app.extensionManager.toast.add({ severity, summary, life: severity === "error" ? 8000 : 2500 });
  } catch (e) { /* frontends sin toast */ }
}

function relOf(path) {
  return path && path.startsWith(WORKFLOWS_DIR) ? path.slice(WORKFLOWS_DIR.length) : null;
}

async function postApi(route, body) {
  const res = await api.fetchApi(API + route, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || "HTTP " + res.status);
    err.code = data.code;
    err.params = data.params;
    throw err;
  }
  return data;
}

// ---------- Escucha de operaciones de ComfyUI ----------
const silentRenames = new Set();   // renombrados iniciados por el gestor, que ya los reconcilia
let hooksInstalled = false;
let dirtyStamp = 0;                // la app del iframe recarga el árbol cuando cambia
let saveFailed = false;
const pendingDeletes = new Map();  // rel -> temporizador del aviso de borrado
const overwritten = new Set();     // rutas que "Guardar como" está sustituyendo

// "Guardar como" sobre un archivo existente lo borra y lo vuelve a crear: no es un borrado de verdad.
function cancelPendingDelete(path) {
  const rel = relOf(path);
  if (rel && pendingDeletes.has(rel)) {
    clearTimeout(pendingDeletes.get(rel));
    pendingDeletes.delete(rel);
    overwritten.add(rel);
  }
}

async function afterSaved(rel, created = false) {
  dirtyStamp++;
  try {
    const { mirrored } = await postApi("/events/saved", { path: rel, created });
    dirtyStamp++;
    // Con el autoguardado, sería un aviso cada pocos segundos.
    if (mirrored && app.extensionManager?.setting?.get?.("Comfy.Workflow.AutoSave") !== "after delay") {
      toast("success", text("saved_mirror", { project: mirrored }));
    }
  } catch (e) {
    toast("error", text("mirror_failed", { error: errorText(e) }));
  }
}

function installHooks() {
  const s = store();
  if (!s || typeof s.$onAction !== "function" || hooksInstalled) return;
  hooksInstalled = true;
  s.$onAction(({ name, args, after, onError }) => {
    const wf = args && args[0];
    if (!wf) return;
    if (name === "saveWorkflow") cancelPendingDelete(wf.path);
    else if (name === "renameWorkflow" || name === "saveAs") cancelPendingDelete(args[1]);
    if (name === "saveWorkflow") {
      // Un archivo nuevo, salvo que sustituya a uno que se acaba de borrar con "Guardar como".
      const created = !overwritten.delete(relOf(wf.path)) && !!wf.isTemporary;
      after(() => { const rel = relOf(wf.path); if (rel) afterSaved(rel, created); });
      onError(() => { saveFailed = true; });
    } else if (name === "renameWorkflow") {
      const oldRel = relOf(wf.path);
      const newRel = relOf(args[1]);
      after(() => {
        dirtyStamp++;
        if (silentRenames.delete(oldRel) || !oldRel || !newRel) return;
        if (wf.isTemporary) return;
        postApi("/events/renamed", { old: oldRel, new: newRel })
          .catch((e) => toast("error", text("mirror_failed", { error: errorText(e) })))
          .then(() => { dirtyStamp++; });
      });
    } else if (name === "deleteWorkflow") {
      const rel = relOf(wf.path);
      // Se espera un momento: si enseguida empieza a guardarse en esa ruta, conserva sus proyectos.
      after(() => {
        dirtyStamp++;
        if (!rel) return;
        pendingDeletes.set(rel, setTimeout(() => {
          pendingDeletes.delete(rel);
          postApi("/events/deleted", { path: rel }).then(() => { dirtyStamp++; }).catch(console.error);
        }, DELETE_SETTLE_MS));
      });
    }
  });
}

// ---------- Pestañas ----------
// Misma llamada que usa ComfyUI al cambiar de pestaña: conserva los cambios sin guardar, porque carga
// el estado en memoria de la pestaña (`activeState`) y no el archivo del disco.
const QUIET_LOAD = { checkForRerouteMigration: false, deferWarnings: true, skipAssetScans: true };
let activation = Promise.resolve();

// Uno detrás de otro: dos cargas solapadas dejarían el lienzo con el workflow equivocado.
function activate(wf) {
  const result = activation.then(() => loadInTab(wf));
  activation = result.catch(() => {});
  return result;
}

async function loadInTab(wf) {
  const s = store();
  if (s.isActive(wf)) return;
  const alreadyLoaded = wf.isLoaded;
  if (!alreadyLoaded) await wf.load();
  const state = JSON.parse(JSON.stringify(wf.activeState));
  const loaded = await app.loadGraphData(state, true, true, wf, alreadyLoaded ? QUIET_LOAD : {});
  if (loaded !== false) return;
  // Una carga fallida deja el lienzo vacío con la pestaña anterior activa: guardar la sobrescribiría.
  // Se repinta esa pestaña, igual que hace ComfyUI.
  const retained = s.activeWorkflow;
  if (retained && retained.path !== wf.path && retained.isLoaded) {
    const tracker = retained.changeTracker;
    const initial = tracker.initialState;
    await app.loadGraphData(JSON.parse(JSON.stringify(retained.activeState)), true, true, retained, QUIET_LOAD);
    // Repintar la pestaña activa la da por recién guardada: debe seguir marcada si tenía cambios sin
    // guardar, o cerrarla los perdería sin avisar.
    tracker.initialState = initial;
    tracker.updateModified?.();
  }
  throw new Error(text("open_failed", { name: wf.filename }));
}

function find(rel) {
  const s = store();
  return s ? s.getWorkflowByPath(WORKFLOWS_DIR + rel) : null;
}

function isOpen(rel) {
  const s = store();
  const wf = find(rel);
  return !!(s && wf && s.isOpen(wf));
}

window.bswmBridge = {
  available: () => !!store(),

  // Estado que pinta el árbol: pestaña activa, abiertas y con cambios sin guardar.
  getState() {
    const s = store();
    if (!s) return { active: null, open: [], dirty: dirtyStamp };
    const a = s.activeWorkflow;
    return {
      dirty: dirtyStamp,
      active: a ? {
        rel: relOf(a.path), name: a.filename, modified: !!a.isModified, temporary: !!a.isTemporary,
      } : null,
      open: s.openWorkflows.map((w) => ({ rel: relOf(w.path), modified: !!w.isModified })),
    };
  },

  isOpen,

  // Una pestaña restaurada al arrancar está abierta, pero su contenido aún no se ha leído del disco.
  isLoaded(rel) {
    const wf = find(rel);
    return !!(wf && wf.isLoaded);
  },

  openUnder(folder) {
    const s = store();
    if (!s) return [];
    const prefix = WORKFLOWS_DIR + folder + "/";
    return s.openWorkflows.filter((w) => w.path.startsWith(prefix)).map((w) => relOf(w.path));
  },

  async sync() {
    const s = store();
    if (s) await s.syncWorkflows();
  },

  // Abre un workflow; si ya tiene pestaña, solo la activa.
  async open(rel) {
    const s = store();
    let wf = find(rel);
    if (!wf) {
      await s.syncWorkflows();
      wf = find(rel);
    }
    if (!wf) {
      const err = new Error("Not found: " + rel);
      err.code = "not_found";
      err.params = { path: rel };
      throw err;
    }
    const wasOpen = s.isOpen(wf);
    await activate(wf);
    return { switched: wasOpen };
  },

  // Renombra/mueve un workflow con pestaña abierta usando ComfyUI, para que la pestaña lo siga.
  async renameOpen(oldRel, newRel) {
    const s = store();
    const wf = find(oldRel);
    if (!wf) throw Object.assign(new Error("Not found: " + oldRel), { code: "not_found", params: { path: oldRel } });
    const rename = async (from, to) => {
      silentRenames.add(from);
      try {
        await s.renameWorkflow(wf, WORKFLOWS_DIR + to);
      } catch (e) {
        silentRenames.delete(from);
        throw e;
      }
    };
    if (oldRel.toLowerCase() !== newRel.toLowerCase()) {
      await rename(oldRel, newRel);
      return;
    }
    // Solo cambian mayúsculas: en Windows ComfyUI lo rechaza porque el destino "ya existe".
    const step = newRel.replace(/\.json$/i, ".bswm-rename.json");
    await rename(oldRel, step);
    try {
      await rename(step, newRel);
    } catch (e) {
      await rename(step, oldRel).catch(console.error);
      throw e;
    }
  },

  // Cierra la pestaña de un workflow que se va a borrar. false si el usuario lo cancela.
  async closeForDelete(rel) {
    const s = store();
    const wf = find(rel);
    if (!s || !wf || !s.isOpen(wf)) return true;
    await activate(wf);
    // El comando cierra la pestaña activa: nunca otra distinta de la que se va a borrar.
    if (!s.isActive(wf)) return false;
    await app.extensionManager.command.execute("Workspace.CloseWorkflow");
    return !s.isOpen(wf);
  },

  // Guardar nativo de ComfyUI: pide nombre si el workflow es nuevo. El espejo lo hace la escucha.
  async save() {
    const s = store();
    saveFailed = false;
    await app.extensionManager.command.execute("Comfy.SaveWorkflow");
    const a = s && s.activeWorkflow;
    const rel = a ? relOf(a.path) : null;
    // El comando no propaga los errores: solo muestra un aviso, y a quien llama le parece que ha ido bien.
    const failed = saveFailed || !!(a && !a.isTemporary && a.isModified);
    if (rel && !hooksInstalled && !a.isTemporary && !failed) await afterSaved(rel);
    return { rel, temporary: !!(a && a.isTemporary), failed };
  },

  // Guarda un workflow todavía sin archivo en una ruta concreta de la carpeta de ComfyUI.
  async saveActiveAs(rel) {
    const s = store();
    const wf = s.activeWorkflow;
    if (!wf || !wf.isTemporary) throw new Error("Not a new workflow");
    const path = WORKFLOWS_DIR + rel;
    const existing = s.getWorkflowByPath(path);
    if (existing && !existing.isTemporary) throw new Error("exists");
    await s.renameWorkflow(wf, path);
    const tracker = wf.changeTracker;
    if (tracker) (tracker.prepareForSave || tracker.checkState).call(tracker);
    await s.saveWorkflow(wf);
    return { rel };
  },

  // Acción pendiente pedida desde ComfyUI (menú File) para cuando la app del iframe esté lista.
  takePending() {
    const action = pendingAction;
    pendingAction = null;
    return action;
  },
};

let pendingAction = null;

// ---------- Arrastrar del panel al lienzo ----------
// Solo atiende los arrastres del panel: cualquier otro sigue llegando al manejador de ComfyUI.
function installCanvasDrop() {
  const ours = (e) => !!e.dataTransfer && [...e.dataTransfer.types].includes(CANVAS_DRAG_TYPE);
  const accept = (e) => {
    if (!ours(e)) return;
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = "copy";
  };
  window.addEventListener("dragenter", accept, true);
  window.addEventListener("dragover", accept, true);
  window.addEventListener("drop", async (e) => {
    if (!ours(e)) return;
    e.preventDefault();
    e.stopPropagation();
    try {
      for (const rel of JSON.parse(e.dataTransfer.getData(CANVAS_DRAG_TYPE))) {
        if (!isOpen(rel) || !window.bswmBridge.isLoaded(rel)) {
          await postApi("/workflow/prepare-open", { path: rel });
          await store().syncWorkflows();
        }
        await window.bswmBridge.open(rel);
      }
    } catch (err) {
      toast("error", errorText(err));
    }
  }, true);
}

// El icono de la barra lateral, en el círculo rojo de la marca.
function installSidebarIconStyle() {
  const style = document.createElement("style");
  style.textContent = `
    i.${SIDEBAR_ICON} {
      display: inline-flex; align-items: center; justify-content: center;
      width: 1.9em; height: 1.9em; border-radius: 50%;
      font-size: 14px; line-height: 1;
      background: #AC1F23; color: #FAF0DC;
    }
    button:hover i.${SIDEBAR_ICON} { background: #C24145; }
  `;
  document.head.appendChild(style);
}

function openPanel() {
  const sidebar = app.extensionManager && app.extensionManager.sidebarTab;
  if (sidebar && sidebar.activeSidebarTabId !== TAB_ID) sidebar.toggleSidebarTab(TAB_ID);
}

async function saveCommand() {
  try {
    await window.bswmBridge.save();
  } catch (e) {
    toast("error", String(e && e.message ? e.message : e));
  }
}

// ---------- Resize guard (igual que el model-manager) ----------
// Mientras se arrastra el borde del panel, el ratón pasa por encima del iframe y este "se traga"
// los eventos, atascando el redimensionado. Solución: desactivar pointer-events del iframe mientras
// hay un botón pulsado en la página padre, y reactivarlos al soltar.
function installResizeGuard(iframe) {
  if (window.__bswmResizeGuard) {
    window.__bswmResizeGuard.push(iframe);
    return;
  }
  const frames = [iframe];
  window.__bswmResizeGuard = frames;
  const setPE = (val) => frames.forEach((f) => { if (f) f.style.pointerEvents = val; });
  document.addEventListener("pointerdown", () => setPE("none"), true);
  window.addEventListener("pointerup", () => setPE("auto"), true);
  window.addEventListener("pointercancel", () => setPE("auto"), true);
  window.addEventListener("blur", () => setPE("auto"));
}

function buildIframe(el) {
  el.style.position = "relative";
  el.style.height = "100%";
  el.innerHTML = "";
  const iframe = document.createElement("iframe");
  iframe.src = APP_URL;
  iframe.title = "BS Workflow Manager";
  iframe.style.cssText =
    "position:absolute;inset:0;width:100%;height:100%;border:none;display:block;background:#1A1819;";
  el.appendChild(iframe);
  installResizeGuard(iframe);
}

function addFloatingButton() {
  if (document.getElementById("bs-wm-fab")) return;
  const btn = document.createElement("button");
  btn.id = "bs-wm-fab";
  btn.textContent = "BS Workflows";
  btn.title = "BS Workflow Manager";
  btn.style.cssText =
    "position:fixed;right:16px;bottom:56px;z-index:9999;padding:8px 12px;border-radius:8px;" +
    "border:1px solid #555;background:#222;color:#eee;cursor:pointer;font:13px sans-serif;";
  btn.onclick = () => window.open(APP_URL, "_blank");
  document.body.appendChild(btn);
}

app.registerExtension({
  name: "bonestudio.workflow_manager",
  commands: [
    {
      id: "BSWM.Save",
      icon: "pi pi-save",
      label: () => text("save"),
      function: saveCommand,
    },
    {
      id: "BSWM.SaveToProject",
      icon: "pi pi-folder-plus",
      label: () => text("save_to_project"),
      menubarLabel: () => text("save_to_project"),
      function: () => { pendingAction = "save-to-project"; openPanel(); },
    },
  ],
  menuCommands: [{ path: ["File"], commands: ["BSWM.SaveToProject"] }],
  actionBarButtons: [
    {
      icon: "icon-[lucide--save]",
      get label() { return text("save_short"); },
      get tooltip() { return text("save"); },
      onClick: saveCommand,
    },
  ],
  async setup() {
    installHooks();
    // El almacén de workflows puede no estar listo todavía: sin la escucha, los guardados no llegarían al proyecto.
    if (!hooksInstalled) {
      const retry = setInterval(() => { installHooks(); if (hooksInstalled) clearInterval(retry); }, 1000);
    }
    installCanvasDrop();
    installSidebarIconStyle();
    try {
      if (app.extensionManager && app.extensionManager.registerSidebarTab) {
        app.extensionManager.registerSidebarTab({
          id: TAB_ID,
          icon: `pi pi-folder-open ${SIDEBAR_ICON}`,
          title: "BS-WM",
          tooltip: text("tooltip"),
          type: "custom",
          render: buildIframe,
        });
        return;
      }
    } catch (e) {
      console.error("[BS Workflow Manager] registerSidebarTab failed:", e);
    }
    // Fallback si la API del sidebar no existe (versiones antiguas/futuras).
    addFloatingButton();
  },
});
