# Ensures index.py (and its sibling flat modules) are importable from tests/
# even though this project has no package structure (no __init__.py files).
# Having any conftest.py here makes pytest add this directory to sys.path.
