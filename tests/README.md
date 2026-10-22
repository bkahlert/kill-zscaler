# Lifecycle evidence

Run the safe local suite from the repository root:

```shell
python3 -m unittest discover -s tests -p 'test_*.py' -v
bash tests/share-zscaler-download-test.sh
```

These commands do not install Zscaler or change local services.
The observer's fast tests use command and clock doubles, including a service
returning at 595 seconds and at the final 600-second boundary.
They also reject permission errors, unavailable domains, and invalid inputs.

## Completed evidence

| Environment                                      | Completed result                           | Boundary                                     |
|--------------------------------------------------|--------------------------------------------|----------------------------------------------|
| Sonoma 14.8.9 (23J631)                           | [600.174 seconds][fixture-run]             | Fixtures, not exact 14.0/14.6 or Zscaler     |
| macOS 15.7.9 (24G830)                            | [600.135 seconds][fixture-run]             | Fixtures, not a proprietary client           |
| macOS 26.6.2 (25G83)                             | [600.180 seconds][fixture-run]             | Fixtures, not a proprietary client           |
| Zscaler 4.8.0.281 / macOS 15.7.9 (24G830), arm64 | [600.177 seconds, restored][client-15-job] | Unenrolled service/tray; no active extension |
| Zscaler 4.8.0.281 / macOS 26.6.2 (25G83), arm64  | [600.195 seconds, restored][client-26-job] | Unenrolled service/tray; no active extension |
| Enrolled/MDM-controlled Zscaler                  | Not verified                               | Requires authorized tenant and policy        |

[fixture-run]: https://github.com/bkahlert/kill-zscaler/actions/runs/39735802284
[client-15-job]: https://github.com/bkahlert/kill-zscaler/actions/runs/39738487884/job/119689739282
[client-26-job]: https://github.com/bkahlert/kill-zscaler/actions/runs/39738487884/job/119689739125

The linked fixture jobs passed stop, sustained absence, restoration,
repeated operations, unrelated-service preservation, and console-user app open.
The three-OS fixture run at `76d5a6c` completed successfully.

The actual-client run at `a779891` also completed successfully on both current
macOS versions. It verified the pinned installer and real running service/tray,
old-process exit, ten minutes of sampled absence, restoration, repeated
stop/start, console-user tray ownership, and an unchanged unrelated `logd` PID.
All three discovered launchd targets were absent during observation.
The demand-started tunnel was not running before stop and was loaded on restore.
Neither runner had a supplied tenant or an active system extension before or
after the lifecycle. This does not establish enrolled VPN/network function.
The same run passed 55 regression tests (Ubuntu skips two macOS-only cases).

Earlier Tahoe readiness failures were harness false negatives: nested
resource-coalition state overwrote the direct service state.
The corrected parser reads only direct service fields, with a regression test.

A fixture is not an installed Zscaler client. A signed installer, installation
exit status, or launched app alone would not prove client readiness or lifecycle.

## Sustained fixture observation

The [workflow](../.github/workflows/test.yml) runs
[`launchd-integration`](launchd-integration) only on disposable GitHub-hosted
macOS runners. It refuses local execution and an existing Zscaler installation.
Its harmless KeepAlive agent and daemon use unique labels.
The test proves KeepAlive respawn before stopping, checks the old processes
exit, repeats stop, observes absent launchd targets for at least 600 seconds,
then restores both services and opens a stand-in app under the console user.
An unrelated service must retain its PID.

[`observe_launchd.py`](observe_launchd.py) checks each domain and service
every five seconds, including a final sample after the observation deadline.
Only launchctl status 113 in an available domain counts as service absence.
An observed reappearance, permission error, missing domain, or command timeout
fails rather than becoming a successful skip.
The successful JSON reports targets, requested and observed seconds, and samples.
Polling cannot detect every between-sample restart or prove indefinite absence.

The `sonoma` workflow-dispatch input adds `macos-14` while GitHub still provides
it. [Runner retirement](https://github.com/actions/runner-images/issues/13518)
is scheduled for November 2, 2026, with brownouts beforehand.
A completed run must record its exact macOS version and build.
Neither a newer runner nor a different Sonoma patch release certifies 14.0/14.6.

## Real-client prerequisites

Real-client testing is restricted to disposable CI, never the maintainer's Mac.
The manually dispatched `real_client` input of the [workflow](../.github/workflows/test.yml)
installs only the reviewed, pinned package on fresh macOS 15/26 runners,
then runs the actual-client lifecycle after readiness succeeds.
The [manifest](fixtures/zscaler-client.json) records its version, SHA-256,
vendor signing identity, architectures, and selected test OS versions.
No placeholder tenant, arbitrary "latest" URL, or fixture fallback is acceptable.

Without enrollment, the actual client must still expose a nonempty, running
vendor-service baseline. An enrollment or system-extension approval requirement
is a readiness blocker, not a green integration result.
Only after readiness can the same observer meaningfully check stop, sustained
absence, repeated operations, and restoration of actual services.
Extensions and enrolled policy remain separate evidence, not inferred from
launchd service status.

### Reviewed installer (October 22, 2026)

Zscaler's [2026 release summary](https://help.zscaler.com/zscaler-client-connector/client-connector-app-release-summary-2026)
lists macOS build **4.8.0.281** as generally available.
The user authorized downloading the versioned package from
`https://d32a6ru7mhaq0c.cloudfront.net/Zscaler-osx-4.8.0.281-installer.pkg`
and testing it on disposable runners. No vendor binary is redistributed.
Its SHA-256 is
`51e8d295ba0c2cfe1efaf775d8fe24710b3737d95342194b3b43c45de7d1aa92`.

Zscaler's [download guidance](https://help.zscaler.com/zscaler-client-connector/understanding-zscaler-client-connector-app-downloads)
directs administrators to **Infrastructure > Client Connector > App Store**
in the tenant Admin Console. It directs end users to their IT administrator.
This CI experiment is not a replacement for that supported acquisition path.

The vendor's [Jamf deployment guidance](https://help.zscaler.com/zscaler-client-connector/deploying-zscaler-client-connector-jamf-pro-macos)
independently identifies extension Team ID `PCBCQZJ7S7` and discusses Sequoia
and Tahoe. Local read-only package inspection verified Apple's trusted
`Developer ID Installer: Zscaler inc (PCBCQZJ7S7)` chain and notarization.
The payload's app version is 4.8.0.281, with native x86_64 and arm64 code.
The native PKG installs to `/Applications/Zscaler`; its postinstall installs
the vendor service, tunnel, and tray launchd plists.
Nothing was installed or executed locally.
No documented tenant-free setup was found in the
[macOS installation options](https://help.zscaler.com/zscaler-client-connector/customizing-zscaler-client-connector-install-options-macos).
That does **not** prove services cannot start before enrollment.

[`real_client_integration.py`](real_client_integration.py) refuses local execution,
self-hosted runners, existing installations, and unselected OS/architectures.
It verifies the downloaded hash, package signing identity, Gatekeeper assessment,
and installed app version/signature before checking actual service readiness.
It opens the real app as the logged-in runner without tenant parameters.
Both a real agent and daemon must be running, including every discovered
`RunAtLoad` service. The demand-started tunnel is reported, never fabricated.
Installation success alone cannot pass. Startup has a 120-second bound.
The allowlisted JSON report distinguishes discovered jobs, running PIDs,
extension state, and the absence of enrollment/network-function evidence.
Raw installer output, vendor diagnostics, configuration, and payloads are not
uploaded. Readiness failure remains a failed job, never a fixture fallback.

After readiness, the same harness invokes the public stop/start scripts as the
ordinary console user. It checks every original vendor process exits,
repeats stop, observes every discovered target absent for 600 seconds,
then checks restoration of the original running baseline and all discovered
launchd jobs. Repeated start must retain service PIDs. The actual tray executable
must belong to the console user, and an unrelated existing `logd` service must
retain its PID. Extension state is reported separately before and after.
The demand-started tunnel need not run without enrollment; this is not a
functional VPN or "all Zscaler components stopped" certification.
