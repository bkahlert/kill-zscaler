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

| Environment                              | Completed result                                                                                                | Boundary                                                                   |
|------------------------------------------|-----------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------|
| macOS 15.7.9 (24G830) and 26.6.2 (25G83) | [23 regressions and launchd fixtures passed](https://github.com/bkahlert/kill-zscaler/actions/runs/39731780695) | Earlier immediate stop/restore checks; no sustained observation            |
| Sonoma 14.x                              | Not yet verified                                                                                                | No completed Sonoma run; 14.0 and 14.6 remain specifically unverified      |
| Actual Zscaler Client Connector          | Not verified                                                                                                    | No suitable installer and tenant-free running-service baseline established |
| Enrolled/MDM-controlled Zscaler          | Not verified                                                                                                    | Requires an authorized tenant and deployment policy                        |

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
Before adding an installation workflow, establish a vendor-authorized,
versioned installer with supported OS/architecture, a pinned SHA-256,
independently verified vendor signing identity, and documented unattended usage.
No placeholder tenant, arbitrary "latest" URL, or fixture fallback is acceptable.

Without enrollment, the actual client must still expose a nonempty, running
vendor-service baseline. An enrollment or system-extension approval requirement
is a readiness blocker, not a green integration result.
Only after readiness can the same observer meaningfully check stop, sustained
absence, repeated operations, and restoration of actual services.
Extensions and enrolled policy remain separate evidence, not inferred from
launchd service status.

### Acquisition gate (October 22, 2026)

Zscaler's [2026 release summary](https://help.zscaler.com/zscaler-client-connector/client-connector-app-release-summary-2026)
lists macOS build **4.8.0.281** as generally available.
A read-only HEAD request to
`https://d32a6ru7mhaq0c.cloudfront.net/Zscaler-osx-4.8.0.281-installer.pkg`
returned HTTP 200. This contemporary lead replaces the Microsoft sample's
3.6.1.19 installer as a research candidate, not a reviewed installation manifest.

Zscaler's [download guidance](https://help.zscaler.com/zscaler-client-connector/understanding-zscaler-client-connector-app-downloads)
directs administrators to **Infrastructure > Client Connector > App Store**
in the tenant Admin Console. It directs end users to their IT administrator.
Authorization for direct-CDN acquisition and CI installation has not been
established. Reachability does not establish that authorization.

The vendor's [Jamf deployment guidance](https://help.zscaler.com/zscaler-client-connector/deploying-zscaler-client-connector-jamf-pro-macos)
independently identifies extension Team ID `PCBCQZJ7S7` and discusses Sequoia
and Tahoe. That is not verification of this package's signature or architecture.
No payload was downloaded, hashed, inspected, or installed.
Exact package architecture support and tenant-free service startup remain
unestablished. No documented tenant-free setup was found in the
[macOS installation options](https://help.zscaler.com/zscaler-client-connector/customizing-zscaler-client-connector-install-options-macos).
That does **not** prove services cannot start before enrollment.

**Blocked before installation:** obtain an authorized current installer and
permission for disposable CI use, then verify its hash, signature, architecture,
and actual unenrolled readiness. No real-client workflow or placeholder manifest
was added because those prerequisites are unresolved.
