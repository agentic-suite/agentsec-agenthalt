# PRD 38 — Evidence Privacy & Data-Handling Policy

**BLUF:** The evidence snapshot is incident-response gold **and a personal-data liability in one artifact**: it
captures process trees (usernames, paths, command args), open connections (IPs, hosts), and the agentwatch
trace window (tool arguments — potentially message content, customer data, secrets). This policy defines the
data inventory, the **redaction pipeline** (redact-before-persistence, proven by the canary drill case), access
control, retention, export rules, and data-subject-request handling — so an operator can answer *"what personal
data does your halt evidence hold, and who can read it?"* with a document instead of a shrug. It is policy
**template + product requirements**, not legal advice (the standing honesty rule).

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Why this is a PRD-level concern

- The snapshot is taken at the worst possible moment for data minimization: the scene *is* the point. Forensic
  research shows raw captures hide ~4x the sensitive material a first scan finds (decoded tokens, JWTs) —
  redaction must be a **pipeline**, not a scan ([PRD 06](06-security-baseline.md) control, operationalized here).
- EU AI Act Art. 12 *requires* logging for high-risk systems while GDPR *constrains* it; the operator can only
  satisfy both if the tool's defaults are defensible by design. US/state breach rules add a third frame.
- The blast-map/readout surfaces credential identities and network topology — the same care must apply to what
  we show responders ([PRD 26](26-receipt-schema-and-examples.md)).

## Data inventory (what a halt captures)

| Artifact | Data categories present | Sensitivity |
|---|---|---|
| **Trace window** (agentwatch events) | Tool calls + arguments; possibly message content, customer data, secrets-in-args; session/principal ids | High — content data |
| **Process tree** | Usernames (process owners), executable paths, **argv** (can contain tokens, file paths, personal data) | High |
| **Open connections** | Local/remote IPs, hostnames, ports; owning process | Medium — infrastructure + potentially user activity |
| **Credential inventory** | Grant ids, issuers, scopes, expiry — **not** secret material (typed refs only, agentkeys invariant) | Medium |
| **Receipt / journal** | Actor identities (emails/principals), scopes, reasons, timestamps | Medium — personnel data (who halted what) |

## The redaction pipeline (product requirements)

1. **Typed placeholders, not deletion:** secrets → `secret:<kind>[redacted ×n]`; emails/phones →
   `pii:<class>[redacted]`; the count/class survives so the forensic value survives
   ([PRD 17](17-evidence-and-proof-format.md)).
2. **Redact-before-persistence:** the pipeline runs between collection and write; there is no "raw then clean"
   temp file, ever — the raw bytes never touch disk (RK-adjacent: the disk is the attacker's post-halt target).
3. **The canary proves it:** `evidence-canary` (drill case #10) plants known canaries in argv, args, and a
   connection string; the golden asserts zero canary occurrences in snapshot, receipt, and **export bundle**.
4. **Reversible-lookup escrow (opt-in, off by default):** if an org needs un-redacted evidence for a legal
   process, an **encrypted escrow** segment keys redactions to a local KMS entry — access is a journaled,
   dual-control event. v0.2.0 surface; the v0.1.0 answer is "redacted, permanently."
5. **Receipts carry no content:** the receipt schema contains refs and counts by design — personnel data (actor)
   is its only personal-data class, and it is the *point* of the journal (Art. 12-friendly).

## Access control

| Surface | Who can read | Enforcement |
|---|---|---|
| Snapshot directory | OS file perms + explicit `agenthalt evidence` access role; default `0700`, per-halt subdirs | local ACLs; export requires the role |
| Escrow (v0.2.0, opt-in) | dual-control + journaled unwrap | local KMS |
| Export bundle | The exporter of record (the operator) | bundle carries a data-handling notice header (below) |
| Metrics | Aggregates only — no personal data by construction ([PRD 36](36-observability-and-soc-pack.md) cardinality rule) | schema invariant |

## Retention & deletion (the chain tension, resolved out loud)

- Defaults: snapshots **90 days hot**, then archive-encrypted; journal **90 days hot + archived** per the
  shared chain policy ([PRD 13](13-non-functional-requirements.md)); receipts are small and retained with the
  journal. Incident hold and legal hold extend per-case — and both are journaled.
- **Deletion never breaks the chain:** erasure removes *content files*; the chain entries (hashes) remain as
  non-reversible commitments — the erasure itself is a journaled event, so the record honestly says "evidence
  existed, was retained, then erased on <date> under <policy>." This is the stated resolution of
  chain-integrity vs. erasure: hashes are commitments, not personal data. (Documented reasoning, not legal
  advice — operators confirm with counsel.)
- A **missing segment remains a loud finding** ([PRD 13](13-non-functional-requirements.md)): erasure via
  policy is distinguishable from erasure via tampering *because the policy erasure is journaled*.

## Export & cross-border

- The export bundle's `manifest.json` carries a **data-handling notice**: categories present (post-redaction),
  retention origin, exporter of record, and the redaction version. An operator handing evidence to a partner,
  auditor, or authority is handing them a labeled artifact, not a mystery tarball.
- Cross-border transfer is the operator's compliance question; the tool's contribution is the inventory +
  notice above. We ship no cloud sink by default — local-first is also the privacy posture
  ([PRD 13](13-non-functional-requirements.md) portability).

## Data-subject requests (DSAR tooling)

- `agenthalt evidence find --subject <ref>` (v0.2.0): searches snapshot *metadata* (principal ids, paths) for
  a subject's presence across halts; produces the list of artifacts + their retention state.
- Production to a subject uses the redacted form; the escrow path exists for the rare lawful plaintext case.
- The journal's actor data is exempt-by-purpose (security records) in most frames — again, stated as mapping,
  not as legal advice.

## GDPR mapping (policy template rows)

| GDPR article | This policy's answer |
|---|---|
| Art. 5(1)(c) minimization | Typed-placeholder redaction; receipts are refs + counts |
| Art. 5(1)(e) storage limitation | Retention defaults + journaled erasure |
| Art. 6 lawful basis | The operator's legitimate interest / legal obligation — the tool makes the record defensible |
| Art. 25 data protection by design | Redact-before-persistence; escrow off by default; canary case in CI |
| Art. 28 processor role | agenthalt (the OSS tool) processes nothing centrally; the *operator* is controller of their snapshots — local-first is the answer |
| Art. 32 security | Encryption at rest (trace window), chain integrity, access roles |
| Art. 15/17 access & erasure | DSAR tooling + journaled, chain-preserving erasure |

## Claims discipline

- Allowed: "evidence is redacted before persistence and proven by a canary test" (C-07 artifact).
- Forbidden: "GDPR compliant" (F-04 class — compliance is the operator's counsel's claim, never the README's).
- The inventory table is regenerated with the coverage matrix; a new capture field without a redaction rule
  fails the same CI lint ([PRD 31](31-claims-ledger.md) rule 1).
