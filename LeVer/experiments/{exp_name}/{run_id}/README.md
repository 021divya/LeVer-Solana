# ──────────────────────────────────────────────────────────────────────
# Experiment Template — Solana Run
# This directory is created at runtime by the pipeline.
# 
# When --target solana:
#   Target.rs              ← Generated Anchor program source
#   kani_workspace/        ← Kani formal verification workspace  
#   simulation_env/        ← Anchor project (build + test)
#     ├── Anchor.toml
#     ├── programs/lever_target/src/lib.rs
#     ├── tests/
#     └── migrations/
#   checkpoint.json        ← Pipeline state checkpoint
#   result.json            ← Final pass/fail result
#   execution.log          ← Full execution log
#   metrics_iter_*.json    ← Per-iteration metrics
#
# When --target solidity:
#   Target.sol             ← Generated Solidity source
#   lean_project/          ← Lean 4 formal verification workspace
#   simulation_env/        ← Foundry project (forge build + test)
#     ├── foundry.toml
#     ├── src/
#     └── script/
#   (same checkpoint/result/log/metrics files)
# ──────────────────────────────────────────────────────────────────────
