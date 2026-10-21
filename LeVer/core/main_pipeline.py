import argparse
import json
import os
import re
import sys
from pathlib import Path

from core.adapter_factory import adapter_factory

from core.agents import (
    AttackAnalyst,
    AuditorAgent,
    EnvironmentArchitect,
    FatalLLMError,
    LeanFormalizer,
    LeanProver,
    PropertySelector,
    SemanticObligationExtractor,
    SolidityCoder,
)
from core.formal_verifier import FormalVerifier
from core.logger import GLOBAL_LOGGER
from core.pipeline.checkpoint import CheckpointManager
from core.pipeline.context import PipelineContext
from core.pipeline.workflows import workflow_from_requirement
from core.simulator import SimulationRunner


VALID_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def _safe_name(value: str, label: str) -> str:
    if not VALID_NAME.fullmatch(value or "") or value in {".", ".."}:
        raise ValueError(
            f"{label} must contain only letters, numbers, '.', '_' or '-': {value!r}"
        )
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run LeVer from a natural-language requirement in one of three modes."
    )
    parser.add_argument(
        "--mode",
        choices=["full", "lean_only", "no_lean"],
        default="full",
    )
    parser.add_argument("--req-file", required=True, help="UTF-8 requirement text file")
    parser.add_argument("--exp-name", default="three_mode_smoke")
    parser.add_argument("--run-id", default="run_0")
    parser.add_argument("--max-iters", type=int, default=3)
    parser.add_argument("--attack-rounds", type=int, default=3)
    parser.add_argument(
        "--model",
        default=os.getenv("LLM_MODEL", "gemma4:e2b"),
        help="LLM model name (also settable via LLM_MODEL env var).",
    )
    parser.add_argument(
        "--slither-command",
        default=os.getenv("SLITHER_COMMAND", "slither"),
        help="Slither executable or command prefix (also configurable via SLITHER_COMMAND).",
    )
    parser.add_argument(
        "--target",
        choices=["solidity", "solana"],
        default="solidity",
        help="Target blockchain platform (default: solidity).",
    )
    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        exp_name = _safe_name(args.exp_name, "--exp-name")
        run_id = _safe_name(args.run_id, "--run-id")
        if args.max_iters < 1 or args.attack_rounds < 1:
            raise ValueError("--max-iters and --attack-rounds must be positive")
        if not args.slither_command.strip():
            raise ValueError("--slither-command must not be empty")
        os.environ["SLITHER_COMMAND"] = args.slither_command

        req_path = Path(args.req_file).expanduser().resolve()
        requirement = req_path.read_text(encoding="utf-8").strip()
        if not requirement:
            raise ValueError(f"Requirement file is empty: {req_path}")

        project_root = Path.cwd().resolve()
        experiments_root = (project_root / "experiments").resolve()
        workspace = (experiments_root / exp_name / run_id).resolve()
        if experiments_root not in workspace.parents:
            raise ValueError(f"Workspace escapes experiments root: {workspace}")
        workspace.mkdir(parents=True, exist_ok=True)

        GLOBAL_LOGGER.configure(str(workspace / "execution.log"))
        checkpoint = CheckpointManager(str(workspace / "checkpoint.json"))
        ctx = PipelineContext(str(workspace), checkpoint)

        # ── Create the target adapter ─────────────────────────────────
        # SolidityAdapter accepts model_name and simulator kwargs;
        # SolanaAdapter currently takes no constructor arguments.
        target = args.target
        if target == "solidity":
            # Simulator is needed for compilation; created early so it
            # can be injected into both the adapter and the tools dict.
            simulator = SimulationRunner(
                root_dir=str(workspace / "simulation_env"),
                attack_rounds=args.attack_rounds,
            )
            adapter = adapter_factory(
                target,
                model_name=args.model,
                simulator=simulator,
            )
        elif target == "solana":
            # Solana adapter methods are not yet implemented.
            # Fail early with a clear, actionable message rather than
            # letting the pipeline enter the Solidity-specific workflow.
            raise NotImplementedError(
                "Solana target support is not yet implemented. "
                "The SolanaAdapter scaffold exists but all methods raise "
                "NotImplementedError. To use LeVer, run with '--target solidity' "
                "(the default). Solana support will be available in a future release."
            )
        else:
            # Should not be reachable due to argparse choices, but
            # guard defensively for programmatic callers.
            adapter = adapter_factory(target)

        property_path = project_root / "property.json"
        if not property_path.is_file():
            raise FileNotFoundError(f"Property knowledge base not found: {property_path}")

        common = {"model_name": args.model}
        agents = {
            "coder": SolidityCoder(**common),
            "selector": PropertySelector(json_path=str(property_path), **common),
            "semantic_extractor": SemanticObligationExtractor(),
        }
        if args.mode in {"full", "lean_only"}:
            agents.update({
                "formalizer": LeanFormalizer(**common),
                "prover": LeanProver(**common),
            })
        if args.mode in {"full", "no_lean"}:
            agents.update({
                "architect": EnvironmentArchitect(**common),
                "auditor": AuditorAgent(**common),
                "analyst": AttackAnalyst(**common),
            })

        tools = {"simulator": simulator}
        if args.mode in {"full", "lean_only"}:
            tools["verifier"] = FormalVerifier(project_root=str(workspace / "lean_project"))

        print(f"\nTarget: {target}")
        print(f"Mode: {args.mode}")
        print(f"Model: {args.model}")
        print(f"Workspace: {workspace}")
        passed = workflow_from_requirement(
            ctx=ctx,
            agents=agents,
            tools=tools,
            requirement=requirement,
            mode=args.mode,
            max_iters=args.max_iters,
            adapter=adapter,
        )

        final_path = workspace / "result.json"
        result = json.loads(final_path.read_text(encoding="utf-8"))
        print(f"\nPIPELINE {'PASSED' if passed else 'FAILED'}: {args.mode}")
        print(f"Result: {final_path}")
        print(f"Iterations: {result.get('iterations')}")
        return 0 if passed else 1
    except FatalLLMError as exc:
        print(f"LLM EXECUTION ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"PIPELINE EXECUTION ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
