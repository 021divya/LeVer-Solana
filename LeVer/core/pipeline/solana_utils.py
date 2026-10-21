# ──────────────────────────────────────────────────────────────────────
# core/pipeline/solana_utils.py  — 🆕 NEW
# Solana-specific pipeline utilities.
#
# - "use anchor_lang" plausibility check
# - Anchor project structure validation
# - Rust source extraction helpers
# ──────────────────────────────────────────────────────────────────────

from __future__ import annotations

import re


def is_plausible_anchor_source(code: str) -> bool:
    """Quick regex-level check: does *code* look like an Anchor program?

    Checks for:
        1. ``use anchor_lang::prelude::*`` import
        2. At least one ``#[program]`` or ``#[derive(Accounts)]`` attribute
    """
    if not code or not code.strip():
        return False
    has_anchor_import = "use anchor_lang" in code
    has_program_attr = bool(
        re.search(r"#\[\s*program\s*\]", code)
        or re.search(r"#\[\s*derive\s*\(\s*Accounts\s*\)\s*\]", code)
    )
    return has_anchor_import and has_program_attr


def validate_anchor_project_structure(workspace: str) -> list[str]:
    """Check that *workspace* contains a valid Anchor project layout.

    Returns a list of errors (empty = valid).
    """
    import os

    errors: list[str] = []
    required_files = [
        "Anchor.toml",
        os.path.join("programs", "lever_target", "Cargo.toml"),
        os.path.join("programs", "lever_target", "src", "lib.rs"),
    ]
    for rel_path in required_files:
        full_path = os.path.join(workspace, rel_path)
        if not os.path.isfile(full_path):
            errors.append(f"Missing required file: {rel_path}")
    return errors


def extract_program_id(anchor_toml_content: str) -> str | None:
    """Extract the program ID from an Anchor.toml file's content."""
    match = re.search(
        r'\[\s*programs\s*\.\s*localnet\s*\]\s*\n\s*\w+\s*=\s*"([^"]+)"',
        anchor_toml_content,
    )
    return match.group(1) if match else None
