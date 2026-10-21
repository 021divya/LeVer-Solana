# ──────────────────────────────────────────────────────────────────────
# core/adapters/solidity_adapter.py  — SolidityAdapter(TargetAdapter)
#
# WRAPS existing LeVer code — no modification to original modules:
#   generate_code()     → core.agents.SolidityCoder
#   repair_code()       → core.agents.SolidityCoder
#   is_valid_source()   → core.pipeline.solidity_utils.is_plausible_solidity_source()
#   check_compilation() → core.simulator.SimulationRunner.check_compilation() (forge build)
#   generate_formal_spec() → core.agents.LeanFormalizer
#   verify_spec()       → core.formal_verifier.FormalVerifier.verify_file() (Lean 4)
#   generate_test_harness() → core.agents.EnvironmentArchitect.generate_fuzz_test()
#   run_tests()         → core.simulator.SimulationRunner.run_foundry_fuzzing()
#   extract_counterexample() → Foundry/forge output parser
# ──────────────────────────────────────────────────────────────────────

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from core.adapters.base import TargetAdapter


class SolidityAdapter(TargetAdapter):
    """Adapter for Solidity / EVM targets (Foundry + Lean 4).

    This adapter is a thin wrapper around the **existing** LeVer modules.
    No original code is modified — only delegated to.

    Parameters
    ----------
    coder : SolidityCoder | None
        Pre-constructed ``SolidityCoder`` agent. If *None*, a new instance
        is created on demand (requires an LLM endpoint).
    formalizer : LeanFormalizer | None
        Pre-constructed ``LeanFormalizer`` agent.
    architect : EnvironmentArchitect | None
        Pre-constructed ``EnvironmentArchitect`` agent.
    simulator : SimulationRunner | None
        Pre-constructed ``SimulationRunner`` instance.
    verifier : FormalVerifier | None
        Pre-constructed ``FormalVerifier`` instance.
    model_name : str | None
        LLM model name forwarded to agents created on demand.
    """

    def __init__(
        self,
        *,
        coder: Any = None,
        formalizer: Any = None,
        architect: Any = None,
        simulator: Any = None,
        verifier: Any = None,
        model_name: Optional[str] = None,
        **_kwargs: Any,
    ) -> None:
        self._coder = coder
        self._formalizer = formalizer
        self._architect = architect
        self._simulator = simulator
        self._verifier = verifier
        self._model_name = model_name

    # ── Lazy accessors ────────────────────────────────────────────────
    # Build heavyweight dependencies only when actually needed.

    def _get_coder(self):
        """Return the SolidityCoder agent, creating one if necessary."""
        if self._coder is None:
            from core.agents import SolidityCoder
            kwargs = {}
            if self._model_name:
                kwargs["model_name"] = self._model_name
            self._coder = SolidityCoder(**kwargs)
        return self._coder

    def _get_formalizer(self):
        """Return the LeanFormalizer agent, creating one if necessary."""
        if self._formalizer is None:
            from core.agents import LeanFormalizer
            kwargs = {}
            if self._model_name:
                kwargs["model_name"] = self._model_name
            self._formalizer = LeanFormalizer(**kwargs)
        return self._formalizer

    def _get_architect(self):
        """Return the EnvironmentArchitect agent, creating one if necessary."""
        if self._architect is None:
            from core.agents import EnvironmentArchitect
            kwargs = {}
            if self._model_name:
                kwargs["model_name"] = self._model_name
            self._architect = EnvironmentArchitect(**kwargs)
        return self._architect

    def _get_simulator(self):
        """Return the SimulationRunner, raising if not injected."""
        if self._simulator is None:
            raise RuntimeError(
                "SolidityAdapter: no SimulationRunner was injected. "
                "Pass simulator= to the constructor or use the adapter "
                "factory with the appropriate kwargs."
            )
        return self._simulator

    def _get_verifier(self):
        """Return the FormalVerifier, raising if not injected."""
        if self._verifier is None:
            raise RuntimeError(
                "SolidityAdapter: no FormalVerifier was injected. "
                "Pass verifier= to the constructor or use the adapter "
                "factory with the appropriate kwargs."
            )
        return self._verifier

    # ── Code Generation ──────────────────────────────────────────────

    def generate_code(
        self,
        requirement: str,
        properties: List[Dict],
        *,
        feedback_constraints: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> str:
        """Generate Solidity source via ``SolidityCoder.generate_modern_code``.

        On the first call (no feedback_constraints) the coder's
        ``generate_modern_code`` is used for a clean 0.8.20 generation.
        When *feedback_constraints* are present the coder's
        ``generate_code`` method is used instead, which includes the
        security-repair system prompt.

        The *properties* list is converted to constraint strings when
        constraints are provided so the coder can incorporate them.
        """
        coder = self._get_coder()

        constraints = list(feedback_constraints or [])
        # Append property descriptions as additional constraints if present.
        for prop in (properties or []):
            desc = prop.get("invariant_template") or prop.get("description") or prop.get("name", "")
            if desc:
                constraints.append(f"Enforce property: {desc}")

        if not constraints:
            # First-pass generation — use the modern code path.
            return coder.generate_modern_code(requirement)
        else:
            # Repair/constrained generation path.
            return coder.generate_code(requirement, constraints)

    def repair_code(
        self,
        current_code: str,
        feedback: str,
        *,
        properties: Optional[List[Dict]] = None,
        **kwargs: Any,
    ) -> str:
        """Repair Solidity source via ``SolidityCoder.generate_code``.

        The legacy ``SolidityCoder`` does not have a separate repair
        method — its ``generate_code(requirements, constraints)`` already
        accepts the current code plus compiler/verifier feedback as the
        requirement prompt and a list of constraints.  We compose the
        repair prompt in the same style that ``workflows.py`` uses.
        """
        coder = self._get_coder()

        constraints = [feedback]
        for prop in (properties or []):
            desc = prop.get("invariant_template") or prop.get("description") or prop.get("name", "")
            if desc:
                constraints.append(f"Enforce property: {desc}")

        repair_prompt = (
            f"[CURRENT SOLIDITY]\n{current_code}\n\n"
            f"[FEEDBACK]\n{feedback}\n\n"
            "Return a complete repaired Solidity implementation that "
            "addresses every supplied constraint."
        )
        return coder.generate_code(repair_prompt, constraints)

    # ── Validation ───────────────────────────────────────────────────

    def is_valid_source(self, code: str) -> bool:
        """Quick plausibility check via ``is_plausible_solidity_source``."""
        from core.pipeline.solidity_utils import is_plausible_solidity_source
        return is_plausible_solidity_source(code)

    def check_compilation(self, code: str, workspace: str) -> Tuple[bool, str]:
        """Compile Solidity via Foundry (``forge build``).

        The legacy ``SimulationRunner.check_compilation()`` takes no
        arguments — it compiles whatever is currently on disk in the
        simulation workspace.  This adapter bridges the gap by:

        1. Calling ``simulator.initialize_environment(code, "")`` to
           write ``src/Target.sol`` (and an empty ``src/Mocks.sol``).
        2. Calling ``simulator.check_compilation()`` which runs
           ``forge build --offline --skip test``.
        """
        sim = self._get_simulator()
        try:
            sim.initialize_environment(code, "")
            return sim.check_compilation()
        except Exception as exc:
            return False, f"Compilation infrastructure error: {exc}"

    # ── Formal Verification ──────────────────────────────────────────

    def generate_formal_spec(
        self,
        code: str,
        properties: List[Dict],
        **kwargs: Any,
    ) -> str:
        """Produce a Lean 4 formal specification via ``LeanFormalizer``.

        Converts the property dicts to a list of description strings,
        which is the format expected by
        ``LeanFormalizer.formalize_definitions(solidity_code, properties, ...)``.
        """
        formalizer = self._get_formalizer()

        property_strings: List[str] = []
        for prop in (properties or []):
            text = prop.get("invariant_template") or prop.get("description") or prop.get("name", "")
            if text:
                property_strings.append(text)

        error_feedback = kwargs.get("error_feedback", "")
        theorem_budget = kwargs.get("theorem_budget", 0)

        return formalizer.formalize_definitions(
            solidity_code=code,
            properties=property_strings,
            error_feedback=error_feedback,
            theorem_budget=theorem_budget,
        )

    def verify_spec(self, spec: str, workspace: str) -> Tuple[bool, List[str]]:
        """Run the Lean 4 verifier and return ``(all_passed, error_list)``.

        The legacy ``FormalVerifier`` works with files on disk:
        1. ``save_file(filename, content)`` writes a ``.lean`` file.
        2. ``verify_file(filename)`` compiles it and returns a list of
           error strings (empty means success).

        This method uses a fixed filename ``"Definitions.lean"`` as the
        pipeline convention.
        """
        verifier = self._get_verifier()
        filename = "Definitions.lean"
        try:
            verifier.save_file(filename, spec)
            errors = verifier.verify_file(filename)
            return (len(errors) == 0, errors)
        except Exception as exc:
            return False, [f"Lean verification infrastructure error: {exc}"]

    # ── Testing / Simulation ─────────────────────────────────────────

    def generate_test_harness(
        self,
        code: str,
        properties: List[Dict],
        **kwargs: Any,
    ) -> str:
        """Create a Foundry invariant test harness via ``EnvironmentArchitect``.

        Delegates to ``EnvironmentArchitect.generate_fuzz_test``.
        The architect needs the target source and optionally the
        SafetyRules source and semantic context.
        """
        architect = self._get_architect()

        safety_code = kwargs.get("safety_code", "")
        error_feedback = kwargs.get("error_feedback", "")
        previous_code = kwargs.get("previous_code", "")
        semantic_context = kwargs.get("semantic_context", "")

        return architect.generate_fuzz_test(
            target_code=code,
            safety_code=safety_code,
            error_feedback=error_feedback,
            previous_code=previous_code,
            semantic_context=semantic_context,
        )

    def run_tests(self, workspace: str, **kwargs: Any) -> Dict[str, Any]:
        """Execute Foundry invariant/fuzz tests via ``SimulationRunner``.

        Delegates to ``SimulationRunner.run_foundry_fuzzing`` when a
        ``test_source`` keyword argument is provided (the generated
        ``Invariant.t.sol`` source text).

        If ``test_source`` is not provided but the simulation workspace
        already has tests on disk, falls back to
        ``SimulationRunner.check_fuzz_compilation`` for a compile-only
        check and reports no pass/fail counts.

        Returns
        -------
        dict
            Keys: ``success``, ``passed``, ``failed``, ``details``.
        """
        sim = self._get_simulator()
        test_source = kwargs.get("test_source", "")

        if not test_source:
            return {
                "success": False,
                "passed": 0,
                "failed": 0,
                "details": "No test_source provided to run_tests.",
            }

        try:
            result = sim.run_foundry_fuzzing(test_source)
        except Exception as exc:
            return {
                "success": False,
                "passed": 0,
                "failed": 0,
                "details": f"Test execution infrastructure error: {exc}",
            }

        # Normalize the SimulationRunner result dict to the adapter schema.
        safe = result.get("safe", False)
        log = result.get("log", "")
        infra_broken = result.get("infra_broken", False)
        compile_pass = result.get("foundry_compile_pass", False)
        test_pass = result.get("foundry_test_pass", False)

        passed_count = result.get("fuzz_runs", 0) if safe else 0
        failed_count = len(result.get("broken_invariants", []))

        return {
            "success": safe and not infra_broken,
            "passed": passed_count,
            "failed": failed_count,
            "details": log,
            # Preserve extra Foundry-specific fields for downstream consumers.
            "foundry_compile_pass": compile_pass,
            "foundry_test_pass": test_pass,
            "infra_broken": infra_broken,
            "broken_invariants": result.get("broken_invariants", []),
            "foundry_summary": result.get("foundry_summary", {}),
        }

    # ── Counterexample Extraction ────────────────────────────────────

    def extract_counterexample(self, tool_output: str) -> Optional[Dict[str, Any]]:
        """Parse Foundry / ``forge test`` output for a concrete counterexample.

        Foundry counterexamples appear as:

        * ``[FAIL. Reason: ... Counterexample: calldata=0x... args=[...]]``
        * A ``Traces:`` section with the failing call sequence.

        This parser extracts:
          - ``reason``: The revert/assertion reason string.
          - ``calldata``: The raw hex calldata (if present).
          - ``args``: The decoded argument list (if present).
          - ``raw_trace``: Up to 3000 chars of the Traces section.

        Limitations
        -----------
        * Parsing is regex-based; deeply nested or multi-line counter-
          examples may not be fully captured.
        * Only the *first* counterexample is returned when multiple
          invariants fail in the same run.

        Returns
        -------
        dict | None
            Structured counterexample data, or ``None`` if no failure
            pattern is found in *tool_output*.
        """
        if not tool_output:
            return None

        result: Dict[str, Any] = {"source": "foundry"}

        # 1. Try to extract the FAIL line with reason and counterexample.
        # Foundry format:
        #   [FAIL. Reason: <reason> Counterexample: calldata=0x... args=[...]]
        # The outer [] can contain nested [] in the args field, so we
        # first find the FAIL block with a greedy match up to the last ]].
        fail_match = re.search(
            r"\[FAIL\.\s*Reason:\s*(?P<reason>.*?)(?:\s*Counterexample:\s*"
            r"calldata=(?P<calldata>0x[0-9a-fA-F]+)\s*"
            r"args=\[(?P<args>[^\]]*)\])?\]",
            tool_output,
        )
        if fail_match:
            result["reason"] = fail_match.group("reason").strip()
            if fail_match.group("calldata"):
                result["calldata"] = fail_match.group("calldata")
            if fail_match.group("args"):
                result["args"] = fail_match.group("args").strip()

        # 2. Try to extract the Traces section.
        if "Traces:" in tool_output:
            trace_start = tool_output.index("Traces:")
            result["raw_trace"] = tool_output[trace_start : trace_start + 3000]

        # 3. Extract broken invariant names (e.g. ``invariant_solvency``).
        broken = re.findall(
            r"\[FAIL[^\]]*\]\s+(invariant_\w+)",
            tool_output,
        )
        if broken:
            result["broken_invariants"] = broken

        if len(result) <= 1:
            # Only "source" key — nothing useful was parsed.
            return None

        return result
