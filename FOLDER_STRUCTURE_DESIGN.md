# 📂 LeVer Solana Generalization — Folder Structure Design
## Architecture Diagram → Actual Directory Layout Mapping

> **⚠️ Yeh Document Kya Hai?**
> Yeh Phase 0 ke architecture diagram (Before/After Adapter Pattern) ka **exact folder structure blueprint** hai.
> Diagram ke har ek box ko real file/folder mein map kiya gaya hai.
> **Code nahi hai — sirf structure hai. Code Phase 1+ mein aayega.**

---

## 1. Current LeVer Structure (BEFORE — Hardcoded EVM)

Yeh abhi ka folder layout hai jismein Solidity har jagah hardcoded hai:

```
LeVer-Research/LeVer/
├── core/
│   ├── __init__.py
│   ├── main_pipeline.py          ← 🔴 Entry point (hardcoded SolidityCoder import)
│   ├── agents.py                 ← 🔴 SolidityCoder class (prompt: "You are a Solidity Engineer")
│   ├── config.py                 ← 🔴 Anvil RPC URL + Ethereum private keys hardcoded
│   ├── simulator.py              ← 🔴 Direct "forge build", "forge test" calls
│   ├── formal_verifier.py        ← 🔴 Sirf .lean files accept karta hai
│   ├── logger.py
│   ├── structured_logging.py
│   ├── regression_runner.py
│   └── pipeline/
│       ├── __init__.py
│       ├── workflows.py          ← 🔴 ctx.solidity_code, is_plausible_solidity_source()
│       ├── iteration.py          ← 🔴 run_common_pipeline() (Solidity logic mixed)
│       ├── context.py            ← 🔴 self.solidity_code variable
│       ├── solidity_utils.py     ← 🔴 "pragma solidity" check
│       ├── formal_stage.py
│       ├── lean_utils.py         ← 🔴 Lean-only utilities
│       ├── lean_validation.py    ← 🔴 Lean-only validation
│       ├── slither.py            ← 🔴 Slither = Solidity-only static analyzer
│       ├── checkpoint.py
│       ├── cleanup.py
│       ├── context.py
│       ├── dataset.py
│       ├── diagnostic_utils.py
│       ├── dynamic_utils.py
│       ├── metrics.py
│       ├── options.py
│       ├── fs_utils.py
│       └── collection_utils.py
├── property.json                 ← 🔴 21KB, 100% EVM vulnerabilities (Reentrancy, Delegatecall, etc.)
├── examples/
├── experiments/                  ← Runtime generated experiment outputs
├── libs_cache/                   ← forge-std, openzeppelin-contracts
├── logs/
├── requirements.txt
├── README.md
└── ...config files
```

**🔴 = Solidity hardcoded point (Coupling Problem)**

---

## 2. New LeVer Structure (AFTER — Adapter Pattern)

Diagram ke har component ka folder mapping:

```
LeVer-Research/LeVer/
│
│  ╔═══════════════════════════════════════════════════════════════════╗
│  ║  🟢 COMMON CORE ENGINE (Language Agnostic — Green Box)          ║
│  ║  Diagram: adapter_factory(target), run_common_pipeline(),       ║
│  ║           Feedback Loop & Attack Analyst                        ║
│  ╚═══════════════════════════════════════════════════════════════════╝
│
├── core/
│   ├── __init__.py
│   ├── main_pipeline.py          ← ✅ MODIFIED: --target flag, adapter_factory() call
│   │                                 Ab: adapter = adapter_factory(args.target)
│   │                                 Pehle: Seedha SolidityCoder() banata tha
│   │
│   ├── adapter_factory.py        ← 🆕 NEW: Factory function jo target string se adapter load kare
│   │                                 adapter_factory("solana") → SolanaAdapter()
│   │                                 adapter_factory("solidity") → SolidityAdapter()
│   │
│   ├── agents.py                 ← ✅ UNTOUCHED (SolidityCoder stays, used by SolidityAdapter)
│   ├── config.py                 ← ✅ UNTOUCHED (Anvil config stays, used by SolidityAdapter)
│   ├── simulator.py              ← ✅ UNTOUCHED (forge logic stays, used by SolidityAdapter)
│   ├── formal_verifier.py        ← ✅ UNTOUCHED (Lean logic stays, used by SolidityAdapter)
│   ├── logger.py                 ← ✅ UNTOUCHED
│   ├── structured_logging.py     ← ✅ UNTOUCHED
│   ├── regression_runner.py      ← ✅ UNTOUCHED
│   │
│   │  ╔═══════════════════════════════════════════════════════════════╗
│   │  ║  🔌 TARGET ADAPTER INTERFACE (Universal Contract — Blue Box) ║
│   │  ║  Diagram: Interface Methods: generate_code(), repair_code(), ║
│   │  ║           is_valid_source(), check_compilation(),            ║
│   │  ║           generate_formal_spec(), verify_spec(),             ║
│   │  ║           generate_test_harness(), run_tests(),              ║
│   │  ║           extract_counterexample()                           ║
│   │  ╚═══════════════════════════════════════════════════════════════╝
│   │
│   ├── adapters/                 ← 🆕 NEW FOLDER: Adapter Pattern ka ghar
│   │   ├── __init__.py           ← Exports: TargetAdapter, adapter_factory
│   │   │
│   │   ├── base.py               ← 🆕 TargetAdapter Abstract Base Class (ABC)
│   │   │                            Defines: generate_code(), repair_code(),
│   │   │                                     is_valid_source(), check_compilation(),
│   │   │                                     generate_formal_spec(), verify_spec(),
│   │   │                                     generate_test_harness(), run_tests(),
│   │   │                                     extract_counterexample()
│   │   │
│   │   │  ╔═══════════════════════════════════════════════════════════╗
│   │   │  ║  🟡 SOLIDITY ADAPTER (Wraps Existing Code — Yellow Box) ║
│   │   │  ║  Diagram: SolidityCoder, Foundry/forge build,           ║
│   │   │  ║           Lean 4 Verifier, forge test + Anvil            ║
│   │   │  ╚═══════════════════════════════════════════════════════════╝
│   │   │
│   │   ├── solidity_adapter.py   ← 🆕 SolidityAdapter(TargetAdapter)
│   │   │                            Wraps:
│   │   │                              generate_code()     → agents.SolidityCoder
│   │   │                              is_valid_source()   → solidity_utils.is_plausible_solidity_source()
│   │   │                              check_compilation() → simulator.check_compilation() (forge build)
│   │   │                              verify_spec()       → formal_verifier.verify_file() (Lean 4)
│   │   │                              run_tests()         → simulator.run_fuzz_and_attack() (forge test + Anvil)
│   │   │                            ⚠️ Purana koi bhi code modify NAHI hoga — sirf wrap hoga
│   │   │
│   │   │  ╔═══════════════════════════════════════════════════════════╗
│   │   │  ║  🔵 SOLANA ADAPTER (NEW Anchor + Rust — Blue Box)       ║
│   │   │  ║  Diagram: AnchorCoder Agent, anchor build,              ║
│   │   │  ║           Kani Model Checker,                           ║
│   │   │  ║           anchor test + solana-test-validator            ║
│   │   │  ╚═══════════════════════════════════════════════════════════╝
│   │   │
│   │   ├── solana_adapter.py     ← 🆕 SolanaAdapter(TargetAdapter)
│   │   │                            Implements:
│   │   │                              generate_code()     → AnchorCoder agent (Rust/Anchor prompts)
│   │   │                              is_valid_source()   → "use anchor_lang" check
│   │   │                              check_compilation() → "anchor build" subprocess
│   │   │                              verify_spec()       → "cargo kani" subprocess (Kani Model Checker)
│   │   │                              run_tests()         → "anchor test" + solana-test-validator
│   │   │                              extract_counterexample() → Solana log parser
│   │   │
│   │   │  ╔═══════════════════════════════════════════════════════════╗
│   │   │  ║  ⚪ FUTURE ADAPTERS (Extensible — Grey Box)              ║
│   │   │  ║  Diagram: Move / Aptos Adapter (Plug-in)                ║
│   │   │  ╚═══════════════════════════════════════════════════════════╝
│   │   │
│   │   └── (future: move_adapter.py, sui_adapter.py, etc.)
│   │         Kal ko naye blockchains support karne hain,
│   │         bas ek nayi file add karni hogi — core touch nahi hoga
│   │
│   │
│   ├── pipeline/                 ← ✅ EXISTING FOLDER (modifications inside)
│   │   ├── __init__.py
│   │   ├── workflows.py          ← ✅ MODIFIED: ctx.solidity_code → ctx.generated_code
│   │   │                            adapter.is_valid_source() call (not hardcoded check)
│   │   │                            adapter.check_compilation() call (not forge directly)
│   │   │
│   │   ├── iteration.py          ← ✅ MODIFIED: run_common_pipeline() ab adapter methods use kare
│   │   │                            Pehle: Seedha forge/lean call karta tha
│   │   │                            Ab: adapter.verify_spec(), adapter.run_tests()
│   │   │
│   │   ├── context.py            ← ✅ MODIFIED: self.solidity_code → self.generated_code
│   │   │                            + self.target_type field added ("solana" / "solidity")
│   │   │
│   │   ├── solidity_utils.py     ← ✅ UNTOUCHED (SolidityAdapter ke through use hoga)
│   │   ├── formal_stage.py       ← ✅ UNTOUCHED (SolidityAdapter ke through use hoga)
│   │   ├── lean_utils.py         ← ✅ UNTOUCHED
│   │   ├── lean_validation.py    ← ✅ UNTOUCHED
│   │   ├── slither.py            ← ✅ UNTOUCHED (Solidity-only, adapter scope)
│   │   │
│   │   │   ─── 🆕 Solana-specific pipeline utilities ───
│   │   │
│   │   ├── solana_utils.py       ← 🆕 NEW: "use anchor_lang" check, Anchor project validation
│   │   ├── kani_utils.py         ← 🆕 NEW: Kani harness helpers, output parsing
│   │   └── ... (existing: checkpoint.py, cleanup.py, metrics.py, etc. — UNTOUCHED)
│   │
│   │
│   │  ╔═══════════════════════════════════════════════════════════════╗
│   │  ║  🔵 SOLANA-SPECIFIC AGENTS & CONFIG                         ║
│   │  ╚═══════════════════════════════════════════════════════════════╝
│   │
│   ├── solana_agents.py          ← 🆕 NEW: AnchorCoder agent class
│   │                                Prompt: "You are a Solana Anchor + Rust Security Engineer"
│   │                                generate_anchor_code(), repair_anchor_code()
│   │
│   └── solana_config.py          ← 🆕 NEW: Solana local test config
│                                    SOLANA_TEST_VALIDATOR_URL = "http://127.0.0.1:8899"
│                                    Test keypairs (Deployer, Alice, Bob, Mallory, Sybil)
│                                    Solana CLI paths, Anchor workspace config
│
│
│  ╔═══════════════════════════════════════════════════════════════════╗
│  ║  📦 SEMANTIC IR LAYER (Properties — Purple Box)                 ║
│  ║  Diagram: properties/schema.json, solidity.json,                ║
│  ║           solana.json (SOL-01..10)                               ║
│  ╚═══════════════════════════════════════════════════════════════════╝
│
├── properties/                   ← 🆕 NEW FOLDER (replaces single property.json)
│   ├── schema.json               ← 🆕 Target-neutral IR schema definition
│   │                                Common fields: id, name, invariant_template,
│   │                                target_neutral flag, annotations per chain
│   │
│   ├── solidity.json             ← 🆕 MIGRATED from property.json
│   │                                EVM-specific: Reentrancy, Delegatecall, Selfdestruct,
│   │                                msg.value, tx.origin, etc.
│   │                                (Purane property.json ka exact data, reorganized)
│   │
│   └── solana.json               ← 🆕 NEW: Solana safety properties
│                                    SOL-01: Missing Signer Check
│                                    SOL-02: Account Ownership Validation
│                                    SOL-03: PDA & Bump Validation
│                                    SOL-04: Duplicate Account Aliasing
│                                    SOL-05: CPI Program-ID Validation
│                                    SOL-06: Sysvar Account Validation
│                                    SOL-07: Arithmetic Overflow (checked_mul etc.)
│                                    SOL-08: Signer & Authority Mismatch
│                                    SOL-09: State Transition Invariant
│                                    SOL-10: CPI Cross-Instruction Assumptions
│
├── property.json                 ← ✅ KEPT FOR BACKWARD COMPAT (deprecated, points to properties/)
│
│
│  ╔═══════════════════════════════════════════════════════════════════╗
│  ║  🧪 EXPERIMENTS & RUNTIME (Per-target Workspaces)               ║
│  ╚═══════════════════════════════════════════════════════════════════╝
│
├── experiments/
│   ├── {exp_name}/
│   │   └── {run_id}/
│   │       ├── Target.sol              ← Solidity output (when --target solidity)
│   │       ├── Target.rs               ← Anchor output (when --target solana)
│   │       ├── lean_project/           ← Lean workspace (Solidity path)
│   │       ├── kani_workspace/         ← 🆕 Kani workspace (Solana path)
│   │       ├── simulation_env/         ← Foundry env (Solidity) OR Anchor env (Solana)
│   │       │   ├── foundry.toml        ← (Solidity runs)
│   │       │   ├── Anchor.toml         ← 🆕 (Solana runs)
│   │       │   ├── src/                ← Contract source
│   │       │   ├── tests/              ← 🆕 Anchor test scripts (Solana)
│   │       │   └── programs/           ← 🆕 Anchor program structure (Solana)
│   │       │       └── {program_name}/
│   │       │           ├── Cargo.toml
│   │       │           └── src/
│   │       │               └── lib.rs
│   │       ├── checkpoint.json
│   │       ├── result.json
│   │       ├── execution.log
│   │       └── metrics_iter_*.json
│   │
│   └── ... (existing experiments — UNTOUCHED)
│
│
│  ╔═══════════════════════════════════════════════════════════════════╗
│  ║  📚 LIBS CACHE (Shared Dependencies)                            ║
│  ╚═══════════════════════════════════════════════════════════════════╝
│
├── libs_cache/
│   ├── forge-std/                ← ✅ EXISTING (Solidity test framework)
│   ├── openzeppelin-contracts/   ← ✅ EXISTING (Solidity libraries)
│   └── anchor-spl/              ← 🆕 NEW (Solana SPL Token program interfaces — cached)
│
│
│  ╔═══════════════════════════════════════════════════════════════════╗
│  ║  📄 ROOT FILES                                                  ║
│  ╚═══════════════════════════════════════════════════════════════════╝
│
├── README.md                     ← ✅ UPDATED: --target flag documentation added
├── requirements.txt              ← ✅ UPDATED: solana-py, anchorpy added (if needed)
├── env.sh / env.ps1              ← ✅ UPDATED: SOLANA_CLUSTER, ANCHOR_PATH env vars
└── ...
```

---

## 3. Diagram Component → Folder Mapping Table

Yeh table **diagram ke har ek box** ko exact file/folder se map karta hai:

### 🟢 Common Core Engine (Green Box)

| Diagram Component | File/Folder | Status | Description |
|-------------------|-------------|--------|-------------|
| `adapter_factory(target)` | `core/adapter_factory.py` | 🆕 NEW | Target string → Adapter instance |
| `run_common_pipeline()` | `core/pipeline/iteration.py` | ✅ MODIFIED | Ab adapter methods through chale |
| `Feedback Loop & Attack Analyst` | `core/pipeline/workflows.py` | ✅ MODIFIED | ctx.solidity_code → ctx.generated_code |
| Pipeline Context | `core/pipeline/context.py` | ✅ MODIFIED | target_type field added |

### 🔌 TargetAdapter Interface (Blue Border Box)

| Diagram Component | File/Folder | Status | Description |
|-------------------|-------------|--------|-------------|
| Interface Methods | `core/adapters/base.py` | 🆕 NEW | Abstract Base Class with 9 methods |
| generate_code() + repair_code() | base.py abstract methods | 🆕 | Code generation contract |
| is_valid_source() + check_compilation() | base.py abstract methods | 🆕 | Validation contract |
| generate_formal_spec() + verify_spec() | base.py abstract methods | 🆕 | Verification contract |
| generate_test_harness() + run_tests() | base.py abstract methods | 🆕 | Testing contract |
| extract_counterexample() | base.py abstract method | 🆕 | Attack analysis contract |

### 🟡 Solidity Adapter (Yellow Box — Wraps Existing Code)

| Diagram Component | File/Folder | Status | Description |
|-------------------|-------------|--------|-------------|
| SolidityCoder | `core/agents.py` (existing) | ✅ UNTOUCHED | Wrapped by SolidityAdapter |
| Foundry / forge build | `core/simulator.py` (existing) | ✅ UNTOUCHED | Wrapped by SolidityAdapter |
| Lean 4 Verifier | `core/formal_verifier.py` (existing) | ✅ UNTOUCHED | Wrapped by SolidityAdapter |
| forge test + Anvil | `core/simulator.py` (existing) | ✅ UNTOUCHED | Wrapped by SolidityAdapter |
| SolidityAdapter class | `core/adapters/solidity_adapter.py` | 🆕 NEW | Wrapper over all above |

### 🔵 Solana Adapter (Blue Box — NEW)

| Diagram Component | File/Folder | Status | Description |
|-------------------|-------------|--------|-------------|
| AnchorCoder Agent | `core/solana_agents.py` | 🆕 NEW | Anchor/Rust code generation |
| anchor build | `core/adapters/solana_adapter.py` | 🆕 NEW | subprocess: anchor build |
| Kani Model Checker | `core/adapters/solana_adapter.py` | 🆕 NEW | subprocess: cargo kani |
| anchor test + solana-test-validator | `core/adapters/solana_adapter.py` | 🆕 NEW | subprocess: anchor test |
| Solana Config | `core/solana_config.py` | 🆕 NEW | Test validator URL + keypairs |
| Solana Utilities | `core/pipeline/solana_utils.py` | 🆕 NEW | Anchor validation helpers |
| Kani Utilities | `core/pipeline/kani_utils.py` | 🆕 NEW | Kani output parsing |

### ⚪ Future Adapters (Grey Box)

| Diagram Component | File/Folder | Status | Description |
|-------------------|-------------|--------|-------------|
| Move / Aptos Adapter | `core/adapters/move_adapter.py` | 🔮 FUTURE | Plug-in without touching core |
| Sui Adapter | `core/adapters/sui_adapter.py` | 🔮 FUTURE | Plug-in without touching core |

### 📦 Semantic IR Layer (Purple Box)

| Diagram Component | File/Folder | Status | Description |
|-------------------|-------------|--------|-------------|
| properties/schema.json | `properties/schema.json` | 🆕 NEW | Target-neutral IR schema |
| solidity.json | `properties/solidity.json` | 🆕 MIGRATED | From property.json |
| solana.json (SOL-01..10) | `properties/solana.json` | 🆕 NEW | 10 Solana safety properties |

---

## 4. File Change Summary

### 🆕 New Files (Total: 10)

| # | File Path | Purpose |
|---|-----------|---------|
| 1 | `core/adapter_factory.py` | Factory function: target string → adapter |
| 2 | `core/adapters/__init__.py` | Package exports |
| 3 | `core/adapters/base.py` | TargetAdapter ABC |
| 4 | `core/adapters/solidity_adapter.py` | SolidityAdapter wrapper |
| 5 | `core/adapters/solana_adapter.py` | SolanaAdapter implementation |
| 6 | `core/solana_agents.py` | AnchorCoder LLM agent |
| 7 | `core/solana_config.py` | Solana test configuration |
| 8 | `core/pipeline/solana_utils.py` | Anchor validation utilities |
| 9 | `core/pipeline/kani_utils.py` | Kani output parsing utilities |
| 10 | `properties/schema.json` | Target-neutral IR schema |

### 🔄 New Data Files (Total: 2)

| # | File Path | Purpose |
|---|-----------|---------|
| 1 | `properties/solidity.json` | Migrated from property.json |
| 2 | `properties/solana.json` | SOL-01 to SOL-10 properties |

### ✅ Modified Files (Total: 4)

| # | File Path | What Changes |
|---|-----------|-------------|
| 1 | `core/main_pipeline.py` | `--target` flag, adapter_factory() call |
| 2 | `core/pipeline/workflows.py` | ctx.solidity_code → ctx.generated_code |
| 3 | `core/pipeline/iteration.py` | adapter methods through common pipeline |
| 4 | `core/pipeline/context.py` | target_type field, generic variable name |

### 🚫 Untouched Files (Critical — No Breaking Changes)

| File | Why Untouched |
|------|---------------|
| `core/agents.py` | SolidityCoder stays — used by SolidityAdapter |
| `core/config.py` | Anvil config stays — used by SolidityAdapter |
| `core/simulator.py` | Forge logic stays — used by SolidityAdapter |
| `core/formal_verifier.py` | Lean logic stays — used by SolidityAdapter |
| `core/pipeline/solidity_utils.py` | is_plausible_solidity_source() stays |
| `core/pipeline/lean_utils.py` | Lean helpers stay |
| `core/pipeline/lean_validation.py` | Lean validation stays |
| `core/pipeline/slither.py` | Slither stays (Solidity-only tool) |
| All other pipeline/*.py | No changes needed |

---

## 5. Data Flow: --target Flag Se Kaise Kaam Karega

```
User Command:
  python -m core.main_pipeline --target solana --req-file req.txt

                    │
                    ▼
         ┌─────────────────────┐
         │  main_pipeline.py   │
         │  args.target="solana"│
         └────────┬────────────┘
                  │
                  ▼
         ┌─────────────────────┐
         │ adapter_factory.py  │
         │ "solana" → SolanaAdapter()
         │ "solidity" → SolidityAdapter()
         └────────┬────────────┘
                  │
                  ▼
         ┌─────────────────────┐
         │   workflows.py      │
         │   adapter.generate_code()     ← (AnchorCoder → Rust code)
         │   adapter.is_valid_source()   ← ("use anchor_lang" check)
         │   adapter.check_compilation() ← ("anchor build")
         └────────┬────────────┘
                  │
        ┌─────────┴──────────┐
        ▼                    ▼
  ┌───────────┐      ┌────────────┐
  │ FORMAL    │      │ EMPIRICAL  │
  │ verify_   │      │ run_tests()│
  │ spec()    │      │ "anchor    │
  │ "cargo    │      │  test" +   │
  │  kani"    │      │  validator │
  └─────┬─────┘      └─────┬──────┘
        │                   │
        └─────────┬─────────┘
                  ▼
         ┌─────────────────────┐
         │ extract_counter     │
         │ example() → Feedback│
         │ → repair_code()     │
         │ (Loop until pass)   │
         └─────────────────────┘
```

---

## 6. Anchor Project Structure (Solana Simulation Env)

Jab `--target solana` hoga, `simulation_env/` ka layout:

```
simulation_env/                    (= Anchor workspace)
├── Anchor.toml                    ← Anchor workspace config
├── Cargo.toml                     ← Rust workspace manifest
├── programs/
│   └── lever_target/              ← Generated program
│       ├── Cargo.toml             ← Program dependencies (anchor-lang, anchor-spl)
│       └── src/
│           └── lib.rs             ← 🎯 AI-generated Anchor program (target code)
├── tests/
│   ├── attack_signer.ts           ← SOL-01: Missing signer attack test
│   ├── attack_ownership.ts        ← SOL-02: Ownership bypass test
│   ├── attack_pda.ts              ← SOL-03: PDA manipulation test
│   ├── attack_duplicate.ts        ← SOL-04: Duplicate account test
│   ├── attack_cpi.ts              ← SOL-05: Fake CPI program test
│   └── ... (SOL-06 to SOL-10)
├── kani_harness/                  ← 🆕 Kani verification harnesses
│   ├── harness_overflow.rs        ← SOL-07: Arithmetic bounds check
│   ├── harness_state.rs           ← SOL-09: State transition proof
│   └── harness_pda.rs             ← SOL-03: PDA bump verification
└── migrations/
    └── deploy.ts
```

---

## 7. Naming Conventions

| Category | Convention | Example |
|----------|-----------|---------|
| Adapter class | `{Chain}Adapter` | `SolanaAdapter`, `SolidityAdapter` |
| Agent class | `{Chain}Coder` or `AnchorCoder` | `AnchorCoder`, `SolidityCoder` |
| Config file | `{chain}_config.py` | `solana_config.py`, `config.py` (existing) |
| Utils file | `{chain}_utils.py` | `solana_utils.py`, `solidity_utils.py` |
| Properties file | `{chain}.json` | `solana.json`, `solidity.json` |
| Output file | `Target.{ext}` | `Target.rs` (Solana), `Target.sol` (Solidity) |

---

## 8. Key Design Rules

1. **🚫 Core Pipeline = Chain Agnostic**: `iteration.py` aur `workflows.py` mein koi bhi chain-specific logic NAHI hogi. Sab kuch adapter methods se hoga.

2. **🔒 Backward Compatibility**: Purana koi bhi test ya Solidity workflow break NAHI hoga. `SolidityAdapter` existing code ko wrap karega bina modify kiye.

3. **🔌 Plug-In Rule**: Naya chain add karna = 1 adapter file + 1 agent file + 1 config file + 1 properties JSON. Core touch nahi karna padega.

4. **📦 Properties Split**: `property.json` deprecated hoga lekin hatega nahi. Naye runs `properties/` folder se load karenge.

5. **🧪 Isolated Workspaces**: Har run ka `simulation_env/` independent hoga — Solidity run ka Foundry layout, Solana run ka Anchor layout.
