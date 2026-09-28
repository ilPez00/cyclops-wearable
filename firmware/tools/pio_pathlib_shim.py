# Re-export the REAL stdlib pathlib (a package in 3.13+). The external
# site-packages dir below sits on PYTHONPATH and ships an ancient
# pathlib-1.0.1 single-module shim that would otherwise shadow the package
# and break every importlib.resources user (i.e. semantic_version ->
# pkg_resources -> platformio). Prepended to PYTHONPATH by `just fw-build`.
import importlib.util as _ilu
import os as _os
import sys as _sys
import sysconfig as _sc

_std = _sc.get_paths()["stdlib"]
_spec = _ilu.spec_from_file_location(
    "_stdlib_pathlib",
    _os.path.join(_std, "pathlib", "__init__.py"),
    submodule_search_locations=[_os.path.join(_std, "pathlib")],
)
_mod = _ilu.module_from_spec(_spec)
_sys.modules["_stdlib_pathlib"] = _mod
_spec.loader.exec_module(_mod)
globals().update({k: v for k, v in vars(_mod).items() if not k.startswith("__")})
_sys.modules[__name__] = _mod
