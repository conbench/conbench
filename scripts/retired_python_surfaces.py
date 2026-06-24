from __future__ import annotations


RETIRED_PYTHON_PACKAGE_ROOTS: tuple[str, ...] = (
    "benchadapt",
    "benchalerts",
    "benchclients",
    "benchconnect",
    "benchrun",
    "conbench_client",
    "conbenchlegacy",
)

RETIRED_PYTHON_MODULE_FILES: tuple[str, ...] = tuple(
    f"{name}.py" for name in RETIRED_PYTHON_PACKAGE_ROOTS
)

RETIRED_PYTHON_PATH_PREFIXES: tuple[str, ...] = (
    *RETIRED_PYTHON_PACKAGE_ROOTS,
    "legacy/conbenchlegacy",
)
