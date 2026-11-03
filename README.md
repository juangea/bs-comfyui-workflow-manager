# Bone-Studio Workflow Manager — for ComfyUI

> **EN** · Keep your production workflows organized: projects and folders in one tree, next to the
> canvas. Saves go to ComfyUI's workflows folder and, for projects with their own folder, to that folder
> too. Bulk export and optional Git versioning included. It runs in its own iframe (Nodes 2.0 proof).
>
> **ES** · Mantén organizados tus workflows de producción: proyectos y carpetas en un solo árbol, junto
> al lienzo. Se guardan en la carpeta de workflows de ComfyUI y, en proyectos con carpeta propia, también
> en esa carpeta. Incluye exportación masiva y versionado Git opcional. Funciona en su propio iframe
> (a prueba de Nodes 2.0).

![License: GPL v3](https://img.shields.io/badge/License-GPLv3-AC1F23.svg)
&nbsp;·&nbsp; Bilingual EN/ES &nbsp;·&nbsp; Python 3.10–3.13 &nbsp;·&nbsp; stdlib only

---

## Features

- **One tree** — projects and your regular workflows side by side, with search, multi-select,
  drag & drop and right-click menus.
- **Tab-aware opening** — click a workflow to open it. If it already has a tab, you go to that tab and
  keep any unsaved changes. Dots in the tree mark open tabs and unsaved changes.
- **Saving that just works** — every save writes to ComfyUI's workflows folder. If the workflow belongs
  to a project with its own folder, a copy is written there too. This works the same with the panel's
  **Save**, the **Save** button in the top bar, **File > Save** and `Ctrl+S`. **File > Save to Project…**
  saves the current workflow into a project.
- **Projects** — group workflows with subfolders. A project can be:
  - **without its own folder**: it only groups them, and the files stay where they are. A workflow belongs
    to one project unless you choose to share the same file (edits then affect every project using it).
  - **with its own folder**, picked by browsing the ComfyUI server: its files live in
    `workflows/<project>` and in that folder. If the copies differ when you open a workflow, the newest
    one is used (for example, after a `git pull`). If saving from ComfyUI would replace a different file
    that was only in the project folder, that file is kept as `name (conflict).json`.
- **Stays in sync with ComfyUI** — renames and deletions made from ComfyUI's own panel also update projects.
- **Export** — one workflow, a selection, a folder or a whole project, to a `.zip`.
- **Git** (optional) — per project folder: create a repository, commit, set a remote or create a GitHub
  repository (with `gh`), push/pull, browse history and restore. A project folder can also be part of a
  shared studio repository. Git is disabled for folders that belong to ComfyUI or its repository. A file
  deleted by a `git pull` stays in ComfyUI's copy: delete it from the panel to remove it from the project.

## Requirements

- ComfyUI (provides `aiohttp` and the PromptServer). **No `pip install`** needed: stdlib only.
- **Git features** need `git` on the ComfyUI server (and optionally `gh` for GitHub). Without them, Git
  options are disabled. **We never install them.**

## Install

**From ComfyUI-Manager (recommended):** search for **"Bone-Studio Workflow Manager"**, install and restart.

**Manual:** copy this folder into `ComfyUI/custom_nodes/` and restart ComfyUI. Open the **BS-WM** tab in
the sidebar.

## Usage

- **Open:** click a workflow. Ctrl/⌘-click and Shift-click select several.
- **Drag and drop:** a tip shows what will happen while you drag. Drop on a folder, a project or any
  workflow in the place you want.
  - **No key:** moves between folders of the same project, or adds a workflow from *Workflows* to a project.
  - **Ctrl/⌘:** also adds it to another project, and it stays in the first one. Between two projects
    with their own folder, the second one gets a copy.
  - **Shift:** moves it to another project and takes it out of the first one, or takes it out of the
    project if you drop it on *Workflows*.
- **Open by dragging:** drop workflows on the canvas to open them.
- **Undo:** after a move, use **Undo** in the status line or `Ctrl+Z`.
- **Own folders:** each project needs its own; two projects can't share a folder or be nested.
- **Keyboard:** `↑` `↓` move through the list, `Enter` opens, `F2` renames, `Del` deletes.
- **New project:** the **+** next to *Projects*, or drop workflows on that heading. Choosing its own
  folder is optional.
- **Import:** drag `.json` files from your computer onto the tree, or right-click a folder or project.
- **Save:** use any of the save options above. The bar at the top of the panel shows where the active
  workflow will be saved.

Use the **?** icon (top right, next to EN/ES) for in-app help.

## Upgrading from 1.0.x

Projects and links are kept. ComfyUI's workflows folder is now always the main location:

- If you had set a custom workflows root, it becomes a project with its own folder. Nothing in that
  folder is moved or deleted.
- Files of projects with their own folder are copied to `workflows/<project>` the first time you open them.
- Git now works on a project's own folder. To keep using a repository, give the project that folder.
- With `--multi-user`, each user has their own projects. Data from 1.0.x stays with the `default` user.

## Security note

ComfyUI has no login of its own, and this tool can list server folders and change workflow files. If you
start ComfyUI with `--listen`, anyone who can reach it on the network can use this panel, as with the rest
of ComfyUI. File operations are limited to workflow `.json` files, and Git remotes to normal transports.

---

## License / Licencia

**EN —** Code is licensed under the **GNU General Public License v3.0** (`GPL-3.0-only`); see
[`LICENSE`](LICENSE). Copyright © 2026 **Enob-Studio S.L. and Juan Gea**. As the sole copyright holders,
Enob-Studio S.L. and Juan Gea **reserve the right to relicense** this code under other terms (e.g.
Apache-2.0 or MIT) in the future.

- **Fonts:** the files under [`webapp/fonts/`](webapp/fonts) (Jost, Hanken Grotesk, IBM Plex Mono) are
  third-party fonts under the **SIL Open Font License 1.1** — see [`webapp/fonts/OFL.txt`](webapp/fonts/OFL.txt).
- **Brand:** the name **"Bone-Studio"** and the **BS-WM** logo are **trademarks of Enob-Studio S.L.**, all
  rights reserved, and are **not** covered by the GPL.

**ES —** El código se distribuye bajo la **Licencia Pública General de GNU v3.0** (`GPL-3.0-only`); ver
[`LICENSE`](LICENSE). Copyright © 2026 **Enob-Studio S.L. y Juan Gea**, que **se reservan el derecho a
relicenciar** el código bajo otros términos (p. ej. Apache-2.0 o MIT) en el futuro. Las **fuentes**
(`webapp/fonts/`) son de terceros bajo **SIL OFL 1.1**; la **marca** «Bone-Studio» y el logo **BS-WM** son
marcas de Enob-Studio S.L. (todos los derechos reservados, fuera de la GPL).

## Disclaimer / Descargo de responsabilidad

**EN — Use at your own risk.** This software is provided **"AS IS", without warranty of any kind**. It
reads, writes, moves, duplicates and deletes workflow files at your request, and can run Git operations
(commit, push, pull, restore). To the maximum extent permitted by law, Enob-Studio S.L. and Juan Gea are
**not liable** for any damage or data loss. (See also GPLv3 §§15–16 and [`NOTICE`](NOTICE).)

**ES — Úsalo bajo tu responsabilidad.** El software se ofrece **«tal cual», sin garantía de ningún tipo**.
Lee, escribe, mueve, duplica y borra archivos de workflow a petición tuya, y puede ejecutar operaciones
Git (commit, push, pull, restaurar). En la máxima medida permitida por la ley, Enob-Studio S.L. y Juan Gea
**no se responsabilizan** de ningún daño ni pérdida de datos.
