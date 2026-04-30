"""Generate networks.json from the visual editor's networks config.

The visual config stores networks as a list:
  [
    {
      "network": "mainnet",
      "contracts": {
        "Alchemist": {
          "instances": [
            { "label": "alUSD", "address": "0xAAA...", "startBlock": 14265505 },
            { "label": "alETH", "address": "0xBBB...", "startBlock": 14265505 }
          ]
        }
      }
    }
  ]

The generated networks.json follows graph-cli's multi-network format, with one
top-level key per contract *instance* (ContractType_label):

  {
    "mainnet": {
      "Alchemist_alUSD": { "address": "0xAAA...", "startBlock": 14265505 },
      "Alchemist_alETH": { "address": "0xBBB...", "startBlock": 14265505 }
    }
  }

This allows `graph build --network mainnet` to substitute the correct values
into the mustache placeholders in subgraph.yaml.
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def build_networks_json(networks_config: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the networks.json data structure from the visual config.

    Args:
        networks_config: List of network entries from visual-config.json.

    Returns:
        Dictionary suitable for serialisation as networks.json.

    Raises:
        ValueError: If the config is malformed.
    """
    result: dict[str, dict[str, Any]] = {}

    for entry in networks_config:
        network_name = entry.get("network", "").strip()
        if not network_name:
            logger.warning("Skipping network entry with empty network name")
            continue

        contracts = entry.get("contracts", {})
        if not isinstance(contracts, dict):
            raise ValueError(f"'contracts' must be a dict, got {type(contracts)}")

        network_block: dict[str, Any] = result.setdefault(network_name, {})

        for contract_type, contract_data in contracts.items():
            instances = contract_data.get("instances", [])
            for inst in instances:
                label = inst.get("label", "").strip()
                address = inst.get("address", "").strip()
                start_block_raw = inst.get("startBlock", "")

                if not label:
                    logger.warning(
                        f"Skipping instance with no label for {contract_type} on {network_name}"
                    )
                    continue

                # Key in networks.json: ContractType_label (e.g. Alchemist_alUSD)
                key = f"{contract_type}_{label}"

                entry_data: dict[str, Any] = {}
                if address:
                    entry_data["address"] = address
                if start_block_raw != "":
                    try:
                        entry_data["startBlock"] = int(start_block_raw)
                    except (ValueError, TypeError):
                        logger.warning(
                            f"Invalid startBlock '{start_block_raw}' for {key} on {network_name}, skipping"
                        )

                network_block[key] = entry_data

    return result


def render_networks_json(networks_config: list[dict[str, Any]]) -> str:
    """Render networks.json content as a pretty-printed JSON string.

    Args:
        networks_config: List of network entries from visual-config.json.

    Returns:
        Pretty-printed JSON string.
    """
    data = build_networks_json(networks_config)
    return json.dumps(data, indent=2)


def write_networks_json(
    networks_config: list[dict[str, Any]],
    output_dir: Path,
) -> Path:
    """Write networks.json to the output directory.

    Args:
        networks_config: List of network entries from visual-config.json.
        output_dir: Directory to write networks.json into.

    Returns:
        Path to the written file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "networks.json"
    content = render_networks_json(networks_config)
    out_path.write_text(content, encoding="utf-8")
    logger.info(f"Wrote {out_path}")
    return out_path
