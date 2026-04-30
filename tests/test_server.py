"""Tests for the FastAPI server routes."""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from subgraph_wizard.server import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

MINIMAL_ABI = [
    {
        "type": "event",
        "name": "Transfer",
        "inputs": [
            {"name": "from", "type": "address", "indexed": True},
            {"name": "to", "type": "address", "indexed": True},
            {"name": "value", "type": "uint256", "indexed": False},
        ],
    },
    {
        "type": "function",
        "name": "balanceOf",
        "stateMutability": "view",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
]


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_health_returns_200(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_health_returns_ok_status(self):
        resp = client.get("/api/health")
        assert resp.json()["status"] == "ok"

    def test_health_returns_version(self):
        resp = client.get("/api/health")
        assert "version" in resp.json()


# ---------------------------------------------------------------------------
# POST /api/abi/parse
# ---------------------------------------------------------------------------

class TestAbiParseEndpoint:
    def test_parse_returns_200(self):
        resp = client.post("/api/abi/parse", json={"abi": MINIMAL_ABI})
        assert resp.status_code == 200

    def test_parse_returns_events(self):
        resp = client.post("/api/abi/parse", json={"abi": MINIMAL_ABI})
        data = resp.json()
        assert "events" in data
        assert len(data["events"]) == 1
        assert data["events"][0]["name"] == "Transfer"

    def test_parse_returns_read_functions(self):
        resp = client.post("/api/abi/parse", json={"abi": MINIMAL_ABI})
        data = resp.json()
        assert "read_functions" in data
        assert len(data["read_functions"]) == 1
        assert data["read_functions"][0]["name"] == "balanceOf"

    def test_parse_event_params_included(self):
        resp = client.post("/api/abi/parse", json={"abi": MINIMAL_ABI})
        params = resp.json()["events"][0]["params"]
        assert len(params) == 3
        assert params[0]["name"] == "from"
        assert params[2]["graph_type"] == "BigInt"

    def test_parse_read_function_inputs_included(self):
        resp = client.post("/api/abi/parse", json={"abi": MINIMAL_ABI})
        inputs = resp.json()["read_functions"][0]["inputs"]
        assert len(inputs) == 1
        # Solidity `address` maps to the Graph type `Address`, not `Bytes`
        assert inputs[0]["graph_type"] == "Address"

    def test_parse_empty_abi_returns_422(self):
        resp = client.post("/api/abi/parse", json={"abi": []})
        assert resp.status_code == 422

    def test_parse_invalid_body_returns_422(self):
        resp = client.post("/api/abi/parse", json={"abi": "not-a-list"})
        assert resp.status_code == 422

    def test_parse_abi_missing_type_field_returns_422(self):
        bad_abi = [{"name": "Transfer"}]  # missing "type"
        resp = client.post("/api/abi/parse", json={"abi": bad_abi})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/abi/fetch
# ---------------------------------------------------------------------------

class TestAbiFetchEndpoint:
    def test_fetch_returns_200_on_success(self):
        with patch("subgraph_wizard.abi.etherscan.fetch_abi_from_explorer") as mock_fetch:
            mock_fetch.return_value = MINIMAL_ABI
            resp = client.post(
                "/api/abi/fetch",
                json={"address": "0x6B175474E89094C44Da98b954EedeAC495271d0F", "network": "ethereum"},
            )
        assert resp.status_code == 200

    def test_fetch_returns_abi_events_and_read_functions(self):
        with patch("subgraph_wizard.abi.etherscan.fetch_abi_from_explorer") as mock_fetch:
            mock_fetch.return_value = MINIMAL_ABI
            resp = client.post(
                "/api/abi/fetch",
                json={"address": "0x6B175474E89094C44Da98b954EedeAC495271d0F", "network": "ethereum"},
            )
        data = resp.json()
        assert "abi" in data
        assert "events" in data
        assert "read_functions" in data

    def test_fetch_passes_address_and_network_to_etherscan(self):
        with patch("subgraph_wizard.abi.etherscan.fetch_abi_from_explorer") as mock_fetch:
            mock_fetch.return_value = MINIMAL_ABI
            client.post(
                "/api/abi/fetch",
                json={"address": "0xABC", "network": "optimism"},
            )
        mock_fetch.assert_called_once_with("0xABC", "optimism")

    def test_fetch_error_returns_422(self):
        from subgraph_wizard.errors import AbiFetchError
        with patch("subgraph_wizard.abi.etherscan.fetch_abi_from_explorer") as mock_fetch:
            mock_fetch.side_effect = AbiFetchError("Contract not verified")
            resp = client.post(
                "/api/abi/fetch",
                json={"address": "0x0000000000000000000000000000000000000000", "network": "ethereum"},
            )
        assert resp.status_code == 422
        assert "Contract not verified" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /api/config  and  POST /api/config
# ---------------------------------------------------------------------------

MINIMAL_CONFIG = {
    "schema_version": 1,
    "subgraph_name": "my-subgraph",
    "networks": [],
    "nodes": [
        {
            "id": "contract-1",
            "type": "contract",
            "position": {"x": 0, "y": 0},
            "data": {
                "name": "ERC20",
                "abi": [],
                "events": [],
                "readFunctions": [],
                "instances": [{"label": "main", "address": "0xAAA", "startBlock": 1}],
            },
        }
    ],
    "edges": [],
}


class TestConfigEndpoints:
    def test_load_returns_scaffold_when_no_file(self, tmp_path):
        resp = client.get("/api/config", params={"dir": str(tmp_path)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["schema_version"] == 1
        assert data["nodes"] == []
        assert data["edges"] == []

    def test_save_returns_200(self, tmp_path):
        resp = client.post("/api/config", json=MINIMAL_CONFIG, params={"dir": str(tmp_path)})
        assert resp.status_code == 200

    def test_save_returns_saved_true(self, tmp_path):
        resp = client.post("/api/config", json=MINIMAL_CONFIG, params={"dir": str(tmp_path)})
        assert resp.json()["saved"] is True

    def test_save_creates_file(self, tmp_path):
        client.post("/api/config", json=MINIMAL_CONFIG, params={"dir": str(tmp_path)})
        assert (tmp_path / "visual-config.json").exists()

    def test_save_then_load_roundtrip(self, tmp_path):
        """Save a config then load it back — data should be identical."""
        client.post("/api/config", json=MINIMAL_CONFIG, params={"dir": str(tmp_path)})
        resp = client.get("/api/config", params={"dir": str(tmp_path)})
        data = resp.json()
        assert data["subgraph_name"] == "my-subgraph"
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["id"] == "contract-1"

    def test_save_preserves_subgraph_name(self, tmp_path):
        payload = {**MINIMAL_CONFIG, "subgraph_name": "curve-subgraph"}
        client.post("/api/config", json=payload, params={"dir": str(tmp_path)})
        resp = client.get("/api/config", params={"dir": str(tmp_path)})
        assert resp.json()["subgraph_name"] == "curve-subgraph"

    def test_save_preserves_networks(self, tmp_path):
        network = {
            "network": "mainnet",
            "contracts": {
                "ERC20": {"instances": [{"label": "t", "address": "0xAAA", "startBlock": 1}]}
            },
        }
        payload = {**MINIMAL_CONFIG, "networks": [network]}
        client.post("/api/config", json=payload, params={"dir": str(tmp_path)})
        resp = client.get("/api/config", params={"dir": str(tmp_path)})
        assert len(resp.json()["networks"]) == 1
        assert resp.json()["networks"][0]["network"] == "mainnet"

    def test_save_returns_path(self, tmp_path):
        resp = client.post("/api/config", json=MINIMAL_CONFIG, params={"dir": str(tmp_path)})
        assert "path" in resp.json()
        assert "visual-config.json" in resp.json()["path"]


# ---------------------------------------------------------------------------
# POST /api/validate
# ---------------------------------------------------------------------------

class TestValidateEndpoint:
    def test_validate_returns_200(self):
        resp = client.post("/api/validate", json=MINIMAL_CONFIG)
        assert resp.status_code == 200

    def test_validate_returns_issues_and_has_errors(self):
        resp = client.post("/api/validate", json=MINIMAL_CONFIG)
        data = resp.json()
        assert "issues" in data
        assert "has_errors" in data

    def test_validate_empty_config_no_issues(self):
        payload = {**MINIMAL_CONFIG, "nodes": [], "edges": []}
        resp = client.post("/api/validate", json=payload)
        data = resp.json()
        assert data["issues"] == []
        assert data["has_errors"] is False

    def test_validate_contract_no_abi_is_error(self):
        node_no_abi = {
            "id": "c1",
            "type": "contract",
            "position": {"x": 0, "y": 0},
            "data": {"name": "ERC20", "abi": [], "events": [], "readFunctions": [], "instances": []},
        }
        payload = {**MINIMAL_CONFIG, "nodes": [node_no_abi], "edges": []}
        resp = client.post("/api/validate", json=payload)
        data = resp.json()
        codes = {i["code"] for i in data["issues"]}
        assert "CONTRACT_NO_ABI" in codes
        assert data["has_errors"] is True


# ---------------------------------------------------------------------------
# POST /api/generate  (smoke test)
# ---------------------------------------------------------------------------

class TestGenerateEndpoint:
    def test_generate_returns_200(self, tmp_path):
        """generate with a valid config writes files and returns 200."""
        payload = {
            "schema_version": 1,
            "subgraph_name": "test-gen",
            "networks": [
                {
                    "network": "mainnet",
                    "contracts": {
                        "ERC20": {
                            "instances": [{"label": "main", "address": "0xAAA", "startBlock": 1}]
                        }
                    },
                }
            ],
            "nodes": [
                {
                    "id": "c1",
                    "type": "contract",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "name": "ERC20",
                        "abi": [],
                        "events": [],
                        "readFunctions": [],
                        "instances": [{"label": "main", "address": "0xAAA", "startBlock": 1}],
                    },
                }
            ],
            "edges": [],
        }
        resp = client.post("/api/generate", json=payload, params={"dir": str(tmp_path)})
        assert resp.status_code == 200

    def test_generate_returns_files_list(self, tmp_path):
        payload = {
            "schema_version": 1,
            "subgraph_name": "test-gen",
            "networks": [],
            "nodes": [],
            "edges": [],
        }
        resp = client.post("/api/generate", json=payload, params={"dir": str(tmp_path)})
        data = resp.json()
        assert "files" in data
        assert isinstance(data["files"], list)

    def test_generate_writes_visual_config(self, tmp_path):
        payload = {
            "schema_version": 1,
            "subgraph_name": "roundtrip",
            "networks": [],
            "nodes": [],
            "edges": [],
        }
        client.post("/api/generate", json=payload, params={"dir": str(tmp_path)})
        assert (tmp_path / "visual-config.json").exists()

    def test_generate_writes_subgraph_yaml(self, tmp_path):
        payload = {
            "schema_version": 1,
            "subgraph_name": "roundtrip",
            "networks": [],
            "nodes": [
                {
                    "id": "c1",
                    "type": "contract",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "name": "ERC20",
                        "abi": [{"type": "event"}],
                        "events": [],
                        "readFunctions": [],
                        "instances": [{"label": "main", "address": "0xAAA", "startBlock": 1}],
                    },
                }
            ],
            "edges": [],
        }
        client.post("/api/generate", json=payload, params={"dir": str(tmp_path)})
        assert (tmp_path / "subgraph.yaml").exists()


# ---------------------------------------------------------------------------
# GET /api/fs/browse
# ---------------------------------------------------------------------------

class TestFsBrowseEndpoint:
    def test_browse_no_path_defaults_to_home(self):
        """No path param → defaults to user home directory."""
        import os
        home = os.path.expanduser("~")
        resp = client.get("/api/fs/browse")
        assert resp.status_code == 200
        data = resp.json()
        assert data["path"] == home

    def test_browse_no_path_returns_required_keys(self):
        resp = client.get("/api/fs/browse")
        assert resp.status_code == 200
        data = resp.json()
        assert "path" in data
        assert "parent" in data
        assert "dirs" in data

    def test_browse_dirs_is_list(self):
        resp = client.get("/api/fs/browse")
        assert isinstance(resp.json()["dirs"], list)

    def test_browse_dirs_entries_have_name_and_path(self):
        resp = client.get("/api/fs/browse")
        for entry in resp.json()["dirs"]:
            assert "name" in entry
            assert "path" in entry

    def test_browse_with_specific_valid_path(self, tmp_path):
        """A specific valid directory path is returned as-is."""
        # Create a subdirectory to ensure dirs is non-empty
        subdir = tmp_path / "alpha"
        subdir.mkdir()
        resp = client.get("/api/fs/browse", params={"path": str(tmp_path)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["path"] == str(tmp_path)
        names = [e["name"] for e in data["dirs"]]
        assert "alpha" in names

    def test_browse_with_valid_path_returns_correct_parent(self, tmp_path):
        """Parent field should be the parent directory of the given path."""
        from pathlib import Path
        resp = client.get("/api/fs/browse", params={"path": str(tmp_path)})
        data = resp.json()
        assert data["parent"] == str(Path(tmp_path).parent)

    def test_browse_with_invalid_nonexistent_path_clamps(self, tmp_path):
        """A nonexistent path that has a valid parent should clamp to parent."""
        nonexistent = tmp_path / "does_not_exist"
        resp = client.get("/api/fs/browse", params={"path": str(nonexistent)})
        assert resp.status_code == 200
        data = resp.json()
        # Should clamp to parent (tmp_path) since it exists as a directory
        assert data["path"] == str(tmp_path)

    def test_browse_hidden_dirs_excluded(self, tmp_path):
        """Hidden directories (starting with '.') must not appear in dirs."""
        (tmp_path / ".hidden").mkdir()
        (tmp_path / "visible").mkdir()
        resp = client.get("/api/fs/browse", params={"path": str(tmp_path)})
        names = [e["name"] for e in resp.json()["dirs"]]
        assert "visible" in names
        assert ".hidden" not in names


# ---------------------------------------------------------------------------
# POST /api/fs/mkdir
# ---------------------------------------------------------------------------

class TestFsMkdirEndpoint:
    def test_mkdir_creates_directory(self, tmp_path):
        new_dir = tmp_path / "new_subdir"
        resp = client.post("/api/fs/mkdir", json={"path": str(new_dir)})
        assert resp.status_code == 200
        assert new_dir.is_dir()

    def test_mkdir_returns_path(self, tmp_path):
        new_dir = tmp_path / "created"
        resp = client.post("/api/fs/mkdir", json={"path": str(new_dir)})
        data = resp.json()
        assert "path" in data
        assert data["path"] == str(new_dir)

    def test_mkdir_creates_nested_parents(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c"
        resp = client.post("/api/fs/mkdir", json={"path": str(deep)})
        assert resp.status_code == 200
        assert deep.is_dir()

    def test_mkdir_existing_dir_is_ok(self, tmp_path):
        """exist_ok=True means creating an existing dir should succeed."""
        resp = client.post("/api/fs/mkdir", json={"path": str(tmp_path)})
        assert resp.status_code == 200

    def test_mkdir_empty_path_returns_400(self):
        resp = client.post("/api/fs/mkdir", json={"path": ""})
        assert resp.status_code == 400

    def test_mkdir_missing_path_key_returns_400(self):
        """Body with no 'path' key resolves to empty string → 400."""
        resp = client.post("/api/fs/mkdir", json={})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# _render_package_json helper
# ---------------------------------------------------------------------------

class TestRenderPackageJson:
    def test_returns_valid_json(self):
        import json
        from subgraph_wizard.server import _render_package_json
        result = _render_package_json("my-subgraph")
        # Should not raise
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_contains_required_keys(self):
        import json
        from subgraph_wizard.server import _render_package_json
        parsed = json.loads(_render_package_json("my-subgraph"))
        assert "name" in parsed
        assert "version" in parsed
        assert "scripts" in parsed
        assert "dependencies" in parsed

    def test_name_is_slugified(self):
        import json
        from subgraph_wizard.server import _render_package_json
        parsed = json.loads(_render_package_json("My Subgraph"))
        assert parsed["name"] == "my-subgraph"

    def test_scripts_contain_deploy(self):
        import json
        from subgraph_wizard.server import _render_package_json
        parsed = json.loads(_render_package_json("curve-finance"))
        assert "deploy" in parsed["scripts"]
        assert "curve-finance" in parsed["scripts"]["deploy"]

    def test_dependencies_include_graph_cli(self):
        import json
        from subgraph_wizard.server import _render_package_json
        parsed = json.loads(_render_package_json("test"))
        assert "@graphprotocol/graph-cli" in parsed["dependencies"]
        assert "@graphprotocol/graph-ts" in parsed["dependencies"]


# ---------------------------------------------------------------------------
# _render_howto_md helper
# ---------------------------------------------------------------------------

class TestRenderHowtoMd:
    def test_returns_nonempty_string(self):
        from subgraph_wizard.server import _render_howto_md
        result = _render_howto_md("my-subgraph", "/tmp/output")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_subgraph_name(self):
        from subgraph_wizard.server import _render_howto_md
        result = _render_howto_md("curve-finance", "/tmp/output")
        assert "curve-finance" in result

    def test_contains_output_dir(self):
        from subgraph_wizard.server import _render_howto_md
        result = _render_howto_md("test", "/my/output/path")
        assert "/my/output/path" in result

    def test_contains_install_nodejs_section(self):
        from subgraph_wizard.server import _render_howto_md
        result = _render_howto_md("test", "/tmp")
        assert "Node.js" in result

    def test_contains_deploy_section(self):
        from subgraph_wizard.server import _render_howto_md
        result = _render_howto_md("test", "/tmp")
        assert "Deploy" in result or "deploy" in result

    def test_contains_graph_cli_install(self):
        from subgraph_wizard.server import _render_howto_md
        result = _render_howto_md("test", "/tmp")
        assert "graph-cli" in result

    def test_slug_used_in_deploy_command(self):
        from subgraph_wizard.server import _render_howto_md
        result = _render_howto_md("My Subgraph", "/tmp")
        # slug is lowercased and spaces replaced with dashes
        assert "my-subgraph" in result


# ---------------------------------------------------------------------------
# render_visual_subgraph_yaml — address / startBlock in output
# ---------------------------------------------------------------------------

class TestRenderVisualSubgraphYaml:
    def _config(self, address="0xABC", start_block=12345, network="mainnet"):
        return {
            "subgraph_name": "test-sub",
            "nodes": [
                {
                    "id": "c1",
                    "type": "contract",
                    "data": {
                        "name": "MyToken",
                        "address": address,
                        "startBlock": start_block,
                        "network": network,
                        "events": [
                            {"name": "Transfer", "signature": "Transfer(address,address,uint256)", "params": []}
                        ],
                        "instances": [],
                    },
                }
            ],
            "edges": [],
            "networks": [],
        }

    def test_startBlock_is_integer_in_yaml(self):
        import yaml
        from subgraph_wizard.generate.subgraph_yaml import render_visual_subgraph_yaml
        result = render_visual_subgraph_yaml(self._config())
        parsed = yaml.safe_load(result)
        sb = parsed["dataSources"][0]["source"]["startBlock"]
        assert isinstance(sb, int), f"Expected int, got {type(sb)}: {sb!r}"
        assert sb == 12345

    def test_address_in_yaml(self):
        import yaml
        from subgraph_wizard.generate.subgraph_yaml import render_visual_subgraph_yaml
        result = render_visual_subgraph_yaml(self._config(address="0xDEADBEEF"))
        parsed = yaml.safe_load(result)
        assert parsed["dataSources"][0]["source"]["address"] == "0xDEADBEEF"

    def test_network_per_contract(self):
        import yaml
        from subgraph_wizard.generate.subgraph_yaml import render_visual_subgraph_yaml
        result = render_visual_subgraph_yaml(self._config(network="arbitrum-one"))
        parsed = yaml.safe_load(result)
        assert parsed["dataSources"][0]["network"] == "arbitrum-one"

    def test_zero_startBlock_when_unset(self):
        import yaml
        from subgraph_wizard.generate.subgraph_yaml import render_visual_subgraph_yaml
        result = render_visual_subgraph_yaml(self._config(start_block=0))
        parsed = yaml.safe_load(result)
        assert parsed["dataSources"][0]["source"]["startBlock"] == 0

    def test_no_mustache_placeholders_in_output(self):
        from subgraph_wizard.generate.subgraph_yaml import render_visual_subgraph_yaml
        result = render_visual_subgraph_yaml(self._config())
        assert "{{" not in result, "mustache placeholder leaked into YAML"
