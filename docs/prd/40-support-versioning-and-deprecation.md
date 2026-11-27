# PRD 40 — Support, Versioning & Deprecation Policy

**BLUF:** What we support and for how long, which public surfaces are frozen forever, and how anything ever
breaks: **loudly, with a migration note, never silently** (DD-31). The receipt schema, exit codes, journal entry
format, and evidence chain semantics are **Tier-0 immutable** (additive-only, a v0.1.0 receipt verifies forever);
the library API, CLI, adapter contract, and trigger config are stable semver surfaces; internals are volatile
with shipped migrations. Platforms and harnesses get dated support windows, and the compatibility table is the
honest record of what "supported" means per release.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Supported platforms (the dated matrix)

| Surface | Supported at v0.1.0 | Policy |
|---|---|---|
| macOS | current and prior two major releases (stated per release) | drill leg green per release or the row drops to "best-effort" honestly |
| Linux | stated distro/kernel classes (drill runner classes pinned per release) | cgroup/eBPF legs documented per kernel; agentkernel-dependent legs only where agentkernel is deployed |
| Windows | **not supported** — dated plan, revisited v0.2.0 (DD-17) | the install surface says so plainly; no silent partial support |
| Python | 3.10+ (matching the ecosystem) | EOL Pythons drop with a release note |

**What "supported" means** ([PRD 19](19-harness-compatibility.md)): the drill leg (or field-test case) is green
on that surface for that release — *exercised*, not *assumed*. The compatibility table regenerates from CI per
release (DD-30) and carries exercised / covered-by-construction / not-tested states, never a bare ✔.

## Public-surface stability tiers

| Tier | Surfaces | Change policy |
|---|---|---|
| **Tier 0 — Immutable** | `agenthalt.receipt.v1` fields & semantics ([PRD 26](26-receipt-schema-and-examples.md)) · evidence format + chain semantics ([PRD 17](17-evidence-and-proof-format.md)) · exit codes ([PRD 37](37-cli-and-output-ux-spec.md)) · journal entry format · the halt event shape in the agentwatch schema | **Additive-only.** A breaking change requires a *new* schema id + a migration note + verifier support for the old id kept indefinitely. A v0.1.0 receipt verifies forever — this is the product's proof, and proof does not expire |
| **Tier 1 — Stable** | Python library `halt()`/`prove()` API · CLI commands & flags · adapter contract schema · trigger config format · drill pack `cases.yaml` | Semver-compatible changes; removals go through the deprecation process below; new flags/fields may land in any release |
| **Tier 2 — Compatible** | config file format (additive within a major; an unknown key is rejected, never ignored — DD-42) · metric names/labels (labels additive only, [PRD 36](36-observability-and-soc-pack.md)) · log line fields (additive) | Additive within a major; schema-validated at load with clear errors |
| **Tier 3 — Volatile** | store internals · lineage segment layout · coordinator internals · drill runner internals | Free to change **with shipped migrations**; `agenthalt doctor --migrate` is the only supported path |

## Semver rules (0.x, with one honesty exception)

- During 0.x, minor bumps may change Tier-2/3 behavior with release notes; **Tier 0 and Tier 1 are treated as
  stable even in 0.x** — the exception is deliberate: responders write runbooks and scripts against receipts and
  exit codes on day one, and "we're pre-1.0" is not a defense for breaking a proof artifact.
- 1.0 is the commitment that Tier 1 surfaces move to full semver discipline; its gate is the v0.1.0 release
  gate ([PRD 07](07-success-metrics.md)) plus ≥1 partner drill cadence and ≥2 exercised Tier-1 harnesses.

## Deprecation process (how anything ever breaks)

1. **Announce** in release notes + `doctor` warning + docs, with the replacement and the date.
2. **Dual-support** for ≥ 2 minor releases (old flag/alias works; both journaled paths verify).
3. **Remove** with a major-bump entry and a migration note (DD-31). There is no step 4 — silent removals do not
   exist; `git log` on a removed surface always shows the announcement release.

**Never-deprecated list** (explicit): receipt verification for old schema ids; journal segments readable
forever; exit-code semantics. Breaking any of these is, by definition, a new product.

## Upgrade path

- Store/journal/lineage migrations ship **with** the release that changes them; `agenthalt doctor --migrate`
  validates, backs up, migrates, and re-verifies the chain post-migration (a migration that breaks chain
  verification is a release blocker).
- Mixed-version fleets: the adapter versions recorded in every receipt ([PRD 15](15-data-model.md)) make a
  mixed halt reconstructable; the policy is **coordinator ≥ layer adapters** — newer layers with an older
  coordinator are supported and report their version honestly, the reverse warns at load.
- Upgrade sequencing for the ecosystem: agenthalt composes via documented action surfaces, so layer upgrades
  land independently (the [PRD 32](32-build-vs-integrate.md) boundary is also the upgrade boundary).

## Support windows & security backports

| Version | Window |
|---|---|
| Latest minor | full support until the next minor |
| Prior minors (within a major) | security fixes only, until the next major + 3 months |
| EOL majors | no fixes; the disclosure runbook + manual fallback ([PRD 28](28-failure-mode-runbook.md)) remain valid *by design* — the layers' own commands outlive us |

Security support: disclosure SLAs per the org policy ([PRD 06](06-security-baseline.md)); a stop-suppression or
receipt-forgery fix backports to every supported minor, because a kill switch with known holes in any supported
line is a fleet liability, not just a bug ([PRD 31](31-claims-ledger.md) miss-handling).

## Compatibility recordkeeping

- Every release ships: compatibility table (platform × harness × layer × exercised state), adapter version
  matrix, schema ids supported, and the deprecation ledger (announced → dual-supported → removed, with dates).
- The claims ledger demotes any C-claim whose supporting surface entered a deprecated state without a successor
  artifact — support status and marketing claims cannot drift apart (RK-18 discipline applied to our own
  lifecycle).
