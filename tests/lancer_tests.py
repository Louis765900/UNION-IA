"""Lance toute la suite de tests UNION IA sans dépendance externe (pas besoin de pytest).

Usage :
    python tests/lancer_tests.py
"""
import importlib
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

MODULES = [
    "tests.test_stockage",
    "tests.test_memoire_active",
    "tests.test_llm_parser",
    "tests.test_cerveau",
    "tests.test_skills",
    "tests.test_auth",
    "tests.test_server",
]


def run():
    total = 0
    echecs = 0
    for nom_module in MODULES:
        module = importlib.import_module(nom_module)
        fns = [v for k, v in sorted(vars(module).items())
               if k.startswith("test_") and callable(v)]
        print(f"\n── {nom_module} ──")
        for fn in fns:
            total += 1
            try:
                fn()
                print(f"  OK  {fn.__name__}")
            except Exception:
                echecs += 1
                print(f"  KO  {fn.__name__}")
                traceback.print_exc()

    print(f"\n{'='*40}")
    print(f"Total : {total} tests | Réussis : {total - echecs} | Échecs : {echecs}")
    return 0 if echecs == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
