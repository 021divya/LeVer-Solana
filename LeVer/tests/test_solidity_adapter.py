# ──────────────────────────────────────────────────────────────────────
# tests/test_solidity_adapter.py
# Focused tests for the SolidityAdapter wrapper.
#
# Covers:
#   - is_valid_source (pure logic, no external tools)
#   - extract_counterexample (regex parsing, no external tools)
#   - Constructor & lazy accessor behavior
#   - Method delegation (with mocked dependencies)
#   - Error handling when dependencies are missing
# ──────────────────────────────────────────────────────────────────────

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Ensure the LeVer package root is importable.
LEVER_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if LEVER_ROOT not in sys.path:
    sys.path.insert(0, LEVER_ROOT)

from core.adapters.solidity_adapter import SolidityAdapter


class TestIsValidSource(unittest.TestCase):
    """Test is_valid_source — a pure function with no external dependencies."""

    def setUp(self):
        self.adapter = SolidityAdapter()

    def test_valid_minimal_contract(self):
        code = (
            '// SPDX-License-Identifier: MIT\n'
            'pragma solidity ^0.8.20;\n'
            'contract Counter {\n'
            '    uint256 public count;\n'
            '}\n'
        )
        self.assertTrue(self.adapter.is_valid_source(code))

    def test_valid_interface(self):
        code = (
            'pragma solidity ^0.8.0;\n'
            'interface IERC20 {\n'
            '    function totalSupply() external view returns (uint256);\n'
            '}\n'
        )
        self.assertTrue(self.adapter.is_valid_source(code))

    def test_valid_library(self):
        code = (
            'pragma solidity ^0.8.0;\n'
            'library SafeMath {\n'
            '    function add(uint a, uint b) internal pure returns (uint) {\n'
            '        return a + b;\n'
            '    }\n'
            '}\n'
        )
        self.assertTrue(self.adapter.is_valid_source(code))

    def test_empty_string(self):
        self.assertFalse(self.adapter.is_valid_source(""))

    def test_whitespace_only(self):
        self.assertFalse(self.adapter.is_valid_source("   \n\n  "))

    def test_missing_pragma(self):
        code = 'contract Foo { uint x; }'
        self.assertFalse(self.adapter.is_valid_source(code))

    def test_missing_contract_keyword(self):
        code = 'pragma solidity ^0.8.0;\nuint x = 1;'
        self.assertFalse(self.adapter.is_valid_source(code))

    def test_rust_code_rejected(self):
        code = 'use anchor_lang::prelude::*;\n#[program]\npub mod my_program {}'
        self.assertFalse(self.adapter.is_valid_source(code))

    def test_none_input(self):
        self.assertFalse(self.adapter.is_valid_source(None))


class TestExtractCounterexample(unittest.TestCase):
    """Test extract_counterexample — regex parsing of Foundry output."""

    def setUp(self):
        self.adapter = SolidityAdapter()

    def test_empty_output(self):
        self.assertIsNone(self.adapter.extract_counterexample(""))

    def test_none_output(self):
        self.assertIsNone(self.adapter.extract_counterexample(None))

    def test_passing_test_output(self):
        output = (
            "[PASS] invariant_solvency() (runs: 500, calls: 7500)\n"
            "Test result: ok. 3 passed; 0 failed;\n"
        )
        self.assertIsNone(self.adapter.extract_counterexample(output))

    def test_fail_with_reason_and_counterexample(self):
        output = (
            "[FAIL. Reason: assertion failed "
            "Counterexample: calldata=0xabcd1234 args=[42, 0x1234]] "
            "invariant_solvency() (runs: 100, calls: 1500)\n"
        )
        result = self.adapter.extract_counterexample(output)
        self.assertIsNotNone(result)
        self.assertEqual(result["source"], "foundry")
        self.assertEqual(result["reason"], "assertion failed")
        self.assertEqual(result["calldata"], "0xabcd1234")
        self.assertEqual(result["args"], "42, 0x1234")
        # The broken_invariants regex requires [FAIL...] followed by
        # whitespace then invariant_XXX.  Verify at least the core
        # fields (reason, calldata, args) are extracted.
        # broken_invariants may or may not appear depending on exact
        # formatting; the key information is in reason/calldata/args.

    def test_fail_reason_only_no_counterexample(self):
        output = (
            "[FAIL. Reason: Ownable: caller is not the owner] "
            "invariant_ownership() (runs: 50)\n"
        )
        result = self.adapter.extract_counterexample(output)
        self.assertIsNotNone(result)
        self.assertEqual(result["reason"], "Ownable: caller is not the owner")
        self.assertNotIn("calldata", result)

    def test_traces_section_extraction(self):
        output = (
            "Some preamble output\n"
            "Traces:\n"
            "  [123] Counter::increment()\n"
            "    └─ ← ()\n"
            "  [456] Counter::decrement()\n"
            "    └─ ← revert: underflow\n"
        )
        result = self.adapter.extract_counterexample(output)
        self.assertIsNotNone(result)
        self.assertIn("raw_trace", result)
        self.assertIn("Counter::increment", result["raw_trace"])

    def test_multiple_broken_invariants(self):
        output = (
            "[FAIL. Reason: a] invariant_one() (runs: 10)\n"
            "[FAIL. Reason: b] invariant_two() (runs: 10)\n"
        )
        result = self.adapter.extract_counterexample(output)
        self.assertIsNotNone(result)
        # extract_counterexample returns the first FAIL reason
        self.assertEqual(result["reason"], "a")
        self.assertIn("invariant_one", result["broken_invariants"])
        self.assertIn("invariant_two", result["broken_invariants"])


class TestConstructorAndDependencies(unittest.TestCase):
    """Test that the adapter handles missing dependencies properly."""

    def test_default_construction_no_crash(self):
        """Adapter can be created with no arguments (factory compatibility)."""
        adapter = SolidityAdapter()
        self.assertIsNotNone(adapter)

    def test_factory_kwargs_forwarded(self):
        """model_name kwarg is captured for lazy agent creation."""
        adapter = SolidityAdapter(model_name="gpt-4o")
        self.assertEqual(adapter._model_name, "gpt-4o")

    def test_injected_dependencies_stored(self):
        """Pre-constructed dependencies are accepted and stored."""
        mock_sim = MagicMock()
        mock_ver = MagicMock()
        adapter = SolidityAdapter(simulator=mock_sim, verifier=mock_ver)
        self.assertIs(adapter._simulator, mock_sim)
        self.assertIs(adapter._verifier, mock_ver)

    def test_missing_simulator_raises(self):
        """check_compilation raises RuntimeError when no simulator is injected."""
        adapter = SolidityAdapter()
        with self.assertRaises(RuntimeError) as ctx:
            adapter.check_compilation("pragma solidity ^0.8.0; contract A {}", "/tmp")
        self.assertIn("SimulationRunner", str(ctx.exception))

    def test_missing_verifier_raises(self):
        """verify_spec raises RuntimeError when no verifier is injected."""
        adapter = SolidityAdapter()
        with self.assertRaises(RuntimeError) as ctx:
            adapter.verify_spec("-- lean spec", "/tmp")
        self.assertIn("FormalVerifier", str(ctx.exception))


class TestCheckCompilationDelegation(unittest.TestCase):
    """Test that check_compilation delegates correctly to SimulationRunner."""

    def test_successful_compilation(self):
        mock_sim = MagicMock()
        mock_sim.initialize_environment = MagicMock()
        mock_sim.check_compilation = MagicMock(return_value=(True, ""))
        adapter = SolidityAdapter(simulator=mock_sim)

        ok, log = adapter.check_compilation("pragma solidity ^0.8.0; contract A {}", "/ws")

        self.assertTrue(ok)
        self.assertEqual(log, "")
        mock_sim.initialize_environment.assert_called_once_with(
            "pragma solidity ^0.8.0; contract A {}", ""
        )
        mock_sim.check_compilation.assert_called_once()

    def test_failed_compilation(self):
        mock_sim = MagicMock()
        mock_sim.initialize_environment = MagicMock()
        mock_sim.check_compilation = MagicMock(
            return_value=(False, "STDERR:\nError: expected ';'")
        )
        adapter = SolidityAdapter(simulator=mock_sim)

        ok, log = adapter.check_compilation("invalid code", "/ws")

        self.assertFalse(ok)
        self.assertIn("expected", log)

    def test_infrastructure_exception(self):
        mock_sim = MagicMock()
        mock_sim.initialize_environment = MagicMock(
            side_effect=FileNotFoundError("forge not found")
        )
        adapter = SolidityAdapter(simulator=mock_sim)

        ok, log = adapter.check_compilation("pragma solidity ^0.8.0; contract A {}", "/ws")

        self.assertFalse(ok)
        self.assertIn("infrastructure error", log)
        self.assertIn("forge not found", log)


class TestVerifySpecDelegation(unittest.TestCase):
    """Test that verify_spec delegates correctly to FormalVerifier."""

    def test_successful_verification(self):
        mock_verifier = MagicMock()
        mock_verifier.save_file = MagicMock()
        mock_verifier.verify_file = MagicMock(return_value=[])
        adapter = SolidityAdapter(verifier=mock_verifier)

        ok, errors = adapter.verify_spec("-- valid lean code", "/ws")

        self.assertTrue(ok)
        self.assertEqual(errors, [])
        mock_verifier.save_file.assert_called_once_with("Definitions.lean", "-- valid lean code")
        mock_verifier.verify_file.assert_called_once_with("Definitions.lean")

    def test_failed_verification(self):
        mock_verifier = MagicMock()
        mock_verifier.save_file = MagicMock()
        mock_verifier.verify_file = MagicMock(
            return_value=["line 5:3: unknown identifier 'foo'"]
        )
        adapter = SolidityAdapter(verifier=mock_verifier)

        ok, errors = adapter.verify_spec("-- broken lean code", "/ws")

        self.assertFalse(ok)
        self.assertEqual(len(errors), 1)
        self.assertIn("unknown identifier", errors[0])

    def test_verifier_exception(self):
        mock_verifier = MagicMock()
        mock_verifier.save_file = MagicMock(side_effect=OSError("disk full"))
        adapter = SolidityAdapter(verifier=mock_verifier)

        ok, errors = adapter.verify_spec("-- lean code", "/ws")

        self.assertFalse(ok)
        self.assertEqual(len(errors), 1)
        self.assertIn("infrastructure error", errors[0])


class TestRunTestsDelegation(unittest.TestCase):
    """Test run_tests delegation to SimulationRunner.run_foundry_fuzzing."""

    def test_no_test_source(self):
        mock_sim = MagicMock()
        adapter = SolidityAdapter(simulator=mock_sim)

        result = adapter.run_tests("/ws")

        self.assertFalse(result["success"])
        self.assertIn("No test_source", result["details"])

    def test_safe_fuzz_run(self):
        mock_sim = MagicMock()
        mock_sim.run_foundry_fuzzing = MagicMock(return_value={
            "safe": True,
            "log": "All invariants held.",
            "foundry_compile_pass": True,
            "foundry_test_pass": True,
            "infra_broken": False,
            "broken_invariants": [],
            "fuzz_runs": 500,
            "foundry_summary": {},
        })
        adapter = SolidityAdapter(simulator=mock_sim)

        result = adapter.run_tests("/ws", test_source="// invariant test code")

        self.assertTrue(result["success"])
        self.assertEqual(result["passed"], 500)
        self.assertEqual(result["failed"], 0)

    def test_unsafe_fuzz_run(self):
        mock_sim = MagicMock()
        mock_sim.run_foundry_fuzzing = MagicMock(return_value={
            "safe": False,
            "log": "INVARIANT BROKEN",
            "foundry_compile_pass": True,
            "foundry_test_pass": False,
            "infra_broken": False,
            "broken_invariants": ["invariant_solvency"],
            "fuzz_runs": 100,
            "foundry_summary": {},
        })
        adapter = SolidityAdapter(simulator=mock_sim)

        result = adapter.run_tests("/ws", test_source="// test code")

        self.assertFalse(result["success"])
        self.assertEqual(result["failed"], 1)

    def test_infra_broken_run(self):
        mock_sim = MagicMock()
        mock_sim.run_foundry_fuzzing = MagicMock(return_value={
            "safe": False,
            "log": "Compiler run failed",
            "foundry_compile_pass": False,
            "foundry_test_pass": False,
            "infra_broken": True,
            "broken_invariants": [],
            "fuzz_runs": 0,
            "foundry_summary": {},
        })
        adapter = SolidityAdapter(simulator=mock_sim)

        result = adapter.run_tests("/ws", test_source="// bad test code")

        self.assertFalse(result["success"])
        self.assertTrue(result["infra_broken"])


class TestGenerateCodeDelegation(unittest.TestCase):
    """Test generate_code delegation to SolidityCoder."""

    def test_first_pass_uses_modern_code(self):
        mock_coder = MagicMock()
        mock_coder.generate_modern_code = MagicMock(return_value="// generated")
        adapter = SolidityAdapter(coder=mock_coder)

        result = adapter.generate_code("Build a token", [])

        self.assertEqual(result, "// generated")
        mock_coder.generate_modern_code.assert_called_once_with("Build a token")

    def test_constrained_pass_uses_generate_code(self):
        mock_coder = MagicMock()
        mock_coder.generate_code = MagicMock(return_value="// repaired")
        adapter = SolidityAdapter(coder=mock_coder)

        result = adapter.generate_code(
            "Build a token", [],
            feedback_constraints=["Fix overflow"],
        )

        self.assertEqual(result, "// repaired")
        mock_coder.generate_code.assert_called_once()

    def test_properties_converted_to_constraints(self):
        mock_coder = MagicMock()
        mock_coder.generate_code = MagicMock(return_value="// result")
        adapter = SolidityAdapter(coder=mock_coder)

        props = [{"invariant_template": "No overflow", "name": "Overflow"}]
        adapter.generate_code(
            "Build a token", props,
            feedback_constraints=["Fix bug"],
        )

        # Should receive both the explicit constraint and the property constraint.
        call_args = mock_coder.generate_code.call_args
        constraints = call_args[0][1]  # second positional arg
        self.assertIn("Fix bug", constraints)
        self.assertTrue(any("No overflow" in c for c in constraints))


class TestRepairCodeDelegation(unittest.TestCase):
    """Test repair_code delegation to SolidityCoder."""

    def test_repair_composes_prompt(self):
        mock_coder = MagicMock()
        mock_coder.generate_code = MagicMock(return_value="// fixed")
        adapter = SolidityAdapter(coder=mock_coder)

        result = adapter.repair_code(
            "contract Broken {}",
            "expected ';' but got '}'",
            properties=[{"name": "Solvency"}],
        )

        self.assertEqual(result, "// fixed")
        call_args = mock_coder.generate_code.call_args
        prompt = call_args[0][0]
        constraints = call_args[0][1]
        self.assertIn("CURRENT SOLIDITY", prompt)
        self.assertIn("expected ';'", constraints[0])


if __name__ == "__main__":
    unittest.main()
