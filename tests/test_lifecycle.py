import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LifecycleTest(unittest.TestCase):
    def test_stop_removes_agents_and_daemons_from_their_domains(self):
        result = self.run_script("kill-zscaler.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state(), [])
        self.assertIn(
            ["launchctl", "bootout", "system/org.example.daemon"], self.calls()
        )
        self.assertIn(
            ["launchctl", "bootout", "gui/502/org.example.agent"], self.calls()
        )

    def test_start_restores_both_domains_and_opens_as_console_user(self):
        self.write_state([])
        result = self.run_script("start-zscaler.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            sorted(self.state()),
            ["gui/502/org.example.agent", "system/org.example.daemon"],
        )
        self.assertIn(
            ["launchctl", "asuser", "502", "sudo", "-u", "#502",
             "open", "-a", "/Applications/Zscaler/Zscaler.app", "--hide"],
            self.calls(),
        )

    def test_repeated_stop_and_start_are_successful(self):
        for script in ("kill-zscaler.sh", "kill-zscaler.sh",
                       "start-zscaler.sh", "start-zscaler.sh"):
            result = self.run_script(script)
            self.assertEqual(result.returncode, 0, result.stderr)
        mutations = [call for call in self.calls()
                     if call[:2] in (["launchctl", "bootout"],
                                     ["launchctl", "bootstrap"])]
        self.assertEqual(len(mutations), 4)

    def test_non_root_invocation_elevates_the_quoted_script(self):
        self.env["FAKE_UID"] = "502"
        result = self.run_script("kill-zscaler.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state(), [])
        self.assertIn(
            ["sudo", "/bin/bash", str(self.repo / "kill-zscaler.sh")],
            self.calls(),
        )

    def test_no_console_session_fails_before_mutating_services(self):
        self.env["FAKE_CONSOLE_UID"] = "0"
        result = self.run_script("kill-zscaler.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("console", result.stderr.lower())
        self.assertEqual(len(self.state()), 2)

    def test_missing_gui_domain_fails_before_mutating_services(self):
        self.env["FAKE_GUI_MISSING"] = "1"
        result = self.run_script("kill-zscaler.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.state()), 2)

    def test_missing_services_are_not_confused_with_permission_errors(self):
        self.env["FAKE_FAIL"] = "print-service"
        result = self.run_script("kill-zscaler.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("denied", result.stderr)
        self.assertEqual(len(self.state()), 2)

    def test_command_failures_are_reported(self):
        for failure in ("bootout", "bootstrap", "find", "plutil", "open", "stat"):
            with self.subTest(failure=failure):
                self.write_state([] if failure == "bootstrap" else [
                    "system/org.example.daemon", "gui/502/org.example.agent"
                ])
                self.env["FAKE_FAIL"] = failure
                script = ("start-zscaler.sh" if failure in ("bootstrap", "open")
                          else "kill-zscaler.sh")
                result = self.run_script(script)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("denied", result.stderr)

    def test_denied_elevation_does_not_change_services(self):
        self.env.update(FAKE_UID="502", FAKE_FAIL="sudo")
        result = self.run_script("kill-zscaler.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("denied", result.stderr)
        self.assertEqual(len(self.state()), 2)

    def test_failed_identity_lookup_does_not_retry_elevation(self):
        self.env["FAKE_FAIL"] = "id"
        result = self.run_script("kill-zscaler.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(call[0] == "sudo" for call in self.calls()))
        self.assertEqual(len(self.state()), 2)

    def test_malformed_plists_are_not_silently_skipped(self):
        for data in (b"not a plist", plistlib.dumps({}),
                     plistlib.dumps({"Label": 42})):
            with self.subTest(data=data):
                path = self.fixtures / "LaunchDaemons/com.zscaler test.plist"
                path.write_bytes(data)
                result = self.run_script("kill-zscaler.sh")
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(result.stderr)
                self.assertEqual(len(self.state()), 2)

    @unittest.skipUnless(sys.platform == "darwin", "plutil requires macOS")
    def test_real_plutil_reads_labels_from_paths_with_spaces(self):
        (self.temp / "bin/plutil").unlink()
        result = self.run_script("kill-zscaler.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state(), [])

    def test_invalid_label_is_rejected(self):
        self.make_plist("LaunchDaemons", "com.zscaler test.plist", "")
        result = self.run_script("kill-zscaler.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.state()), 2)

    def test_no_matches_does_not_bootout_an_entire_domain(self):
        for file in self.fixtures.rglob("*.plist"):
            file.unlink()
        result = self.run_script("kill-zscaler.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(call[:2] == ["launchctl", "bootout"]
                             for call in self.calls()))

    def test_unrelated_services_remain_loaded(self):
        self.write_state(self.state() + ["system/org.example.unrelated"])
        result = self.run_script("kill-zscaler.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state(), ["system/org.example.unrelated"])

    def test_help_and_invalid_arguments_do_not_change_services(self):
        for script in ("kill-zscaler.sh", "start-zscaler.sh"):
            for args, status in ((["--help"], 0), (["--unknown"], 2)):
                result = self.run_script(script, args)
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertEqual(len(self.state()), 2)

    def test_apps_delegate_from_a_path_with_spaces(self):
        for app, expected in (("Kill", []), ("Start", [
                "gui/502/org.example.agent", "system/org.example.daemon"])):
            result = self.run_script(
                f"{app} Zscaler.app/Contents/MacOS/main.command"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(sorted(self.state()), expected)
            if sys.platform == "darwin":
                result = subprocess.run(
                    ["osacompile", "-o", str(self.temp / "wrapper.scpt"),
                     str(self.temp / "applescript")],
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_app_authorization_failure_does_not_change_services(self):
        self.env["FAKE_FAIL"] = "osascript"
        result = self.run_script("Kill Zscaler.app/Contents/MacOS/main.command")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.state()), 2)

    def test_integration_refuses_execution_outside_disposable_ci(self):
        result = subprocess.run(
            ["/bin/bash", str(ROOT / "tests/launchd-integration")],
            env=dict(self.env, GITHUB_ACTIONS="false"),
            capture_output=True, text=True, timeout=5,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GitHub-hosted", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_aliases_work_outside_the_checkout(self):
        result = self.run_shell(
            f'ZSCALER_REPO="{self.repo}"\n'
            f'source "{self.repo / "kill-zscaler.alias.txt"}"\n'
            'cd /\nkill-zscaler\nstart-zscaler\n'
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.state()), 2)
        self.assertIn(
            ["launchctl", "bootout", "system/org.example.daemon"], self.calls()
        )

    @unittest.skipUnless(sys.platform == "darwin", "System Zsh requires macOS")
    def test_shell_functions_work_in_zsh(self):
        result = subprocess.run(
            ["/bin/zsh", "-f", "-c",
             'set -e; source "$ZSCALER_REPO/kill-zscaler.alias.txt"; '
             "kill-zscaler; start-zscaler"],
            env=dict(self.env, ZSCALER_REPO=str(self.repo)),
            cwd=self.temp, text=True, capture_output=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.state()), 2)
        self.assertIn(
            ["launchctl", "bootout", "gui/502/org.example.agent"], self.calls()
        )

    def test_documented_lifecycle_commands_execute(self):
        readme = (self.repo / "README.md").read_text()
        lifecycle = readme.split("## Verification and troubleshooting")[0]
        blocks = re.findall(
            r"```(?:shell|bash|sh)\n(?P<code>.*?)```", lifecycle, re.DOTALL
        )
        self.assertTrue(blocks, "No executable lifecycle documentation found")
        for block in blocks:
            for state in ([], ["system/org.example.daemon",
                               "gui/502/org.example.agent"]):
                with self.subTest(block=block, state=state):
                    self.write_state(state)
                    result = self.run_shell(block)
                    self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            ["launchctl", "bootout", "system/org.example.daemon"], self.calls()
        )
        self.assertIn(
            ["launchctl", "bootstrap", "gui/502", str(self.agent)], self.calls()
        )

    def test_all_documented_shell_blocks_parse(self):
        readme = (self.repo / "README.md").read_text()
        blocks = re.findall(
            r"(?m)^[ \t]*```(?:shell|bash|sh)\n(?P<code>.*?)^[ \t]*```",
            readme, re.DOTALL,
        )
        for block in blocks:
            block = textwrap.dedent(block)
            result = subprocess.run(
                ["/bin/bash", "-n"], input=block, text=True, capture_output=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="zscaler's tests ")
        self.addCleanup(self.directory.cleanup)
        self.temp = Path(self.directory.name)
        self.repo = self.temp / "checkout with spaces"
        self.repo.mkdir()
        for name in ("kill-zscaler.sh", "start-zscaler.sh", "zscaler.bash",
                     "kill-zscaler.alias.txt", "README.md",
                     "Kill Zscaler.app", "Start Zscaler.app"):
            source = ROOT / name
            if source.is_dir():
                shutil.copytree(source, self.repo / name)
            elif source.exists():
                shutil.copy2(source, self.repo / name)
        self.fixtures = self.temp / "Library"
        self.agent = self.make_plist(
            "LaunchAgents", "com.Zscaler agent.plist", "org.example.agent"
        )
        self.make_plist(
            "LaunchDaemons", "com.zscaler test.plist", "org.example.daemon"
        )
        self.make_plist("LaunchDaemons", "unrelated.plist", "org.example.unrelated")
        bin_dir = self.temp / "bin"
        bin_dir.mkdir()
        for name in ("id", "stat", "find", "launchctl", "sudo", "open",
                     "plutil", "osascript"):
            (bin_dir / name).symlink_to(ROOT / "tests/fixtures/command")
        self.env = dict(
            os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}",
            FIXTURE_ROOT=str(self.temp), FAKE_UID="0",
        )
        (self.temp / "calls.jsonl").touch()
        for name in ("FAKE_FAIL", "FAKE_GUI_MISSING", "FAKE_CONSOLE_UID",
                     "BASH_ENV", "ENV"):
            self.env.pop(name, None)
        self.write_state([
            "system/org.example.daemon", "gui/502/org.example.agent"
        ])

    def make_plist(self, domain, filename, label):
        path = self.fixtures / domain / filename
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_bytes(plistlib.dumps({"Label": label}))
        return path

    def run_script(self, script, args=()):
        return subprocess.run(
            ["/bin/bash", str(self.repo / script), *args],
            env=self.env, cwd=self.temp, text=True, capture_output=True, timeout=15,
        )

    def run_shell(self, code):
        return subprocess.run(
            ["/bin/bash", "-e", "-O", "expand_aliases"], input=code, env=self.env,
            cwd=self.repo, text=True, capture_output=True,
        )

    def write_state(self, state):
        (self.temp / "state.json").write_text(json.dumps(state))

    def state(self):
        return json.loads((self.temp / "state.json").read_text())

    def calls(self):
        return [json.loads(line) for line in
                (self.temp / "calls.jsonl").read_text().splitlines()]


if __name__ == "__main__":
    unittest.main()
