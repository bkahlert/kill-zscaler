import math
import subprocess
import unittest
from unittest.mock import patch

import observe_launchd


class LaunchdObservationTest(unittest.TestCase):
    def test_absence_is_observed_through_the_full_window(self):
        result = observe_launchd.observe_absence(self.targets, 600, 5)
        self.assertEqual(result["targets"], self.targets)
        self.assertEqual(result["requested_seconds"], 600)
        self.assertGreaterEqual(result["observed_seconds"], 600)
        self.assertEqual(result["samples"], 121)
        self.assertEqual(self.probes[-2:], [
            (600, "gui/502/org.example.agent"),
            (600, "system/org.example.daemon"),
        ])

    def test_loaded_target_fails_even_without_a_pid(self):
        self.returning_at = 0
        with self.assertRaisesRegex(RuntimeError, r"system/org.example.daemon.*0"):
            observe_launchd.observe_absence(self.targets, 600, 5)

    def test_delayed_restart_fails(self):
        self.returning_at = 595
        with self.assertRaisesRegex(RuntimeError, r"system/org.example.daemon.*595"):
            observe_launchd.observe_absence(self.targets, 600, 5)

    def test_reappearance_at_final_boundary_fails(self):
        self.returning_at = 600
        with self.assertRaisesRegex(RuntimeError, r"system/org.example.daemon.*600"):
            observe_launchd.observe_absence(self.targets, 600, 5)

    def test_permission_error_is_not_absence(self):
        self.service_status = 1
        with self.assertRaisesRegex(RuntimeError, "denied"):
            observe_launchd.observe_absence(self.targets, 600, 5)

    def test_missing_domain_is_not_absence(self):
        self.missing_domain = "gui/502"
        with self.assertRaisesRegex(RuntimeError, "gui/502"):
            observe_launchd.observe_absence(self.targets, 600, 5)

    def test_domain_disappearing_during_observation_fails(self):
        self.missing_domain = "gui/502"
        self.domain_missing_at = 595
        with self.assertRaisesRegex(RuntimeError, "gui/502"):
            observe_launchd.observe_absence(self.targets, 600, 5)

    def test_invalid_observations_are_rejected(self):
        for targets, duration, interval in (
            ([], 600, 5), (["system"], 600, 5),
            (["gui/502"], 600, 5), (["system/"], 600, 5),
            (self.targets, 0, 5), (self.targets, -1, 5),
            (self.targets, 600, 0), (self.targets, 600, -1),
            (self.targets, math.inf, 5), (self.targets, math.nan, 5),
            (self.targets, 600, math.inf), (self.targets, 600, math.nan),
        ):
            with self.subTest(targets=targets, duration=duration, interval=interval):
                with self.assertRaises(ValueError):
                    observe_launchd.observe_absence(targets, duration, interval)

    def test_short_final_interval_still_probes_the_boundary(self):
        result = observe_launchd.observe_absence(self.targets, 12, 5)
        self.assertEqual(result["observed_seconds"], 12)
        self.assertEqual(result["samples"], 4)
        self.assertEqual(self.probes[-1][0], 12)

    def setUp(self):
        self.targets = ["gui/502/org.example.agent", "system/org.example.daemon"]
        self.now = 0
        self.returning_at = math.inf
        self.service_status = 113
        self.missing_domain = None
        self.domain_missing_at = 0
        self.probes = []
        for name, replacement in (
            ("time.monotonic", lambda: self.now),
            ("time.sleep", self.advance),
            ("subprocess.run", self.run_command),
        ):
            patcher = patch(f"observe_launchd.{name}", side_effect=replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def advance(self, seconds):
        self.now += seconds

    def run_command(self, command, **_kwargs):
        self.assertEqual(command[:2], ["launchctl", "print"])
        target = command[2]
        if target in ("system", "gui/502"):
            status = (113 if target == self.missing_domain
                      and self.now >= self.domain_missing_at else 0)
        else:
            self.assertIn(target, self.targets)
            self.probes.append((self.now, target))
            status = (0 if target == "system/org.example.daemon"
                      and self.now >= self.returning_at else self.service_status)
        return subprocess.CompletedProcess(
            command, status, stdout="", stderr="denied" if status == 1 else ""
        )


if __name__ == "__main__":
    unittest.main()
