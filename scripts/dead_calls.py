#!/usr/bin/env python3
"""Declared-never-called sweep (docs/37 §B4, docs/41 item 5).

For every function/method defined in brain/*.py, agent/*.py and every
`fun`/class in the Kotlin sources, verify at least one caller exists in
the tree. Unlisted dead code fails loudly (exit 1) — it gets an explicit
allowlist entry (acknowledged dead) or gets deleted. Never silent.

Usage: python3 scripts/dead_calls.py [--allow FILE]

Allowlist format: one `path:Name` per line, `#` comments. Lives next to
this script so the ack is versioned with the code it excuses.
"""

import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW_DEFAULT = os.path.join(ROOT, "scripts", "dead_calls_allowlist.txt")

PY_DIRS = ("brain", "agent", "app")
KT_DIRS = ("android/app/src/main/java", "android/core/src/main/kotlin")

# Caller evidence: all first-party Python (prod AND tests) + Kotlin.
# A symbol called only from tests/ is not dead, but it is prod-unwired:
# reported as WARN, exit stays 0. No callers anywhere = FAIL, exit 1.
SKIP_DIRS = (".git", ".pio", ".venv", "venv", "__pycache__", "node_modules",
             ".gradle", "build", ".physis")
TEST_DIRS = ("tests",)

# Framework-called: the runtime calls these, no in-tree caller exists.
PY_FRAMEWORK = {
    "do_GET", "do_POST", "do_PUT", "do_DELETE",  # http.server handler
    "log_message",  # BaseHTTPRequestHandler override
    "handle",  # socketserver dispatch
    "run", "serve_forever",  # entry points invoked by name
    "main",
}


def py_symbols():
    """{name: [defining files]} for module-level + method defs.
    Returns (symbols, class_names, subclassed, properties, files).
    A base class with an in-tree subclass is architecture, not dead code.
    A @property is called by attribute access (.name), not .name()."""
    found: dict[str, list[str]] = {}
    classes: set[str] = set()
    subclassed: set[str] = set()
    properties: set[str] = set()
    files: list[str] = []
    for d in PY_DIRS:
        base = os.path.join(ROOT, d)
        if not os.path.isdir(base):
            continue
        for fn in sorted(os.listdir(base)):
            if fn.endswith(".py"):
                files.append(os.path.join(base, fn))
    for path in files:
        try:
            src = open(path, encoding="utf-8").read()
            tree = ast.parse(src)
        except (SyntaxError, OSError):
            continue
        lines = src.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name.startswith("__"):
                    continue
                rel = os.path.relpath(path, ROOT)
                found.setdefault(node.name, []).append(rel)
                if isinstance(node, ast.ClassDef):
                    classes.add(node.name)
                    for b in node.bases:
                        if isinstance(b, ast.Name):
                            subclassed.add(b.id)
                        elif isinstance(b, ast.Attribute):
                            subclassed.add(b.attr)
                else:
                    # @property (or @x.setter): attribute access is the call
                    deco = "|".join(
                        getattr(d, "id", getattr(d, "attr", ""))
                        for d in node.decorator_list)
                    if "property" in deco or "setter" in deco:
                        properties.add(node.name)
    return found, classes, subclassed, properties, files


def repo_py_files():
    out = []
    for dp, dns, fns in os.walk(ROOT):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in sorted(fns):
            if fn.endswith(".py"):
                out.append(os.path.join(dp, fn))
    return out


def repo_xml_files():
    """AndroidManifest + layout/menu XML: .Class refs and onClick names."""
    out = []
    res = os.path.join(ROOT, "android", "app", "src", "main")
    for dp, dns, fns in os.walk(res):
        for fn in sorted(fns):
            if fn.endswith((".xml",)):
                out.append(os.path.join(dp, fn))
    return out


def py_callers(name: str, files: list[str], defining: list[str],
               is_class: bool = False, is_property: bool = False):
    """(prod_files, test_files) with a real or string-dispatched call."""
    pat = re.compile(r"(?<![\w.])" + re.escape(name) + r"\s*\(")
    attr = re.compile(r"\." + re.escape(name) + r"\s*\(")
    member = re.compile(r"""(?<![\w."'"])""" + re.escape(name) + r"\.")
    # bare refs: `x = Name`, `f(Name)`, `ThreadingHTTPServer(addr, H)`,
    # `.Name` in manifests. Classes match bare; functions only `= Name`
    # (callback handoff); properties match bare attribute reads (.running).
    bare = re.compile(r"[=,\(\[]\s*\.?" + re.escape(name) + r"\b")
    prop = re.compile(r"\." + re.escape(name) + r"\b")
    qpat = re.compile(r"""['"]""" + re.escape(name) + r"""['"]""")
    defset = set(defining)
    prod, test = [], []
    for path in files:
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            continue
        hit = False
        for line in text.splitlines():
            s = line.strip()
            if s.startswith(("def ", "async def ", "class ")) and name in s:
                continue  # its own definition
            if pat.search(line) or attr.search(line) or member.search(line):
                hit = True
                break
            if is_property and prop.search(line):
                hit = True
                break
            if bare.search(line):
                # classes: any bare ref counts (instantiation site).
                # functions: only `= Name` (callback handoff like
                # progress_cb = _on_step), not argument position.
                if is_class or re.search(r"=\s*\.?" + re.escape(name) + r"\b", line):
                    hit = True
                    break
        if not hit and path not in defset and qpat.search(text):
            hit = True  # string dispatch from another file
        if hit:
            rel = os.path.relpath(path, ROOT)
            (test if rel.split(os.sep)[0] in TEST_DIRS else prod).append(rel)
    return prod, test


def py_called(name: str, files: list[str], defining: list[str]) -> bool:
    p, t = py_callers(name, files, defining)
    return bool(p or t)


FUN_RE = re.compile(r"^\s*(?:override\s+|private\s+|public\s+|protected\s+|internal\s+)*(?:suspend\s+)?fun\s+(\w+)")
CLASS_RE = re.compile(r"^\s*(?:public\s+|private\s+|open\s+|abstract\s+|data\s+|sealed\s+)*(?:class|object|interface)\s+(\w+)")


def kt_symbols():
    found: dict[str, list[str]] = {}
    files: list[str] = []
    test_files: list[str] = []
    for d in KT_DIRS:
        base = os.path.join(ROOT, d)
        for dp, _, fns in os.walk(base):
            for fn in sorted(fns):
                if fn.endswith((".kt", ".java")):
                    files.append(os.path.join(dp, fn))
    # test source sets count as caller evidence (WARN), like tests/ in Python
    for d in ("android/app/src/test", "android/app/src/androidTest",
              "android/core/src/test"):
        base = os.path.join(ROOT, d)
        for dp, _, fns in os.walk(base):
            for fn in sorted(fns):
                if fn.endswith((".kt", ".java")):
                    test_files.append(os.path.join(dp, fn))
    for path in files:
        try:
            lines = open(path, encoding="utf-8").read().splitlines()
        except OSError:
            continue
        rel = os.path.relpath(path, ROOT)
        for line in lines:
            m = FUN_RE.match(line)
            if m and not m.group(1).startswith("_"):
                # override funs are framework callbacks (Activity lifecycle)
                if "override " in line:
                    continue
                found.setdefault(m.group(1), []).append(rel)
                continue
            m = CLASS_RE.match(line)
            if m:
                found.setdefault(m.group(1), []).append(rel)
    return found, files, test_files


def kt_called(name: str, files: list[str], xml_files: list[str],
              test_files: list[str] | None = None) -> tuple[bool, bool]:
    """(prod_called, test_only): test source sets are caller evidence
    (WARN), mirroring tests/ on the Python side."""
    pat = re.compile(r"(?<![\w.])" + re.escape(name) + r"\s*[\(\{<]")
    attr = re.compile(r"\." + re.escape(name) + r"\s*[\(\{<]")
    member = re.compile(r"""(?<![\w."'"])""" + re.escape(name) + r"\.")
    inherit = re.compile(r":\s*" + re.escape(name) + r"\b")
    decl = re.compile(r"(?:fun|class|object|interface)\s+(\w+)")

    def hit_in(paths: list[str]) -> bool:
        for path in paths:
            try:
                text = open(path, encoding="utf-8").read()
            except OSError:
                continue
            for line in text.splitlines():
                s = line.strip()
                m = decl.match(s)
                if m and m.group(1) == name:
                    continue  # its own declaration
                if (pat.search(line) or attr.search(line)
                        or member.search(line) or inherit.search(line)):
                    return True
        return False

    if hit_in(files):
        return True, False
    for path in xml_files:
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            continue
        if f".{name}" in text or f'"{name}"' in text:
            return True, False
    if test_files and hit_in(test_files):
        return True, True
    for path in files:
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            continue
        if f'"{name}"' in text:
            return True, False
    return False, False


def load_allow(path: str) -> set[str]:
    out = set()
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#"):
                out.add(line)
    return out


def main() -> int:
    allow_path = sys.argv[sys.argv.index("--allow") + 1] if "--allow" in sys.argv else ALLOW_DEFAULT
    allow = load_allow(allow_path)
    dead: list[str] = []

    syms, py_classes, py_subclassed, py_properties, _ = py_symbols()
    all_py = repo_py_files()
    warned: list[str] = []
    for name in sorted(syms):
        if name in PY_FRAMEWORK:
            continue
        if name in py_subclassed:
            continue  # base class with an in-tree subclass: architecture
        prod, test = py_callers(name, all_py, syms[name],
                                is_class=name in py_classes,
                                is_property=name in py_properties)
        if prod or test:
            if not prod:
                warned.append(f"{','.join(syms[name])}:{name} (tests only)")
            continue
        if not any(f"{f}:{name}" in allow or f"*:{name}" in allow
                   for f in syms[name]):
            dead.append(f"{','.join(syms[name])}:{name}")

    ksyms, kt_files, kt_tests = kt_symbols()
    xml_files = repo_xml_files()
    for name in sorted(ksyms):
        prod, test_only = kt_called(name, kt_files, xml_files, kt_tests)
        if prod:
            if test_only:
                warned.append(f"{','.join(ksyms[name])}:{name} (tests only)")
            continue
        if not any(f"{f}:{name}" in allow or f"*:{name}" in allow
                   for f in ksyms[name]):
            dead.append(f"{','.join(ksyms[name])}:{name}")

    if dead:
        print(f"DEAD ({len(dead)} declared-never-called):")
        for d in dead:
            print(f"  {d}")
        print("Allowlist (ack) or delete. See scripts/dead_calls_allowlist.txt.")
        return 1
    if warned:
        print(f"TEST-ONLY ({len(warned)} prod-unwired, called from tests/):")
        for w in warned:
            print(f"  {w}")
    total = len(syms) + len(ksyms)
    print(f"CLEAN ({total} symbols, all called or allowlisted)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
