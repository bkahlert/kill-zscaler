import plistlib
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
                    client._require_baseline(inventory, running)

    def test_demand_started_tunnel_is_not_fabricated(self):
        inventory = [
            {"target": "system/com.zscaler.service", "run_at_load": True},
            {"target": "gui/501/com.zscaler.tray", "run_at_load": True},
            {"target": "system/com.zscaler.tunnel", "run_at_load": False},
        ]
        running = {"system/com.zscaler.service": 42, "gui/501/com.zscaler.tray": 43}
        result = client._require_baseline(inventory, running)
        self.assertIsNone(result)

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

    def test_service_diagnostics_exclude_raw_launchd_configuration(self):
        result = subprocess.CompletedProcess([], 0,
                                             "state = waiting\nlast exit code = 78\n"
                                             "private-setting = confidential\n", "")
        with patch.object(client.subprocess, "run", return_value=result):
            state = client._service_state("system/com.zscaler.service")
        self.assertEqual(state, {
            "loaded": True, "state": "waiting", "pid": None, "last_exit_code": "78",
        })

    def test_discovers_vendor_labels_in_their_actual_domains(self):
        with tempfile.TemporaryDirectory() as directory:
            daemon = Path(directory) / "daemon.plist"
            agent = Path(directory) / "agent.plist"
            daemon.write_bytes(plistlib.dumps({
                "Label": "com.zscaler.service", "RunAtLoad": True,
            }))
            agent.write_bytes(plistlib.dumps({
                "Label": "com.zscaler.tray", "RunAtLoad": True,
            }))
            with patch.object(Path, "glob", side_effect=[[daemon], [agent]]):
                result = client._inventory(501)
        self.assertEqual(result, [
            {"target": "system/com.zscaler.service", "run_at_load": True},
            {"target": "gui/501/com.zscaler.tray", "run_at_load": True},
        ])

    def test_refuses_non_vendor_service_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            plist = Path(directory) / "vendor.plist"
            plist.write_bytes(plistlib.dumps({"Label": "com.apple.unrelated"}))
            with patch.object(Path, "glob", return_value=[plist]):
                with self.assertRaisesRegex(RuntimeError, "Unexpected vendor service"):
                    client._inventory(501)

    def test_actual_client_lifecycle_requires_stop_observation_and_restore(self):
        report = self.lifecycle_report()
        commands = self.run_lifecycle(report)
        self.assertTrue(report["lifecycle_passed"])
        self.assertGreaterEqual(report["observation"]["observed_seconds"], 600)
        self.assertEqual(commands.stops, 2)
        self.assertEqual(commands.starts, 2)

    def test_lifecycle_rejects_late_vendor_reappearance(self):
        with self.assertRaisesRegex(RuntimeError, "reappeared"):
            self.run_lifecycle(self.lifecycle_report(), late_restart=True)

    def test_lifecycle_rejects_surviving_original_process(self):
        with self.assertRaisesRegex(RuntimeError, "still running"):
            self.run_lifecycle(self.lifecycle_report(), surviving_process=True)

    def test_lifecycle_rejects_partial_restoration(self):
        with self.assertRaisesRegex(RuntimeError, "not restored"):
            self.run_lifecycle(self.lifecycle_report(), partial_restore=True)

    def test_lifecycle_rejects_unrelated_service_changes(self):
        with self.assertRaisesRegex(RuntimeError, "Unrelated"):
            self.run_lifecycle(self.lifecycle_report(), control_changed=True)

    def test_lifecycle_rejects_app_outside_console_user(self):
        with self.assertRaisesRegex(RuntimeError, "console user"):
            self.run_lifecycle(self.lifecycle_report(), wrong_app_user=True)

    def test_lifecycle_propagates_public_entry_point_failure(self):
        with self.assertRaisesRegex(RuntimeError, "/bin/bash failed"):
            self.run_lifecycle(self.lifecycle_report(), stop_failed=True)

    @staticmethod
    def run_lifecycle(report, **failures):
        commands = _ClientCommands(**failures)
        with patch.object(client.subprocess, "run", side_effect=commands.run), \
                patch.object(client.time, "monotonic", side_effect=lambda: commands.now), \
                patch.object(client.time, "sleep", side_effect=commands.sleep):
            client._lifecycle(report)
        return commands

    @staticmethod
    def lifecycle_report():
        return {
            "ready": True,
            "console_uid": 501,
            "running_services": {
                "system/com.zscaler.service": 10,
                "gui/501/com.zscaler.tray": 20,
            },
            "discovered_services": [
                {"target": "system/com.zscaler.service", "run_at_load": True},
                {"target": "gui/501/com.zscaler.tray", "run_at_load": True},
            ],
        }

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


class _ClientCommands:
    def __init__(self, **failures):
        self.failures = failures
        self.now = 0
        self.stops = 0
        self.starts = 0
        self.stopped = False

    def sleep(self, seconds):
        self.now += seconds

    def run(self, command, **_kwargs):
        command = list(command)
        output = ""
        status = 0
        if command[0] == "/bin/bash":
            if Path(command[1]).name == "kill-zscaler.sh":
                self.stops += 1
                self.stopped = True
                if self.failures.get("stop_failed"):
                    status = 1
            else:
                self.starts += 1
                self.stopped = False
        elif command[:2] == ["launchctl", "print"]:
            target = command[2]
            if target in ("system", "gui/501"):
                pass
            elif target == "system/com.apple.logd":
                pid = 100 if self.stops and self.failures.get("control_changed") else 99
                output = f"state = running\npid = {pid}"
            elif self.stopped:
                if self.now >= 595 and self.failures.get("late_restart"):
                    output = "state = running\npid = 1010"
                else:
                    status = 113
            elif self.starts and self.failures.get("partial_restore"):
                status = 113
            else:
                pid = 20 if target.startswith("gui/") else 10
                output = f"state = running\npid = {pid + (1000 if self.starts else 0)}"
        elif command[0] == "ps":
            pid = int(command[2])
            if command[-1] == "lstart=,comm=":
                if self.stops and not self.failures.get("surviving_process"):
                    status = 1
                else:
                    output = f"Thu Oct 22 06:00:00 2026 vendor-process-{pid}"
            else:
                uid = 0 if self.failures.get("wrong_app_user") else 501
                output = f"{uid} /Applications/Zscaler/Zscaler.app/Contents/MacOS/Zscaler"
        elif command[0] == "systemextensionsctl":
            output = "0 extension(s)"
        else:
            raise AssertionError(f"Unexpected command: {command}")
        return subprocess.CompletedProcess(command, status, output, "")


if __name__ == "__main__":
    unittest.main()
