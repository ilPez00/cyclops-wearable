"""Minimal zero-dependency test runner (pytest not available in this env)."""
import importlib.util
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "brain"))
sys.path.insert(0, os.path.dirname(__file__))

def collect(mod):
    return [(n, getattr(mod, n)) for n in dir(mod) if n.startswith("test_") and callable(getattr(mod, n))]

def main():
    files = sys.argv[1:] or ["test_brain.py"]
    passed = failed = 0
    for f in files:
        spec = importlib.util.spec_from_file_location("t_" + os.path.basename(f)[:-3], f)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            print(f"LOAD ERROR {f}: {e}"); failed += 1; continue
        for name, fn in collect(mod):
            try:
                fn(); print(f"PASS {f}::{name}"); passed += 1
            except Exception as e:
                print(f"FAIL {f}::{name}: {e}")
                traceback.print_exc(); failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
