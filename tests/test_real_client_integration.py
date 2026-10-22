import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import real_client_integration as client


class RealClientIntegrationTest(unittest.TestCase):
    def test_accepts_fresh_supported_console_runner(self):
        with self.guard_environment():
            result = client._guard(self.manifest)
        self.assertEqual(result, {
            "macos": "26.1", "build": "25G83", "architecture": "arm64",
            "console_uid": 501,
        })

    def test_refuses_local_or_self_hosted_execution(self):
        for environment in ({}, {**self.environment, "RUNNER_ENVIRONMENT": "self-hosted"}):
            with self.subTest(environment=environment), patch.dict(
                client.os.environ, environment, clear=True
            ), self.assertRaisesRegex(RuntimeError, "GitHub-hosted"):
                client._guard(self.manifest)

    def test_refuses_existing_installation(self):
        with self.guard_environment(), patch.object(Path, "exists", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "existing"):
                client._guard(self.manifest)

    def test_refuses_unsupported_os_or_architecture(self):
        for version, architecture in (("14.8", "arm64"), ("26.1", "unknown")):
            with self.subTest(version=version, architecture=architecture):
                with self.guard_environment(version, architecture):
                    with self.assertRaisesRegex(RuntimeError, "Unsupported"):
                        client._guard(self.manifest)

    def test_rejects_changed_package_before_signature_check(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "client.pkg"
            package.write_bytes(b"changed")
            with patch.object(client, "_run") as command:
                with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                    client._verify_package(package, self.manifest)
            command.assert_not_called()

    def test_rejects_unexpected_signer(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "client.pkg"
            package.write_bytes(b"")
            manifest = {**self.manifest, "sha256": client.hashlib.sha256(b"").hexdigest()}
            with patch.object(client, "_run", return_value="Developer ID Installer: Other"):
                with self.assertRaisesRegex(RuntimeError, "signing identity"):
                    client._verify_package(package, manifest)

    def test_gatekeeper_failure_propagates(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "client.pkg"
            package.write_bytes(b"")
            manifest = {**self.manifest, "sha256": client.hashlib.sha256(b"").hexdigest()}
            with patch.object(client, "_run", side_effect=[
                "Developer ID Installer: Zscaler inc (PCBCQZJ7S7)",
                RuntimeError("spctl failed"),
            ]):
                with self.assertRaisesRegex(RuntimeError, "spctl failed"):
                    client._verify_package(package, manifest)

    def test_empty_inventory_cannot_be_ready(self):
        with self.assertRaisesRegex(RuntimeError, "agent and daemon"):
            client._require_baseline([], {})

    def test_installation_without_running_services_cannot_be_ready(self):
        inventory = [
            {"target": "system/com.zscaler.service", "run_at_load": True},
            {"target": "gui/501/com.zscaler.tray", "run_at_load": True},
        ]
        for running in ({}, {"system/com.zscaler.service": 42}):
            with self.subTest(running=running):
                with self.assertRaisesRegex(RuntimeError, "not running"):
                    result = client._require_baseline(inventory, running)
                    self.assertIsNone(result)

    def test_demand_started_tunnel_is_not_fabricated(self):
        inventory = [
            {"target": "system/com.zscaler.service", "run_at_load": True},
            {"target": "gui/501/com.zscaler.tray", "run_at_load": True},
            {"target": "system/com.zscaler.tunnel", "run_at_load": False},
        ]
        running = {"system/com.zscaler.service": 42, "gui/501/com.zscaler.tray": 43}
        client._require_baseline(inventory, running)

    def test_permission_error_is_not_absence(self):
        result = subprocess.CompletedProcess([], 1, "", "permission denied")
        with patch.object(client.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "launchctl"):
                client._running("system/com.zscaler.service")

    def test_parses_actual_launchd_pid(self):
        result = subprocess.CompletedProcess([], 0, "state = running\n\tpid = 123\n", "")
        with patch.object(client.subprocess, "run", return_value=result):
            pid = client._running("system/com.zscaler.service")
        self.assertEqual(pid, 123)

    def guard_environment(self, version="26.1", architecture="arm64"):
        from contextlib import ExitStack

        stack = ExitStack()
        stack.enter_context(patch.dict(client.os.environ, self.environment, clear=True))
        stack.enter_context(patch.object(client.platform, "system", return_value="Darwin"))
        stack.enter_context(patch.object(client.platform, "machine", return_value=architecture))
        stack.enter_context(patch.object(client.os, "getuid", return_value=501))
        stack.enter_context(patch.object(Path, "exists", return_value=False))
        stack.enter_context(patch.object(Path, "glob", return_value=[]))
        stack.enter_context(patch.object(client, "_run", side_effect=[
            version, "25G83", "501", "",
        ]))
        stack.enter_context(patch.object(client.subprocess, "run", return_value=
                                        subprocess.CompletedProcess([], 1, "", "")))
        return stack

    environment = {
        "GITHUB_ACTIONS": "true",
        "RUNNER_ENVIRONMENT": "github-hosted",
        "RUNNER_OS": "macOS",
    }
    manifest = {
        "sha256": "reviewed-digest",
        "team_id": "PCBCQZJ7S7",
        "supported_macos": [15, 26],
        "architectures": ["arm64", "x86_64"],
    }


if __name__ == "__main__":
    unittest.main()
