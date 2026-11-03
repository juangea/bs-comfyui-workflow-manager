# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Utilidades comunes: errores de usuario, seguridad de rutas, formato y JSON atómico.

Sin dependencias externas (solo stdlib). `safe_join` / `is_within` son las mismas defensas
anti path-traversal que usa el model-manager: toda ruta que venga de la red pasa por aquí.
"""
import errno
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import time

# Extensión canónica de los workflows de ComfyUI.
WORKFLOW_EXTENSIONS = {".json"}

# Nombres que nunca mostramos/operamos como workflow (índices internos de ComfyUI y dotfiles).
IGNORED_BASENAMES = {".index.json"}

# Mensajes (EN) de los errores que ve el usuario. La UI los traduce por código (`err_<code>`).
ERROR_MESSAGES = {
    "bad_path": "Path not allowed: {path}",
    "outside_root": "Path is outside the allowed folder: {path}",
    "empty_name": "The name can't be empty.",
    "bad_name": "Invalid name: {name}",
    "not_workflow": "Not a workflow file: {path}",
    "not_found": "Not found: {path}",
    "exists": "Already exists: {path}",
    "same_folder": "Source and destination are the same.",
    "root_forbidden": "This can't be done on the root folder.",
    "folder_not_found": "Folder not found: {path}",
    "folder_absolute": "Use an absolute path on the ComfyUI server: {path}",
    "folder_forbidden": "This folder can't be used for a project: {path}",
    "folder_unusable": "The folder can't be used on the server: {detail}",
    "project_unknown": "Unknown project.",
    "project_name_required": "The project name is required.",
    "project_exists": "A project named {name} already exists.",
    "already_linked": "{file} already belongs to project {project}.",
    "not_linked": "This workflow isn't linked to that project.",
    "bad_db": "This isn't a valid projects database.",
    "nothing_to_export": "There's nothing to export.",
    "export_not_ready": "The export isn't ready.",
    "missing_field": "Missing field: {field}",
    "git_missing": "git isn't installed on this system.",
    "git_no_folder": "Git needs a project with its own folder.",
    "git_blocked": "This folder is inside ComfyUI's own folders or Git repository, so Git is disabled to avoid conflicts.",
    "git_bad_url": "Remote URL not allowed: {url}",
    "git_bad_name": "Invalid repository name: {name}",
    "git_bad_commit": "Invalid commit: {commit}",
    "git_unknown_op": "Unknown Git operation: {op}",
    "git_failed": "{detail}",
    "unknown_user": "Unknown ComfyUI user.",
    "folder_in_use": "This folder overlaps with the folder of project {project}: {path}",
    "folder_has_project": "This folder overlaps with the project {project}, so it can't be changed here.",
    "bad_json": "Not a valid workflow file: {name}",
    "copy_changed": "The copy has changed since then, so it wasn't removed: {path}",
}


class UserError(ValueError):
    """Error esperable que se muestra al usuario. `code` permite traducirlo en la UI."""

    def __init__(self, code, **params):
        self.code = code
        self.params = {k: str(v) for k, v in params.items()}
        template = ERROR_MESSAGES.get(code, code)
        try:
            message = template.format(**self.params)
        except (KeyError, IndexError):
            message = template
        super().__init__(message)


def fold_case(text):
    """Texto para comparar rutas: en Linux, `Render` y `render` son carpetas distintas."""
    return text.lower() if sys.platform in ("win32", "darwin") else text


def is_local_abs(path):
    """True si es una ruta absoluta de ESTE sistema (una BD importada puede traer las de otro)."""
    path = str(path or "")
    if os.name == "nt":
        return bool(os.path.splitdrive(path)[0]) and os.path.isabs(path)
    return path.startswith("/")


def is_workflow_file(path):
    """True si el archivo parece un workflow editable (.json y no un índice interno)."""
    base = os.path.basename(path)
    if base in IGNORED_BASENAMES or base.startswith("."):
        return False
    return os.path.splitext(path)[1].lower() in WORKFLOW_EXTENSIONS


def looks_like_workflow(path):
    """True si el archivo es de verdad un workflow de ComfyUI (formato normal o de API).

    Para borrar en bloque: en una carpeta de proyecto también puede haber package.json, configuraciones…
    """
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    if isinstance(data.get("nodes"), list):
        return True
    return bool(data) and all(isinstance(v, dict) and "class_type" in v for v in data.values())


def safe_join(root, *parts):
    """Une `root` con `parts` garantizando que el resultado queda DENTRO de `root`.

    Protege los endpoints HTTP (servir estáticos, leer, escribir, borrar, mover) frente a
    path-traversal (`..`), rutas absolutas y saltos de unidad en Windows.

    Lanza UserError (ValueError) si el resultado se saldría de `root`.
    """
    root_abs = os.path.abspath(root)

    # Ninguna parte puede ser absoluta ni traer unidad propia (C:\, \\server\...).
    for part in parts:
        if part is None:
            continue
        if os.path.isabs(part) or os.path.splitdrive(str(part))[0]:
            raise UserError("bad_path", path=part)

    final = os.path.abspath(os.path.join(root_abs, *[str(p) for p in parts if p is not None]))

    root_n = os.path.normcase(root_abs)
    final_n = os.path.normcase(final)
    try:
        common = os.path.commonpath([root_n, final_n])
    except ValueError:
        # Unidades distintas en Windows -> commonpath lanza ValueError.
        raise UserError("outside_root", path=final)
    if common != root_n:
        raise UserError("outside_root", path=final)
    return final


def is_within(root, candidate):
    """True si `candidate` está dentro de `root` (o es `root`)."""
    try:
        root_n = os.path.normcase(os.path.realpath(root))
        cand_n = os.path.normcase(os.path.realpath(candidate))
        return os.path.commonpath([root_n, cand_n]) == root_n
    except ValueError:
        return False


def is_link(path):
    """True si la propia carpeta es un enlace simbólico o una unión de Windows."""
    parent, name = os.path.split(os.path.abspath(path))
    return os.path.normcase(os.path.realpath(path)) != os.path.normcase(os.path.join(os.path.realpath(parent), name))


def same_path(a, b):
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


_WINDOWS_BAD_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def usable_name(name):
    """False si el sistema no guardaría el archivo con ese nombre.

    En Windows, `a:b` escribiría en un flujo oculto de `a`; `a.` y `a ` son el mismo archivo que `a`.
    """
    if "\0" in name:
        return False
    return os.name != "nt" or not (_WINDOWS_BAD_CHARS.search(name) or name.endswith((" ", ".")))


def reserved_name(name):
    """True para nombres que no conviene crear: Windows 11 admite `aux.json`, las versiones anteriores no."""
    return os.name == "nt" and name.split(".")[0].rstrip(" ").upper() in _WINDOWS_RESERVED


def normalize_rel(rel):
    """Normaliza una ruta relativa que llega de la red a componentes seguros con '/'.

    Colapsa vacíos y rechaza '..' y rutas absolutas. Devuelve la ruta con '/'. Lanza UserError si es
    insegura. '\\' solo separa en Windows: en Linux es parte del nombre, igual que los espacios de los
    extremos, y cambiarlos haría operar sobre otro archivo. No exige que el nombre valga en el disco: una
    subcarpeta de un proyecto sin carpeta propia solo es una etiqueta. Eso lo comprueba `workflows.abs_path`.
    """
    rel = str(rel or "")
    if os.name == "nt":
        rel = rel.replace("\\", "/")
    parts = [p for p in rel.split("/") if p not in ("", ".")]
    for p in parts:
        if p == ".." or os.path.isabs(p) or os.path.splitdrive(p)[0] or "\0" in p:
            raise UserError("bad_path", path=rel)
    return "/".join(parts)


def check_new_folder(rel):
    """Nombre para una carpeta nueva. Si empieza por punto, el árbol no la mostraría, ni lo que se guarde en ella."""
    if any(p.startswith(".") or not usable_name(p) or reserved_name(p) for p in rel.split("/")):
        raise UserError("bad_name", name=rel)


def join_rel(folder, name):
    if not folder or not name:
        return folder or name
    return f"{folder}/{name}"


def split_rel(rel):
    """Devuelve (carpeta, nombre) de una ruta relativa con '/'."""
    return tuple(rel.rsplit("/", 1)) if "/" in rel else ("", rel)


_UNSAFE_COMPONENT = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
MAX_COMPONENT = 100     # un nombre de proyecto muy largo no debe crear carpetas que luego no se pueden usar


def safe_component(name, fallback="item"):
    """Convierte un nombre arbitrario en un componente de carpeta válido en cualquier SO."""
    name = _UNSAFE_COMPONENT.sub("-", str(name or ""))[:MAX_COMPONENT].strip(" .-")
    # En cualquier sistema: la carpeta puede acabar compartida con uno que no los admita.
    if name.split(".")[0].rstrip(" ").upper() in _WINDOWS_RESERVED:
        name = "_" + name
    return name or fallback


def ensure_json_ext(name):
    """Garantiza que `name` termina en .json (para guardar/duplicar/renombrar workflows)."""
    name = str(name or "").strip()
    if not name:
        raise UserError("empty_name")
    if "/" in name or "\\" in name or name in (".", "..") or not usable_name(name) or reserved_name(name):
        raise UserError("bad_name", name=name)
    if not name.lower().endswith(".json"):
        name += ".json"
    return name


def load_json(path, default=None):
    """Lee un JSON; devuelve `default` si no existe o está corrupto."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


_UMASK = os.umask(0)
os.umask(_UMASK)


def _set_final_mode(tmp, dest):
    """Los temporales nacen con permisos 0600: el archivo final conserva los suyos o usa los normales.

    Si no, en una carpeta compartida los demás usuarios dejarían de poder leer los workflows.
    """
    try:
        mode = stat.S_IMODE(os.stat(dest).st_mode) if os.path.exists(dest) else 0o666 & ~_UMASK
        os.chmod(tmp, mode)
    except OSError:
        pass        # sistemas de archivos de red que no admiten cambiar permisos


def _replace(tmp, dest):
    """os.replace. En Windows, un antivirus o un indexador puede tener el archivo abierto un instante."""
    if os.name == "nt":
        for delay in (0.05, 0.1, 0.2):
            try:
                os.replace(tmp, dest)
                return
            except PermissionError:
                time.sleep(delay)
    os.replace(tmp, dest)


def write_atomic(path, data):
    """Escribe bytes de forma atómica (tmp + rename) creando el directorio si hace falta."""
    path = os.path.realpath(path)   # un enlace simbólico se conserva: se escribe en su destino
    dir_name = os.path.dirname(path)
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            try:
                os.fsync(fh.fileno())   # tras un corte de luz, el rename no debe dejar un archivo vacío
            except OSError:
                pass
        _set_final_mode(tmp, path)
        _replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def copy_atomic(src, dst):
    """Copia un archivo de forma atómica conservando su fecha (no deja destinos a medias)."""
    dst = os.path.realpath(dst)
    dir_name = os.path.dirname(dst)
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    os.close(fd)
    try:
        shutil.copyfile(src, tmp)
        info = os.stat(src)
        try:
            os.utime(tmp, ns=(info.st_atime_ns, info.st_mtime_ns))
        except OSError:
            pass    # sin fecha igual, la siguiente comparación lo copia otra vez: no se pierde nada
        _set_final_mode(tmp, dst)
        _replace(tmp, dst)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def move_file(src, dst):
    """Mueve un archivo: o queda en el destino, o sigue donde estaba.

    shutil.move copia y borra ante cualquier error del rename: con el archivo abierto deja dos copias, y
    en Windows puede perderlo escribiendo en un flujo oculto. Solo se copia entre discos distintos.
    """
    try:
        os.rename(src, dst)
        return
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise
    copy_atomic(src, dst)
    try:
        os.remove(src)
    except OSError:
        try:
            os.remove(dst)
        except OSError:
            pass
        raise


def move_tree(src, dst):
    """Mueve una carpeta. Entre discos distintos copia y borra; si no puede borrar, nada se ha perdido."""
    try:
        os.rename(src, dst)
        return
    except OSError as exc:
        if exc.errno != errno.EXDEV or is_link(src):
            raise
    shutil.copytree(src, dst, symlinks=True)
    shutil.rmtree(src)


def same_entry(a, b):
    """True si dos rutas son el mismo archivo (un nombre que solo cambia en mayúsculas, en un disco que no las distingue)."""
    try:
        return a.lower() == b.lower() and os.path.samefile(a, b)
    except OSError:
        return False


def save_json(path, data):
    # backslashreplace: un nombre no UTF-8 de Linux se guarda como escape JSON y se lee igual.
    write_atomic(path, json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8", "backslashreplace"))
