# Bone-Studio Workflow Manager — for ComfyUI

> **EN** · Organize your ComfyUI workflows for production: a folder manager **plus** a project layer
> (an exportable internal database), bulk **export** and optional **Git** versioning — all from a
> built-in panel that lives in its own iframe (Nodes 2.0 proof).
>
> **ES** · Organiza tus workflows de ComfyUI para producción: un gestor de carpetas **más** una capa
> de proyectos (base de datos interna exportable), **exportación** masiva y **versionado Git**
> opcional — desde un panel propio dentro de un iframe (a prueba de Nodes 2.0).

![License: GPL v3](https://img.shields.io/badge/License-GPLv3-AC1F23.svg)
&nbsp;·&nbsp; Bilingual EN/ES &nbsp;·&nbsp; Python 3.10–3.13 &nbsp;·&nbsp; stdlib only

---

## Why / Por qué

Production studios end up with hundreds of workflows in one monolithic, unusable list. This tool
gives them structure two complementary ways, without changing how ComfyUI itself works.

## Features

- **General** — a folder manager over your ComfyUI workflows folder (configurable). **Open** a
  workflow in the canvas, **rename**, **move** between folders, **duplicate**, **delete**, **export**,
  or **add it to a project**. Multi-term search; tick rows and **Export selected** to a `.zip`.
- **Projects** — your own organization layer (an exportable internal JSON database) that links
  workflows to **projects** and **subfolders** (e.g. *pepe* → *imagen* / *video*), independent of where
  files live on disk. Each project is either:
  - **virtual** — tags only; the file stays in the general folder. By default a workflow belongs to
    **one** project; you can opt into linking the **same** file to several projects (it warns you, since
    edits propagate). **Duplicate** makes an independent copy.
  - **folder-backed** — its workflows physically live in a folder you choose; moving/renaming are real
    file operations.
- **Export** — single, bulk selection, a whole project, or a whole folder → `.zip`, built in the
  background.
- **Git** (optional) — pick a repository (the **studio** root or a project's folder) and **init**,
  **commit**, set a **remote** or **create a GitHub repo** (via `gh`), **push/pull** and browse
  **history**. Chosen per project: studio repo, dedicated repo, local-only, or none.
- **Own UI** in an iframe (doesn't use the node graph) → won't break with **Nodes 2.0**. **Bilingual
  EN/ES** with in-app help.

## Requirements

- ComfyUI (provides `aiohttp` and the PromptServer). **No `pip install`** needed — stdlib only.
- **Git features** require `git` (and optionally `gh` for GitHub) installed on the system. If they
  aren't present, the Git options are disabled. **We never install them.**

## Install

**Manual:** copy this folder into `ComfyUI/custom_nodes/` and restart ComfyUI. Open the **BS Workflows**
tab in the sidebar.

**From ComfyUI-Manager:** search **"Bone-Studio Workflow Manager"** → Install → restart.

## Usage

1. **General** — browse/search; *Open* loads a workflow in the canvas. Rename / Move / Duplicate /
   Delete / Export per row, or tick several and *Export selected*. *Add to project* links it.
2. **Projects** — *New* a project (virtual or folder-backed, pick a Git mode). Add workflows from the
   General tab, organize into subfolders, *Move* between projects/subfolders, *Duplicate* into another
   project, *Export* the project.
3. **Git** — pick the repository, *Init*, write a message and *Commit*, set a *Remote* or *Create on
   GitHub*, *Push/Pull*, review *History*.
4. **Settings** — change the workflows root (empty = ComfyUI default) and export/import the projects
   database.

Use the **?** icon (top-right, next to EN/ES) for in-app help.

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
