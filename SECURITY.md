# Security Policy

agenthalt is an emergency control. A vulnerability in it can mean a stop that silently fails, a halt that an
attacker can trigger against a healthy fleet, or a receipt that proves a containment that never happened. We
treat those as the most serious class of bug this project can have.

## Reporting a vulnerability

Report privately — **do not open a public issue**:

- Use GitHub's [private vulnerability reporting](https://github.com/agentic-suite/agentsec-agenthalt/security/advisories/new)
  for this repository, or
- follow the [organization security policy](https://github.com/agentic-suite/.github/blob/main/SECURITY.md).

Please include the agenthalt version, OS, the command or trigger path involved, and — where you have them — the
receipt, journal segment, or drill output that shows the problem.

## What counts as a security issue here

Beyond the usual classes, these are in scope and handled with priority
([PRD 06](docs/prd/06-security-baseline.md), [PRD 30](docs/prd/30-threat-model.md)):

- **Stop suppression** — any way for an agent, harness, or attacker to keep acting after a halt, or to make a
  halt path fail open.
- **Halt forgery / DoS via the switch** — raising a halt without authorization, or widening a trigger's scope.
- **Receipt or journal forgery** — a receipt that verifies but misstates what stopped, or an undetected journal
  edit.
- **Evidence leakage** — secrets or personal data persisted unredacted in the journal, logs, or evidence.

## While a fix is pending: the manual fallback

A kill-switch advisory always ships with the way to stop agents **without** agenthalt. The per-layer manual
commands (process group, cgroup, credential revocation, gateway, firewall) are in the failure-mode runbook,
[PRD 28 §7](docs/prd/28-failure-mode-runbook.md). If you believe agenthalt cannot stop an agent you are
responsible for, use that runbook first and report second.

## Supported versions

Security fixes follow the support windows in [PRD 40](docs/prd/40-support-versioning-and-deprecation.md): a
stop-suppression or receipt-forgery fix is backported to every supported minor. agenthalt has not yet had a
release; until `v0.1.0` ships, only the `main` branch is supported.
