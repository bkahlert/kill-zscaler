import argparse
import hashlib
import json
import os
import platform
import plistlib
import subprocess
import tempfile
import time
from pathlib import Path

from observe_launchd import observe_absence


APP = Path("/Applications/Zscaler/Zscaler.app")


def _run(*command, timeout=30):
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"{command[0]} failed: status {result.returncode}")
    return result.stdout.strip()


def _guard(manifest):
    if (platform.system() != "Darwin"
            or os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted"
            or os.environ.get("RUNNER_OS") != "macOS"):
        raise RuntimeError("Requires disposable GitHub-hosted macOS")
    version = _run("sw_vers", "-productVersion")
    build = _run("sw_vers", "-buildVersion")
    architecture = platform.machine()
    if (int(version.split(".")[0]) not in manifest["supported_macos"]
            or architecture not in manifest["architectures"]):
        raise RuntimeError(f"Unsupported macOS/architecture: {version}/{architecture}")
    uid = int(_run("stat", "-f", "%u", "/dev/console"))
    if uid == 0 or uid != os.getuid():
        raise RuntimeError("Requires the ordinary logged-in console user")
    if (Path("/Applications/Zscaler").exists()
            or list(Path("/Library/LaunchDaemons").glob("com.zscaler.*"))
            or list(Path("/Library/LaunchAgents").glob("com.zscaler.*"))):
        raise RuntimeError("Refusing existing Zscaler installation")
    receipt = subprocess.run(
        ["pkgutil", "--pkg-info", "com.zscaler.zscaler"],
        capture_output=True, text=True, timeout=10,
    )
    if receipt.returncode == 0:
        raise RuntimeError("Refusing existing Zscaler package receipt")
    if receipt.returncode != 1:
        raise RuntimeError(f"Cannot inspect package receipt: status {receipt.returncode}")
    _run("launchctl", "print", f"gui/{uid}")
    return {"macos": version, "build": build, "architecture": architecture,
            "console_uid": uid}


def _verify_package(package, manifest):
    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    if digest != manifest["sha256"]:
        raise RuntimeError("Installer SHA-256 mismatch")
    signature = _run("pkgutil", "--check-signature", str(package))
    identity = f"Developer ID Installer: Zscaler inc ({manifest['team_id']})"
    if identity not in signature:
        raise RuntimeError("Unexpected installer signing identity")
    _run("spctl", "--assess", "--type", "install", "--verbose=2", str(package))
    return {"sha256": digest, "signing_identity": identity}


def _inventory(uid):
    inventory = []
    for directory, domain in (
        ("/Library/LaunchDaemons", "system"),
        ("/Library/LaunchAgents", f"gui/{uid}"),
    ):
        for path in sorted(Path(directory).glob("com.zscaler.*.plist")):
            with path.open("rb") as source:
                data = plistlib.load(source)
            label = data["Label"]
            if not isinstance(label, str) or not label.startswith("com.zscaler."):
                raise RuntimeError(f"Unexpected vendor service label in {path.name}")
            inventory.append({
                "target": f"{domain}/{label}",
                "run_at_load": bool(data.get("RunAtLoad", False)),
            })
    return inventory


def _service_state(target):
    result = subprocess.run(
        ["launchctl", "print", target], capture_output=True, text=True, timeout=10,
    )
    if result.returncode == 113:
        return {"loaded": False, "state": None, "pid": None, "last_exit_code": None}
    if result.returncode:
        raise RuntimeError(f"launchctl print {target}: status {result.returncode}")
    fields = dict(
        line.strip().split(" = ", 1) for line in result.stdout.splitlines()
        if line.startswith("\t") and not line.startswith("\t\t") and " = " in line
    )
    pid = fields.get("pid", "")
    return {
        "loaded": True,
        "state": fields.get("state"),
        "pid": int(pid) if pid.isdigit() else None,
        "last_exit_code": fields.get("last exit code"),
    }


def _running(target):
    state = _service_state(target)
    return state["pid"] if state["state"] == "running" else None


def _require_baseline(inventory, running):
    domains = {item["target"].split("/")[0] for item in inventory}
    if domains != {"system", "gui"}:
        raise RuntimeError("Readiness requires actual vendor agent and daemon inventory")
    required = {item["target"] for item in inventory if item["run_at_load"]}
    if not required or not running or not required.issubset(running):
        raise RuntimeError("Actual vendor RunAtLoad services are not running")
    if {target.split("/")[0] for target in running} != {"system", "gui"}:
        raise RuntimeError("Actual vendor agent and daemon are not running")


def _readiness(manifest, report):
    report["stage"] = "guard"
    report.update(_guard(manifest))
    report["stage"] = "download"
    with tempfile.TemporaryDirectory(prefix="zscaler-ci-") as directory:
        package = Path(directory) / "client.pkg"
        _run("curl", "--fail", "--location", "--silent", "--show-error",
             "--proto", "=https", "--proto-redir", "=https", "--max-time", "180",
             "--output", str(package), manifest["url"], timeout=200)
        report["stage"] = "package-trust"
        report["installer"] = _verify_package(package, manifest)
        report["stage"] = "installation"
        _run("sudo", "-n", "installer", "-pkg", str(package), "-target", "/",
             timeout=900)
    report["installed"] = True
    report["stage"] = "installed-app"
    with (APP / "Contents/Info.plist").open("rb") as source:
        version = plistlib.load(source)["CFBundleShortVersionString"]
    report["client_version"] = version
    if version != manifest["version"]:
        raise RuntimeError("Installed app version mismatch")
    _run("codesign", "--verify", "--deep", "--strict", str(APP))
    identity = subprocess.run(
        ["codesign", "-dv", "--verbose=4", str(APP)],
        capture_output=True, text=True, timeout=30,
    )
    if (identity.returncode
            or f"TeamIdentifier={manifest['team_id']}" not in identity.stderr.splitlines()):
        raise RuntimeError("Installed app signing identity mismatch")
    _run("open", str(APP))
    report["stage"] = "running-baseline"
    inventory = _inventory(report["console_uid"])
    report["discovered_services"] = inventory
    deadline = time.monotonic() + 120
    while True:
        _run("launchctl", "print", "system")
        _run("launchctl", "print", f"gui/{report['console_uid']}")
        states = {item["target"]: _service_state(item["target"]) for item in inventory}
        running = {
            target: state["pid"] for target, state in states.items()
            if state["state"] == "running" and state["pid"] is not None
        }
        report["service_states"] = states
        report["running_services"] = running
        if time.monotonic() >= deadline:
            break
        try:
            _require_baseline(inventory, running)
        except RuntimeError:
            time.sleep(5)
        else:
            break
    report["extension_state"] = [
        line.strip() for line in _run("systemextensionsctl", "list").splitlines()
        if manifest["team_id"] in line
    ]
    report["enrollment"] = "No tenant or enrollment supplied; network function unverified"
    _require_baseline(inventory, running)
    report["stage"] = "readiness"
    report["ready"] = True


def _process_identity(pid):
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "lstart=,comm="],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode == 1:
        return None
    if result.returncode:
        raise RuntimeError(f"Cannot inspect process {pid}: status {result.returncode}")
    return result.stdout.strip()


def _wait_dead(identities):
    deadline = time.monotonic() + 30
    while True:
        surviving = [
            pid for pid, identity in identities.items()
            if _process_identity(pid) == identity
        ]
        if not surviving:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Original vendor processes still running: {surviving}")
        time.sleep(1)


def _assert_control(target, pid):
    if _running(target) != pid:
        raise RuntimeError(f"Unrelated service changed: {target}")


def _check_app(running, uid):
    pid = running[f"gui/{uid}/com.zscaler.tray"]
    process = _run("ps", "-p", str(pid), "-o", "uid=,comm=").split(maxsplit=1)
    executable = str(APP / "Contents/MacOS/Zscaler")
    if process != [str(uid), executable]:
        raise RuntimeError("Real app is not running as the console user")


def _wait_restored(targets):
    deadline = time.monotonic() + 120
    while True:
        running = {target: _running(target) for target in targets}
        if all(pid is not None for pid in running.values()):
            return running
        if time.monotonic() >= deadline:
            missing = [target for target, pid in running.items() if pid is None]
            raise RuntimeError(f"Vendor services not restored: {missing}")
        time.sleep(1)


def _lifecycle(report):
    report["lifecycle_passed"] = False
    report["stage"] = "lifecycle-baseline"
    running = report["running_services"]
    _check_app(running, report["console_uid"])
    control = "system/com.apple.logd"
    control_pid = _running(control)
    if control_pid is None:
        raise RuntimeError("Unrelated control service is not running")
    report["unrelated_control"] = {"target": control, "pid": control_pid}
    identities = {pid: _process_identity(pid) for pid in running.values()}
    if any(identity is None for identity in identities.values()):
        raise RuntimeError("Vendor baseline process disappeared before stop")
    repo = Path(__file__).resolve().parent.parent
    report["stage"] = "stop"
    _run("/bin/bash", str(repo / "kill-zscaler.sh"), timeout=60)
    _wait_dead(identities)
    report["original_processes_exited"] = True
    _run("/bin/bash", str(repo / "kill-zscaler.sh"), timeout=60)
    _assert_control(control, control_pid)
    report["stage"] = "stopped-observation"
    report["observation"] = observe_absence(
        [item["target"] for item in report["discovered_services"]], 600, 5,
    )
    _assert_control(control, control_pid)
    report["stage"] = "restoration"
    _run("/bin/bash", str(repo / "start-zscaler.sh"), timeout=60)
    restored = _wait_restored(running)
    for item in report["discovered_services"]:
        _run("launchctl", "print", item["target"])
    _check_app(restored, report["console_uid"])
    _assert_control(control, control_pid)
    _run("/bin/bash", str(repo / "start-zscaler.sh"), timeout=60)
    repeated = _wait_restored(running)
    if repeated != restored:
        raise RuntimeError("Repeated start changed vendor service processes")
    _check_app(repeated, report["console_uid"])
    _assert_control(control, control_pid)
    report["restored_services"] = restored
    report["extension_state_after"] = [
        line.strip() for line in _run("systemextensionsctl", "list").splitlines()
        if "PCBCQZJ7S7" in line
    ]
    report["stage"] = "lifecycle"
    report["lifecycle_passed"] = True


def main():
    parser = argparse.ArgumentParser(
        description="Install and inspect a pinned real client on disposable macOS CI only."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--stage", choices=("readiness", "lifecycle"), default="readiness")
    args = parser.parse_args()
    report = {"ready": False}
    try:
        manifest = json.loads(args.manifest.read_text())
        _readiness(manifest, report)
        if args.stage == "lifecycle":
            _lifecycle(report)
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        report["error"] = str(error)
        return_code = 1
    else:
        return_code = 0
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
