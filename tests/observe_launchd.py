import argparse
import json
import math
import subprocess
import time


def observe_absence(targets: list[str], duration: float, interval: float) -> dict:
    if not targets:
        raise ValueError("At least one launchd service target is required")
    domains = set()
    for target in targets:
        parts = target.split("/")
        if len(parts) == 2 and parts[0] == "system" and parts[1]:
            domains.add("system")
        elif (len(parts) == 3 and parts[0] == "gui"
              and parts[1].isdigit() and parts[2]):
            domains.add(f"gui/{parts[1]}")
        else:
            raise ValueError(f"Invalid launchd service target: {target}")
    if not all(math.isfinite(value) and value > 0
               for value in (duration, interval)):
        raise ValueError("Observation duration and interval must be finite and positive")

    started = time.monotonic()
    samples = 0
    while True:
        sampled_at = time.monotonic()
        for domain in sorted(domains):
            result = subprocess.run(
                ["launchctl", "print", domain], capture_output=True,
                text=True, timeout=10,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"Cannot inspect domain {domain} at "
                    f"{time.monotonic() - started:.3f}s: "
                    f"status {result.returncode}: {result.stderr.strip()}"
                )
        for target in targets:
            result = subprocess.run(
                ["launchctl", "print", target], capture_output=True,
                text=True, timeout=10,
            )
            elapsed = time.monotonic() - started
            if result.returncode == 0:
                raise RuntimeError(f"Service reappeared: {target} at {elapsed:.3f}s")
            if result.returncode != 113:
                raise RuntimeError(
                    f"Cannot inspect {target} at {elapsed:.3f}s: "
                    f"status {result.returncode}: {result.stderr.strip()}"
                )
        samples += 1
        if sampled_at - started >= duration:
            return {
                "targets": targets,
                "requested_seconds": duration,
                "observed_seconds": time.monotonic() - started,
                "samples": samples,
            }
        remaining = duration - (time.monotonic() - started)
        if remaining > 0:
            time.sleep(min(interval, remaining))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fail if a launchd service returns during a bounded observation."
    )
    parser.add_argument("--target", action="append", required=True)
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--interval", type=float, required=True)
    args = parser.parse_args()
    try:
        observation = observe_absence(args.target, args.seconds, args.interval)
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"Observation failed: {error}\n")
    else:
        print(json.dumps(observation, sort_keys=True), flush=True)
