# ──────────────────────────────────────────────────────────────────────
# tests/test_pipeline_target_integration.py
# Focused tests for the --target integration in main_pipeline.py and
# the adapter routing in workflows.py.
#
# Covers:
#   - Default target is solidity
#   - Explicit --target solidity
#   - Unknown targets are rejected by argparse
#   - adapter_factory is invoked correctly
#   - Validation (is_valid_source) delegated through adapter
#   - Compilation (check_compilation) delegated through adapter
#   - --target solana fails early without entering the Solidity workflow
# ──────────────────────────────────────────────────────────────────────

import sys
import os
import unittest
from unittest.mock import MagicMock, patch, call

# Ensure the LeVer package root is importable.
LEVER_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if LEVER_ROOT not in sys.path:
    sys.path.insert(0, LEVER_ROOT)

from core.main_pipeline import _build_parser, main
from core.adapter_factory import adapter_factory
from core.adapters.solidity_adapter import SolidityAdapter
from core.adapters.solana_adapter import SolanaAdapter


# ── Parser Tests ─────────────────────────────────────────────────────

class TestParserTargetArgument(unittest.TestCase):
    """Verify the --target CLI argument on the parser."""

    def test_default_target_is_solidity(self):
        """When --target is omitted the default must be 'solidity'."""
        parser = _build_parser()
        args = parser.parse_args(["--req-file", "req.txt"])
        self.assertEqual(args.target, "solidity")

    def test_explicit_target_solidity(self):
        """--target solidity is accepted and stored."""
        parser = _build_parser()
        args = parser.parse_args(["--req-file", "req.txt", "--target", "solidity"])
        self.assertEqual(args.target, "solidity")

    def test_explicit_target_solana(self):
        """--target solana is accepted and stored."""
        parser = _build_parser()
        args = parser.parse_args(["--req-file", "req.txt", "--target", "solana"])
        self.assertEqual(args.target, "solana")

    def test_unknown_target_rejected(self):
        """Unknown target values must be rejected by argparse."""
        parser = _build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["--req-file", "req.txt", "--target", "ethereum"])
        # argparse exits with code 2 on invalid choices.
        self.assertEqual(ctx.exception.code, 2)

    def test_unknown_target_move_rejected(self):
        """'move' is not yet a valid target."""
        parser = _build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["--req-file", "req.txt", "--target", "move"])


# ── Adapter Factory Tests ────────────────────────────────────────────

class TestAdapterFactoryInvocation(unittest.TestCase):
    """Verify adapter_factory creates the right adapter types."""

    def test_solidity_adapter_created(self):
        adapter = adapter_factory("solidity")
        self.assertIsInstance(adapter, SolidityAdapter)

    def test_solidity_adapter_with_model_name(self):
        adapter = adapter_factory("solidity", model_name="gpt-4o")
        self.assertIsInstance(adapter, SolidityAdapter)
        self.assertEqual(adapter._model_name, "gpt-4o")

    def test_solana_adapter_created(self):
        """The factory can instantiate SolanaAdapter (even though methods are stubs)."""
        adapter = adapter_factory("solana")
        self.assertIsInstance(adapter, SolanaAdapter)

    def test_unknown_target_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            adapter_factory("ethereum")
        self.assertIn("Unknown target", str(ctx.exception))
        self.assertIn("ethereum", str(ctx.exception))

    def test_case_insensitive_target(self):
        adapter = adapter_factory("Solidity")
        self.assertIsInstance(adapter, SolidityAdapter)

    def test_empty_target_raises(self):
        with self.assertRaises(ValueError):
            adapter_factory("")


# ── Validation Delegation Tests ──────────────────────────────────────

class TestValidationDelegation(unittest.TestCase):
    """Verify is_valid_source is delegated through the adapter in workflows."""

    def test_adapter_is_valid_source_called_in_workflow(self):
        """When an adapter is provided, workflow uses adapter.is_valid_source
        instead of the legacy is_plausible_solidity_source."""
        from core.pipeline.workflows import workflow_from_requirement

        # Build mocks
        mock_adapter = MagicMock()
        mock_adapter.is_valid_source = MagicMock(return_value=False)

        mock_coder = MagicMock()
        mock_coder.model_name = "test-model"
        mock_coder.generate_modern_code = MagicMock(return_value="code")

        mock_checkpoint = MagicMock()
        mock_checkpoint.save_stage = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.iteration = 0
        mock_ctx.workspace = os.path.join(os.path.dirname(__file__), "tmp_ws")
        mock_ctx.checkpoint = mock_checkpoint
        mock_ctx.feedback_constraints = []
        mock_ctx.security_patches = []

        mock_sim = MagicMock()
        agents = {"coder": mock_coder}
        tools = {"simulator": mock_sim}

        result = workflow_from_requirement(
            ctx=mock_ctx,
            agents=agents,
            tools=tools,
            requirement="test req",
            mode="full",
            max_iters=1,
            adapter=mock_adapter,
        )

        # Adapter's is_valid_source must have been called
        mock_adapter.is_valid_source.assert_called_once_with("code")
        # Since validation returned False, workflow should return False
        self.assertFalse(result)

    def test_without_adapter_uses_legacy_validation(self):
        """When no adapter is provided, the legacy path is used."""
        from core.pipeline.workflows import workflow_from_requirement

        mock_coder = MagicMock()
        mock_coder.model_name = "test-model"
        mock_coder.generate_modern_code = MagicMock(return_value="invalid code")

        mock_checkpoint = MagicMock()
        mock_checkpoint.save_stage = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.iteration = 0
        mock_ctx.workspace = os.path.join(os.path.dirname(__file__), "tmp_ws")
        mock_ctx.checkpoint = mock_checkpoint
        mock_ctx.feedback_constraints = []
        mock_ctx.security_patches = []

        mock_sim = MagicMock()
        agents = {"coder": mock_coder}
        tools = {"simulator": mock_sim}

        with patch("core.pipeline.workflows.is_plausible_solidity_source", return_value=False) as mock_ips:
            result = workflow_from_requirement(
                ctx=mock_ctx,
                agents=agents,
                tools=tools,
                requirement="test req",
                mode="full",
                max_iters=1,
                # No adapter — legacy path
            )
            mock_ips.assert_called_once_with("invalid code")


# ── Compilation Delegation Tests ─────────────────────────────────────

class TestCompilationDelegation(unittest.TestCase):
    """Verify check_compilation is delegated through the adapter in workflows."""

    def _run_workflow_with_adapter(self, adapter, compile_result):
        """Helper: run one iteration of workflow_from_requirement with a mock adapter."""
        from core.pipeline.workflows import workflow_from_requirement

        adapter.is_valid_source = MagicMock(return_value=True)
        adapter.check_compilation = MagicMock(return_value=compile_result)

        mock_coder = MagicMock()
        mock_coder.model_name = "test-model"
        mock_coder.generate_modern_code = MagicMock(return_value="pragma solidity ^0.8.0; contract A {}")

        mock_checkpoint = MagicMock()
        mock_checkpoint.save_stage = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.iteration = 0
        mock_ctx.workspace = os.path.join(os.path.dirname(__file__), "tmp_ws")
        mock_ctx.checkpoint = mock_checkpoint
        mock_ctx.feedback_constraints = []
        mock_ctx.security_patches = []

        mock_sim = MagicMock()
        agents = {"coder": mock_coder}
        tools = {"simulator": mock_sim}

        os.makedirs(mock_ctx.workspace, exist_ok=True)

        result = workflow_from_requirement(
            ctx=mock_ctx,
            agents=agents,
            tools=tools,
            requirement="test req",
            mode="full",
            max_iters=1,
            adapter=adapter,
        )
        return result, adapter, mock_sim

    def test_adapter_check_compilation_called(self):
        """When an adapter is provided, compilation goes through adapter.check_compilation."""
        mock_adapter = MagicMock()
        result, adapter, sim = self._run_workflow_with_adapter(
            mock_adapter, (False, "compile error")
        )

        adapter.check_compilation.assert_called_once()
        # Compilation failed, so the simulator's check_compilation should NOT be called.
        sim.check_compilation.assert_not_called()

    def test_compilation_failure_adds_feedback(self):
        """When adapter.check_compilation returns failure, feedback is added."""
        mock_adapter = MagicMock()
        mock_adapter.is_valid_source = MagicMock(return_value=True)
        mock_adapter.check_compilation = MagicMock(return_value=(False, "Error: expected ';'"))

        mock_coder = MagicMock()
        mock_coder.model_name = "test-model"
        mock_coder.generate_modern_code = MagicMock(return_value="some code")

        mock_checkpoint = MagicMock()
        mock_checkpoint.save_stage = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.iteration = 0
        mock_ctx.workspace = os.path.join(os.path.dirname(__file__), "tmp_ws")
        mock_ctx.checkpoint = mock_checkpoint
        mock_ctx.feedback_constraints = []
        mock_ctx.security_patches = []

        os.makedirs(mock_ctx.workspace, exist_ok=True)

        from core.pipeline.workflows import workflow_from_requirement
        workflow_from_requirement(
            ctx=mock_ctx,
            agents={"coder": mock_coder},
            tools={"simulator": MagicMock()},
            requirement="test req",
            mode="full",
            max_iters=1,
            adapter=mock_adapter,
        )

        # Check that feedback was appended about compilation failure
        self.assertTrue(
            any("compiler errors" in fc.lower() or "fix all" in fc.lower()
                for fc in mock_ctx.feedback_constraints),
            f"Expected compilation feedback in {mock_ctx.feedback_constraints}",
        )


# ── Solana Early Failure Tests ───────────────────────────────────────

class TestSolanaEarlyFailure(unittest.TestCase):
    """Verify that --target solana fails early with an actionable message."""

    def test_solana_target_raises_not_implemented(self):
        """main() with --target solana must fail with a clear error.

        The NotImplementedError is caught by the generic Exception handler
        in main() and returns exit code 2 with an error message.
        """
        # We need a req file — create a temporary one.
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Build a token")
            req_file = f.name

        try:
            # Capture stderr to check the error message.
            from io import StringIO
            captured = StringIO()
            old_stderr = sys.stderr
            sys.stderr = captured

            exit_code = main(["--req-file", req_file, "--target", "solana"])

            sys.stderr = old_stderr
            error_output = captured.getvalue()

            self.assertEqual(exit_code, 2)
            self.assertIn("not yet implemented", error_output.lower())
            self.assertIn("solana", error_output.lower())
        finally:
            os.unlink(req_file)

    def test_solana_does_not_enter_solidity_workflow(self):
        """The Solana path must not invoke workflow_from_requirement."""
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Build a token")
            req_file = f.name

        try:
            with patch("core.main_pipeline.workflow_from_requirement") as mock_wf:
                exit_code = main(["--req-file", req_file, "--target", "solana"])
                # Workflow must NOT have been called.
                mock_wf.assert_not_called()
                self.assertEqual(exit_code, 2)
        finally:
            os.unlink(req_file)

    def test_solana_adapter_methods_raise_not_implemented(self):
        """All SolanaAdapter methods must raise NotImplementedError."""
        adapter = SolanaAdapter()
        with self.assertRaises(NotImplementedError):
            adapter.is_valid_source("use anchor_lang")
        with self.assertRaises(NotImplementedError):
            adapter.check_compilation("code", "/ws")
        with self.assertRaises(NotImplementedError):
            adapter.generate_code("req", [])
        with self.assertRaises(NotImplementedError):
            adapter.repair_code("code", "feedback")
        with self.assertRaises(NotImplementedError):
            adapter.generate_formal_spec("code", [])
        with self.assertRaises(NotImplementedError):
            adapter.verify_spec("spec", "/ws")
        with self.assertRaises(NotImplementedError):
            adapter.generate_test_harness("code", [])
        with self.assertRaises(NotImplementedError):
            adapter.run_tests("/ws")
        with self.assertRaises(NotImplementedError):
            adapter.extract_counterexample("output")


# ── Backward Compatibility Tests ─────────────────────────────────────

class TestBackwardCompatibility(unittest.TestCase):
    """Verify existing Solidity CLI commands still work."""

    def test_parser_existing_args_unchanged(self):
        """All pre-existing arguments still parse correctly."""
        parser = _build_parser()
        args = parser.parse_args([
            "--req-file", "req.txt",
            "--mode", "no_lean",
            "--exp-name", "my_exp",
            "--run-id", "run_1",
            "--max-iters", "5",
            "--attack-rounds", "2",
            "--model", "gpt-4",
            "--slither-command", "slither",
        ])
        self.assertEqual(args.mode, "no_lean")
        self.assertEqual(args.exp_name, "my_exp")
        self.assertEqual(args.run_id, "run_1")
        self.assertEqual(args.max_iters, 5)
        self.assertEqual(args.attack_rounds, 2)
        self.assertEqual(args.model, "gpt-4")
        self.assertEqual(args.slither_command, "slither")
        # Default target should be solidity
        self.assertEqual(args.target, "solidity")

    def test_workflow_from_requirement_no_adapter_signature(self):
        """workflow_from_requirement still works without adapter kwarg."""
        from core.pipeline.workflows import workflow_from_requirement
        import inspect
        sig = inspect.signature(workflow_from_requirement)
        params = sig.parameters
        # adapter must be optional with default None
        self.assertIn("adapter", params)
        self.assertEqual(params["adapter"].default, None)


if __name__ == "__main__":
    unittest.main()
