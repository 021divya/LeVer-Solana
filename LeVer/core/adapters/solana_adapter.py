# ──────────────────────────────────────────────────────────────────────
# core/adapters/solana_adapter.py  — SolanaAdapter(TargetAdapter)
#
# Implements the TargetAdapter interface for Solana / Anchor / Rust:
#   is_valid_source()          → delegates to solana_utils.is_plausible_anchor_source()
#   check_compilation()        → stages source into Anchor workspace, runs "anchor build"
#
# Implemented in this milestone:
#   ✅ is_valid_source
#   ✅ check_compilation
#
# Not yet implemented (will raise NotImplementedError):
#   ❌ generate_code        — requires AnchorCoder LLM agent
#   ❌ repair_code          — requires AnchorCoder LLM agent
#   ❌ generate_formal_spec — requires Kani harness generation
#   ❌ verify_spec          — requires "cargo kani" integration
#   ❌ generate_test_harness — requires Anchor test generation
#   ❌ run_tests            — requires "anchor test" + solana-test-validator
#   ❌ extract_counterexample — requires Solana log parser
# ──────────────────────────────────────────────────────────────────────

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from core.adapters.base import TargetAdapter


# Default timeout for `anchor build` (seconds).
_ANCHOR_BUILD_TIMEOUT_SECONDS = 300


class SolanaAdapter(TargetAdapter):
    """Adapter for Solana / Anchor targets (Anchor CLI + Kani Model Checker).

    Parameters
    ----------
    anchor_cli : str | None
        Path or command name for the Anchor CLI.  When *None*, the value
        from ``solana_config.ANCHOR_CLI`` is used (defaults to ``"anchor"``
        or the ``ANCHOR_CLI`` environment variable).
    program_name : str | None
        Anchor program crate name.  When *None*, the value from
        ``solana_config.ANCHOR_WORKSPACE_DEFAULTS["program_name"]`` is used
        (defaults to ``"lever_target"``).
    build_timeout : int
        Maximum seconds to wait for ``anchor build`` before timing out.
    """

    def __init__(
        self,
        *,
        anchor_cli: Optional[str] = None,
        program_name: Optional[str] = None,
        build_timeout: int = _ANCHOR_BUILD_TIMEOUT_SECONDS,
        **_kwargs: Any,
    ) -> None:
        from core.solana_config import ANCHOR_CLI, ANCHOR_WORKSPACE_DEFAULTS

        self._anchor_cli: str = anchor_cli or ANCHOR_CLI
        self._program_name: str = (
            program_name or ANCHOR_WORKSPACE_DEFAULTS["program_name"]
        )
        self._build_timeout: int = build_timeout

    # ── Code Generation ──────────────────────────────────────────────
    # Not yet implemented — requires AnchorCoder LLM agent (next milestone).

    def generate_code(
        self,
        requirement: str,
        properties: List[Dict],
        *,
        feedback_constraints: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> str:
        raise NotImplementedError(
            "SolanaAdapter.generate_code is not yet implemented. "
            "AnchorCoder LLM agent integration is planned for a future milestone."
        )

    def repair_code(
        self,
        current_code: str,
        feedback: str,
        *,
        properties: Optional[List[Dict]] = None,
        **kwargs: Any,
    ) -> str:
        raise NotImplementedError(
            "SolanaAdapter.repair_code is not yet implemented. "
            "AnchorCoder LLM agent integration is planned for a future milestone."
        )

    # ── Validation ───────────────────────────────────────────────────

    def is_valid_source(self, code: str) -> bool:
        """Quick plausibility check via ``is_plausible_anchor_source``.

        Delegates to :func:`core.pipeline.solana_utils.is_plausible_anchor_source`,
        which checks for:
        - ``use anchor_lang`` import
        - At least one ``#[program]`` or ``#[derive(Accounts)]`` attribute
        """
        from core.pipeline.solana_utils import is_plausible_anchor_source

        return is_plausible_anchor_source(code)

    def check_compilation(self, code: str, workspace: str) -> Tuple[bool, str]:
        """Compile Anchor source via ``anchor build``.

        Steps:
        1. Verify the Anchor CLI is available on ``PATH``.
        2. Stage the source code into a valid Anchor workspace layout
           at ``<workspace>/anchor_build/``:
           - ``Anchor.toml``
           - ``programs/<program_name>/Cargo.toml``
           - ``programs/<program_name>/src/lib.rs``
        3. Validate the project structure.
        4. Invoke ``anchor build`` with a subprocess argument list,
           an explicit working directory, captured output, and a
           reasonable timeout.
        5. Return ``(True, "")`` on success, ``(False, diagnostic_text)``
           on failure.

        The ``anchor_build/`` subdirectory isolates build artifacts from
        the rest of the workspace and prevents overwriting unrelated files.
        """
        # ── Step 1: Check tool availability ──────────────────────────
        if not self._is_anchor_available():
            return (
                False,
                f"Anchor CLI not found: '{self._anchor_cli}'. "
                "Install Anchor (https://www.anchor-lang.com/docs/installation) "
                "or set the ANCHOR_CLI environment variable.",
            )

        # ── Step 2: Stage source into Anchor workspace ───────────────
        anchor_ws = os.path.join(workspace, "anchor_build")
        try:
            self._stage_anchor_workspace(code, anchor_ws)
        except Exception as exc:
            return False, f"Failed to stage Anchor workspace: {exc}"

        # ── Step 3: Validate project structure ───────────────────────
        from core.pipeline.solana_utils import validate_anchor_project_structure

        structure_errors = validate_anchor_project_structure(anchor_ws)
        if structure_errors:
            return (
                False,
                "Invalid Anchor project structure:\n"
                + "\n".join(f"  - {e}" for e in structure_errors),
            )

        # ── Step 4: Run anchor build ─────────────────────────────────
        try:
            result = subprocess.run(
                [self._anchor_cli, "build"],
                cwd=anchor_ws,
                capture_output=True,
                text=True,
                timeout=self._build_timeout,
            )
        except subprocess.TimeoutExpired:
            return (
                False,
                f"anchor build timed out after {self._build_timeout}s. "
                "Consider increasing the build_timeout or simplifying the program.",
            )
        except FileNotFoundError:
            # Can happen if the CLI path is set but the binary doesn't exist.
            return (
                False,
                f"Anchor CLI not found at '{self._anchor_cli}'. "
                "Ensure Anchor is installed and on PATH.",
            )
        except OSError as exc:
            return False, f"Failed to execute anchor build: {exc}"

        # ── Step 5: Interpret result ─────────────────────────────────
        if result.returncode == 0:
            return True, ""

        # Combine stdout and stderr for diagnostics (anchor may write
        # errors to either stream).
        diagnostic = ""
        if result.stderr:
            diagnostic += result.stderr
        if result.stdout:
            if diagnostic:
                diagnostic += "\n"
            diagnostic += result.stdout
        # Cap diagnostic length to avoid overwhelming consumers.
        return False, diagnostic[-6000:]

    # ── Formal Verification ──────────────────────────────────────────
    # Not yet implemented — requires Kani integration (future milestone).

    def generate_formal_spec(
        self,
        code: str,
        properties: List[Dict],
        **kwargs: Any,
    ) -> str:
        raise NotImplementedError(
            "SolanaAdapter.generate_formal_spec is not yet implemented. "
            "Kani harness generation is planned for a future milestone."
        )

    def verify_spec(self, spec: str, workspace: str) -> Tuple[bool, List[str]]:
        raise NotImplementedError(
            "SolanaAdapter.verify_spec is not yet implemented. "
            "Kani (cargo kani) integration is planned for a future milestone."
        )

    # ── Testing / Simulation ─────────────────────────────────────────
    # Not yet implemented — requires Anchor test integration (future milestone).

    def generate_test_harness(
        self,
        code: str,
        properties: List[Dict],
        **kwargs: Any,
    ) -> str:
        raise NotImplementedError(
            "SolanaAdapter.generate_test_harness is not yet implemented. "
            "Anchor test generation is planned for a future milestone."
        )

    def run_tests(self, workspace: str, **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError(
            "SolanaAdapter.run_tests is not yet implemented. "
            "Anchor test + solana-test-validator integration is planned "
            "for a future milestone."
        )

    # ── Counterexample Extraction ────────────────────────────────────
    # Not yet implemented — requires Solana log parser (future milestone).

    def extract_counterexample(self, tool_output: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError(
            "SolanaAdapter.extract_counterexample is not yet implemented. "
            "Solana log parser is planned for a future milestone."
        )

    # ── Private helpers ──────────────────────────────────────────────

    def _is_anchor_available(self) -> bool:
        """Check whether the Anchor CLI can be found on PATH."""
        return shutil.which(self._anchor_cli) is not None

    def _stage_anchor_workspace(self, code: str, anchor_ws: str) -> None:
        """Write *code* into a valid Anchor project layout at *anchor_ws*.

        Creates the following structure::

            anchor_ws/
            ├── Anchor.toml
            └── programs/
                └── <program_name>/
                    ├── Cargo.toml
                    └── src/
                        └── lib.rs   ← code goes here

        If the directory already exists the ``lib.rs`` is overwritten
        but existing config files are preserved (idempotent staging).
        """
        from core.solana_config import ANCHOR_WORKSPACE_DEFAULTS

        program_name = self._program_name
        program_dir = os.path.join(anchor_ws, "programs", program_name)
        src_dir = os.path.join(program_dir, "src")
        os.makedirs(src_dir, exist_ok=True)

        # ── lib.rs (always overwritten with the new candidate) ───────
        lib_rs_path = os.path.join(src_dir, "lib.rs")
        with open(lib_rs_path, "w", encoding="utf-8") as f:
            f.write(code)

        # ── Anchor.toml (created only if absent) ─────────────────────
        anchor_toml_path = os.path.join(anchor_ws, "Anchor.toml")
        if not os.path.isfile(anchor_toml_path):
            anchor_version = ANCHOR_WORKSPACE_DEFAULTS.get("anchor_version", "0.30.1")
            solana_version = ANCHOR_WORKSPACE_DEFAULTS.get("solana_version", "1.18.26")
            anchor_toml = (
                f'[toolchain]\n'
                f'anchor_version = "{anchor_version}"\n'
                f'solana_version = "{solana_version}"\n'
                f'\n'
                f'[features]\n'
                f'seeds = false\n'
                f'skip-lint = false\n'
                f'\n'
                f'[programs.localnet]\n'
                f'{program_name} = "Fg6PaFpoGXkYsidMpWTK6W2BeZ7FEfcYkg476zPFsLnS"\n'
                f'\n'
                f'[registry]\n'
                f'url = "https://api.apr.dev"\n'
                f'\n'
                f'[provider]\n'
                f'cluster = "localnet"\n'
                f'wallet = "~/.config/solana/id.json"\n'
                f'\n'
                f'[scripts]\n'
                f'test = "yarn run ts-mocha -p ./tsconfig.json -t 1000000 tests/**/*.ts"\n'
            )
            with open(anchor_toml_path, "w", encoding="utf-8") as f:
                f.write(anchor_toml)

        # ── Cargo.toml (created only if absent) ──────────────────────
        cargo_toml_path = os.path.join(program_dir, "Cargo.toml")
        if not os.path.isfile(cargo_toml_path):
            cargo_toml = (
                f'[package]\n'
                f'name = "{program_name}"\n'
                f'version = "0.1.0"\n'
                f'description = "LeVer auto-generated Anchor program"\n'
                f'edition = "2021"\n'
                f'\n'
                f'[lib]\n'
                f'crate-type = ["cdylib", "lib"]\n'
                f'name = "{program_name.replace("-", "_")}"\n'
                f'\n'
                f'[features]\n'
                f'no-entrypoint = []\n'
                f'no-idl = []\n'
                f'no-log-ix-name = []\n'
                f'cpi = ["no-entrypoint"]\n'
                f'default = []\n'
                f'\n'
                f'[dependencies]\n'
                f'anchor-lang = "0.30.1"\n'
            )
            with open(cargo_toml_path, "w", encoding="utf-8") as f:
                f.write(cargo_toml)
