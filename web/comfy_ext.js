// SPDX-License-Identifier: GPL-3.0-only
// Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
// BS Workflow Manager — cargador de la interfaz dentro de ComfyUI.
//
// Único .js que ComfyUI auto-carga (vía WEB_DIRECTORY). Registra una pestaña en la barra lateral
// cuyo contenido es un <iframe> a /bs_workflow_manager/ (app servida por nuestro backend). Así la
// UI no usa el sistema de nodos/widgets y no se rompe con Nodes 2.0.
//
// Además expone puentes en `window` (mismo origen) que la app del iframe invoca como
// `window.parent.bswmXxx(...)` para hablar con el grafo/los workflows de ComfyUI:
//   - bswmOpenWorkflow(payload)   → abre un workflow en el canvas (nativo si se puede, si no loadGraphData)
//   - bswmGetActiveWorkflow()     → devuelve {path, name} del workflow activo
import { app } from "../../scripts/app.js";

const APP_URL = "/bs_workflow_manager/";

// ---------- Puente: abrir un workflow ----------
// payload: { fetchUrl, name?, storePath? }
//   fetchUrl  = URL del backend que devuelve el JSON del workflow.
//   storePath = ruta conocida por ComfyUI (p.ej. "workflows/foo.json") para apertura nativa rastreada.
window.bswmOpenWorkflow = async function (payload) {
  payload = payload || {};
  try {
    // Siempre leemos el contenido real del workflow desde nuestro backend.
    const res = await fetch(payload.fetchUrl);
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();

    // Si el workflow lo conoce ComfyUI (vive en user/<u>/workflows), recuperamos su objeto para
    // que la pestaña quede ASOCIADA a él y "Guardar" escriba en el archivo correcto.
    let wf = null;
    if (payload.storePath) {
      try {
        const store = app.extensionManager && app.extensionManager.workflow;
        if (store && typeof store.getWorkflowByPath === "function") {
          wf = store.getWorkflowByPath(payload.storePath) || null;
        }
      } catch (e) { /* sin store: cargamos sin asociar */ }
    }

    // Cargamos SIEMPRE el JSON descargado. (No usamos store.openWorkflow porque abre la pestaña
    // pero no vuelca el grafo en el lienzo -> antes parecía "duplicar" el workflow abierto.)
    await app.loadGraphData(data, true, true, wf || payload.name || null);
    return { ok: true, tracked: !!wf };
  } catch (e) {
    console.error("[BS Workflow Manager] open workflow:", e);
    return { ok: false, error: String(e && e.message ? e.message : e) };
  }
};

// ---------- Puente: serializar el lienzo actual (para "Guardar en el gestor") ----------
window.bswmSerializeGraph = function () {
  try {
    const g = app.graph;
    if (!g) return null;
    if (typeof g.serialize === "function") return g.serialize();
    if (typeof g.asSerialisable === "function") return g.asSerialisable();
  } catch (e) {
    console.error("[BS Workflow Manager] serialize graph:", e);
  }
  return null;
};

// ---------- Puente: workflow activo ----------
window.bswmGetActiveWorkflow = function () {
  try {
    const store = app.extensionManager && app.extensionManager.workflow;
    const active = store && store.activeWorkflow;
    if (active) {
      return {
        path: active.path || active.key || null,           // p.ej. "workflows/foo.json"
        name: active.filename || active.name || null,
      };
    }
  } catch (e) {
    console.warn("[BS Workflow Manager] active workflow:", e);
  }
  return null;
};

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
  async setup() {
    try {
      if (app.extensionManager && app.extensionManager.registerSidebarTab) {
        app.extensionManager.registerSidebarTab({
          id: "bs-workflow-manager",
          icon: "pi pi-folder-open",
          title: "BS-WM",
          tooltip: "BS Workflow Manager — organiza tus workflows por carpetas y proyectos",
          type: "custom",
          render: buildIframe,
        });
        return;
      }
    } catch (e) {
      console.error("[BS Workflow Manager] registerSidebarTab falló:", e);
    }
    // Fallback si la API del sidebar no existe (versiones antiguas/futuras).
    addFloatingButton();
  },
});
