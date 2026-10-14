# ──────────────────────────────────────────────────────────────────────
# adapter_factory.py  — 🆕 NEW
# Factory function: target string → concrete TargetAdapter instance.
#
# Usage (from main_pipeline.py):
#     adapter = adapter_factory(args.target)   # "solidity" | "solana"
#
# Adding a new chain:
#     1. Create adapters/<chain>_adapter.py with a class inheriting TargetAdapter.
#     2. Add an entry to _REGISTRY below.
#     3. Done — core pipeline remains untouched.
# ──────────────────────────────────────────────────────────────────────

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.adapters.base import TargetAdapter


# ── Lazy registry ────────────────────────────────────────────────────
# Values are import-path strings so we never import heavy deps we don't need.
_REGISTRY: dict[str, tuple[str, str]] = {
    "solidity": ("core.adapters.solidity_adapter", "SolidityAdapter"),
    "solana":   ("core.adapters.solana_adapter",   "SolanaAdapter"),
    # Future:
    # "move":  ("core.adapters.move_adapter",  "MoveAdapter"),
    # "sui":   ("core.adapters.sui_adapter",   "SuiAdapter"),
}


def adapter_factory(target: str, **kwargs) -> "TargetAdapter":
    """Return a concrete TargetAdapter for *target* (case-insensitive).

    Parameters
    ----------
    target : str
        One of the keys in ``_REGISTRY`` (e.g. ``"solidity"``, ``"solana"``).
    **kwargs
        Forwarded to the adapter constructor.

    Raises
    ------
    ValueError
        If *target* is not recognised.
    """
    key = (target or "").strip().lower()
    if key not in _REGISTRY:
        supported = ", ".join(sorted(_REGISTRY))
        raise ValueError(
            f"Unknown target '{target}'. Supported targets: {supported}"
        )

    module_path, class_name = _REGISTRY[key]

    import importlib
    module = importlib.import_module(module_path)
    adapter_cls = getattr(module, class_name)
    return adapter_cls(**kwargs)
