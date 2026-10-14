# ──────────────────────────────────────────────────────────────────────
# core/solana_config.py  — 🆕 NEW
# Solana local test configuration.
#
# Mirrors core/config.py (Anvil/EVM config) but for the Solana toolchain.
# Uses solana-test-validator for local simulation.
# ──────────────────────────────────────────────────────────────────────

import os

# ── Solana Cluster / RPC ─────────────────────────────────────────────

SOLANA_TEST_VALIDATOR_URL = os.getenv(
    "SOLANA_TEST_VALIDATOR_URL", "http://127.0.0.1:8899"
)

SOLANA_CLUSTER = os.getenv("SOLANA_CLUSTER", "localnet")

# ── CLI Paths ────────────────────────────────────────────────────────

ANCHOR_CLI = os.getenv("ANCHOR_CLI", "anchor")
SOLANA_CLI = os.getenv("SOLANA_CLI", "solana")
CARGO_KANI_CLI = os.getenv("CARGO_KANI_CLI", "cargo-kani")

# ── Test Keypairs (LOCAL-NET ONLY — never use on mainnet) ────────────
# These are well-known devnet/localnet keypairs for testing.

SOLANA_TEST_CONFIG = {
    "rpc_url": SOLANA_TEST_VALIDATOR_URL,
    "cluster": SOLANA_CLUSTER,
    "accounts": {
        "Deployer": {
            "role": "SYSTEM_DEPLOYER",
            "keypair_path": os.getenv(
                "SOLANA_DEPLOYER_KEYPAIR",
                os.path.expanduser("~/.config/solana/id.json"),
            ),
            "description": "Program deploy authority",
        },
        # --- Honest Users (2 accounts) ---
        "Alice": {
            "role": "HONEST_USER",
            "keypair_path": "",  # TODO: Generate or load test keypair
            "description": "Honest end-user A",
        },
        "Bob": {
            "role": "HONEST_USER",
            "keypair_path": "",  # TODO: Generate or load test keypair
            "description": "Honest end-user B",
        },
        # --- Malicious Attackers (2 accounts) ---
        "Mallory": {
            "role": "MALICIOUS_ATTACKER",
            "keypair_path": "",  # TODO: Generate or load test keypair
            "description": "Malicious attacker attempting exploits",
        },
        "Sybil": {
            "role": "MALICIOUS_ATTACKER",
            "keypair_path": "",  # TODO: Generate or load test keypair
            "description": "Sybil attacker (duplicate account aliasing)",
        },
    },
}

# ── Anchor Workspace Defaults ────────────────────────────────────────

ANCHOR_WORKSPACE_DEFAULTS = {
    "anchor_version": os.getenv("ANCHOR_VERSION", "0.30.1"),
    "solana_version": os.getenv("SOLANA_VERSION", "1.18.26"),
    "rust_version": os.getenv("RUST_VERSION", "1.79.0"),
    "program_name": "lever_target",
}


def get_simulation_agents():
    """Returns a dict of all test accounts excluding the Deployer."""
    return {
        k: v
        for k, v in SOLANA_TEST_CONFIG["accounts"].items()
        if k != "Deployer"
    }
