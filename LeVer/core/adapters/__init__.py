# ──────────────────────────────────────────────────────────────────────
# core/adapters/__init__.py  — 🆕 NEW
# Public surface for the adapter subsystem.
# ──────────────────────────────────────────────────────────────────────

from core.adapters.base import TargetAdapter          # noqa: F401 — ABC
from core.adapter_factory import adapter_factory       # noqa: F401 — factory fn
