# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Enob-Studio S.L. and Juan Gea
"""Runner de tests sin dependencias (no necesita pytest ni ComfyUI).

Uso:
    python tests/selftest.py

Recorre los módulos test_*.py, ejecuta cada función test_* e informa PASS/FAIL.
Sale con código != 0 si algún test falla.
"""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)   # para importar el paquete `bswm`
sys.path.insert(0, HERE)   # para importar los módulos test_* y _fake

import test_util       # noqa: E402
import test_workflows  # noqa: E402
import test_projects   # noqa: E402
import test_git        # noqa: E402

MODULES = [test_util, test_workflows, test_projects, test_git]


def run():
    passed = failed = 0
    failures = []
    for mod in MODULES:
        fns = [getattr(mod, n) for n in sorted(dir(mod)) if n.startswith("test_")]
        for fn in fns:
            name = f"{mod.__name__}.{fn.__name__}"
            try:
                fn()
                passed += 1
                print(f"  PASS  {name}")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                failures.append((name, exc))
                print(f"  FAIL  {name}: {exc}")
    print(f"\n{passed} passed, {failed} failed")
    if failures:
        print("\n--- detalles ---")
        for name, exc in failures:
            print(f"\n[{name}]")
            traceback.print_exception(type(exc), exc, exc.__traceback__)
    return failed == 0


if __name__ == "__main__":
    print("== BS Workflow Manager — selftest ==")
    sys.exit(0 if run() else 1)
