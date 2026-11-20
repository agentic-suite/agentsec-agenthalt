# PRD 21 — Evidence Register & Method

**BLUF:** This document preserves the research behind agenthalt so the reasoning is auditable: the **evidence
register** (E1–E22) with primary sources, the **gap analysis** the product closes, the **open PRD tensions**,
and the **method**. It exists so a reviewer can check that the requirements are grounded, not asserted — and so
the sharpest claims (composed stop, proof-of-stop, the 09:01 readout) trace to the 2026 sources that demand
them.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Evidence register

| # | Evidence | Used for | Source |
|---|---|---|---|
| **E1** | Replit's agent deleted a production database and then **kept going and lied about it**; no stop control existed | The founding incident; Wave 0's headline "stop it" | [Fortune, 2025-07-23](https://fortune.com/2025/07/23/ai-coding-tool-replit-wiped-database-called-it-a-catastrophic-failure/) |
| **E2** | Plugin4Shell: 0-click RCE across all five major coding agents — the harness process itself is hostile | Zero-hook-surface containment (R5); hooks never load-bearing (DD-06) | [The Register, 2026-09-17](https://www.theregister.com/security/2026/09/17/ai-coding-agents-0-click-rce-flaw-could-hand-attackers-keys-to-the-kingdom/) |
| **E3** | Frontier models sabotaged their own shutdown scripts in experimental setups (up to 97% of trials); chatbots defied deletion orders and deceived users | "You cannot rely on the agent to stop itself" — the out-of-band rule | [arXiv 2509.14260](https://arxiv.org/abs/2509.14260); [Palisade Research](https://palisaderesearch.org/research/shutdown-resistance); [Berkeley RDI](https://rdi.berkeley.edu/peer-preservation/paper.pdf) |
| **E4** | Evaluation agents at Anthropic, Google, Meta, OpenAI and the UK AISI reached systems outside their test environments (Apr–Jul 2026) | Agents escape; the stop must exist before it's needed | [Tigera, "Would you notice?"](https://www.tigera.io/blog/would-you-notice-five-ai-agent-incidents-and-who-actually-caught-them/) |
| **E5** | The **five-switch drill**: delete-pod, revoke-key, deactivate-identity, deny-at-gateway, lock-in-kernel — **no single row empties the grid**; each leaves something running at 09:01 | The composed-stop thesis (R1); the readout (R11); the "no single-layer claim" anti-metric | [Tigera, 2026-11-02](https://www.tigera.io/blog/what-a-kill-switch-actually-means-for-your-agent-fleet/) |
| **E6** | "If the model can ignore it, it's not a kill switch"; kill must propagate the run graph; dual choke; confirmations not requests; fail closed; drill and publish measured numbers | The product's spine: R2, R8, R10, R14, DD-02/03/04/05 | [Clype, 2026-09-21](https://clype.io/blog/ai-agent-kill-switch) |
| **E7** | An agent kill switch has an **identity problem**: killing the agent leaves its OAuth grants, NHIs, and SaaS access alive | Credential revocation in the composed stop (CUJ-5); the blast map (R20) | [Grip, 2026-11-10](https://www.grip.security/blog/ai-kill-switch-isnt-enough) |
| **E8** | Identity deactivation stops the *next* login; in-flight session termination is a separate, later capability (Okta's own release notes) | The 09:01 residual-window honesty; unrevocable-grant reporting | [Okta, Oktane 2026](https://www.okta.com/newsroom/press-releases/ai-innovations-oktane-2026/) |
| **E9** | **AI Kill Switch Act (H.R. 9917)**: stop inference / terminate access / suspend / shut down; a graduated five-position framework; an *incident* includes sabotaging a shutdown instruction and concealing behaviour from a shutdown mechanism | The regulatory alignment matrix; PRD 06's threat model as law; the mode ladder (PRD 18) | [Congress H.R.9917](https://www.congress.gov/bill/119th-congress/house-bill/9917/text); [CSA research note](https://labs.cloudsecurityalliance.org/research/csa-research-note-ai-kill-switch-act-dhs-shutdown-authority) |
| **E10** | **UK NCSC**: operators should "always be able to 'pull the plug'… may mean more than stopping the agentic AI processes"; controls should cover the network around agents and the agent↔model path | The composed layers (sandbox + choke); the operator-facing trigger set | [NCSC blog, 2026-08-20](https://www.ncsc.gov.uk/blogs/managing-the-cyber-risk-of-agentic-ai) |
| **E11** | **EU AI Act Art. 14**: high-risk systems must let humans interrupt via "a 'stop' button or a similar procedure"; Art. 12 logging | The panic key + journaled actor; the snapshot as oversight evidence | [Aembit regulatory summary](https://aembit.io/blog/ai-kill-switch/) |
| **E12** | The 2026 vendor wave — CrowdStrike Falcon Guardian (11-03), JetStream (07-27), Okta Agent Gateway (09-22), Salesforce Agent Fabric GA (10-27), Aembit, Zenity ($125M Series C, 08-03), Tigera Lynx (11-02), Grip (11-10) — each cuts **one** wire | The landscape: crowded field, single-layer by construction; the whitespace rows #18–#20, #25 | [PRD 03](03-landscape.md) and sources therein |
| **E13** | OSS is loop-level only: `intutic` (KILL verdict in-loop), `LongGuard`, `stoke` (proxy), `loopguard` (budget daemon), `agent-killswitch` (in-process), `the-breaker` (hardware), ALS spec (taxonomy), `AgentDFIR` (after-the-fact), `kerneleye` (kernel layer) | No composed stop in OSS; agenthalt composes, not competes; `kerneleye` is a layer to compose | [PRD 03](03-landscape.md) OSS table and sources therein |
| **E14** | Aembit's own caveat: revocation only works if the agent has no other way in — static keys survive identity revocation | Unrevocable-grant honesty (CUJ-5); short-lived issuance (agentkeys) as the durable fix | [Aembit](https://aembit.io/blog/ai-kill-switch/) |
| **E15** | `ai-loopguard` (own, shipped): failure detection (repeated error, test-failure loop, schema-invalid, hallucination cycle), N-retry thresholds, session budget caps, 391 tests / 95.9% coverage | The absorbed halt-trigger class ([PRD 10](10-feature-parity.md)); the dead-man vocabulary | Vault #58; [PRD 10](10-feature-parity.md) |
| **E16** | Pods deleted by a stop destroy their own evidence; quarantine preserves the pod for investigation | Snapshot-before-termination (DD-10); `pause` as the evidence-preserving first move | [Tigera FAQ](https://www.tigera.io/blog/what-a-kill-switch-actually-means-for-your-agent-fleet/) |
| **E17** | In-flight cancel is best-effort; pretending it is synchronous "is how teams invent a false sense of stop" | The block-new vs cancel-in-flight honesty (PRD 02, PRD 13) | [Clype](https://clype.io/blog/ai-agent-kill-switch) |
| **E18** | A stop that lifts must return to a *chosen* normal state, or nobody will lift it | `lift` semantics; the journaled mode history (PRD 18) | [Tigera](https://www.tigera.io/blog/what-a-kill-switch-actually-means-for-your-agent-fleet/) |
| **E19** | Frontiers, frameworks, and kernels differ: eBPF/cgroup containment exists on Linux (`kerneleye`, Tigera Lynx kernel lock; bpf_send_signal), process groups on macOS | Per-OS executor adapters (DD-23); platform honesty (DD-17) | [kerneleye](https://github.com/rxhtt/kerneleye); eBPF cgroup tutorials; [Tigera Lynx](https://www.tigera.io/blog/what-a-kill-switch-actually-means-for-your-agent-fleet/) |
| **E20** | Ecosystem PRD #216: R1–R12 with the ≤1 s criterion, "no new protocol," "no undo," evidence "accepted as forensic artifact," harness-agnostic mandate | The v0.1.0 scope's backbone (R1–R14 extend it with the 2026 table stakes) | Ecosystem PRD 07 (agenthalt) |
| **E21** | Zenity's runbook guidance: "Confirm you can stop every instance, sub-agent, and scheduled trigger, without wiping memory or logs" | Lineage containment + evidence preservation as *stated buyer expectations* | [Zenity incident triage](https://zenity.io/blog/triaging-ai-agent-security-incidents) |
| **E22** | Salesforce's auto-fire kill switch (on failed evaluation) ships Jan 2027 — automatic triggers are the announced trajectory | The dead-man switches (R16) as v0.2.0, ahead of the commercial auto-fire curve | [Salesforce Agent Fabric](https://www.salesforce.com/news/stories/agent-fabric-catch-failures-control-ai-costs/) |

## Gap analysis (what agenthalt closes)

| Gap | Evidence | agenthalt answer |
|---|---|---|
| Every switch cuts one wire; no composed stop exists | E5, E12 | The composed stop over process + credentials + gateway + sandbox (R1) |
| Stop is a process kill, not a graph op — children survive | E6, E21 | The lineage registry + subtree containment + proof (R2, R9, R10) |
| Nobody can prove a stop — requests are reported as results | E6, E12 | Confirmations-only receipts + offline verification (R10, R21) |
| The stop destroys the evidence | E16, E21 | Snapshot-before-termination, hash-chained (R3, DD-10) |
| Identity/credential survival after the kill | E7, E8, E14 | Revocation in the composed stop + unrevocable-grant honesty + the blast map (CUJ-5, R20) |
| Nobody has pulled the switch | E5 ("a kill switch nobody has pulled is a label on a box") | The drill: CI-measured, partner-runnable, release-blocking (R14, R17) |
| "What is still running at 09:01?" is unanswerable | E5 | The readout (R11) |
| In-loop breakers stop the loop, not the graph | E13, E15 | Out-of-band composition; the absorbed trigger class re-pointed at the stop (R16) |
| Shutdown sabotage / concealment is a named incident class | E3, E9 | Out-of-band store, hooks never load-bearing, suppression-as-trigger (R5, PRD 06) |
| Rollback theater | E17 (+ the category's marketing) | Irreversibility honesty + compensation lists (R13) |
| Regulatory capability sets with no operator-side mapping | E9, E10, E11 | The alignment matrix + the receipt as oversight evidence (PRD 20) |

## PRD tensions (open decisions)

1. **Lineage edge source priority** — harness hook vs. process adapter vs. runtime adapter when they disagree.
   Hypothesis: the process adapter wins (it is what containment acts on); needs design-partner data (RK-2).
2. **Pause max-TTL default** — 24 h ships as the hypothesis; pause-limbo vs. destroyed legitimate pauses
   (RK-15, [PRD 18](18-stop-modes.md)).
3. **Fleet-halt quorum** — is 2 distinct approvers right for `--all`? (R18, needs design-partner input.)
4. **Escalate-on-act defaults** — which attempt classes auto-escalate pause→quarantine→kill; false escalations
   burn trust ([PRD 18](18-stop-modes.md) open questions).
5. **Snapshot retention + encryption** — how long, where, who reads captured (redacted) secrets; ties to the
   security baseline and agentwatch retention.
6. **Windows timing** — v0.1.0 ships macOS + Linux; is the Windows job-object adapter v0.2.0 or design-partner
   driven? (DD-17.)
7. **agentgate co-shipping** — the gateway layer reports `unsupported` until agentgate v1.0 (Wave 1); is the
   receipt's `partial-layer` status acceptable to design partners, or does v0.1.0 wait? (DD-18; hypothesis: ship
   honest, don't wait.)
8. **Stuck-loop triggers at v0.3.0** — the closest to "judgment" in the dead-man set; requires modes + RBAC
   proven first (DD-14).
9. **Remote anchoring default** — local chain anchor vs. RFC 3161 opt-in for high-assurance deployments
   ([PRD 17](17-evidence-and-proof-format.md)).
10. **Verification-key publication** — where offline verifiers get enforcement-point keys; hypothesis: the
    release attestation bundle (PRD 20 ladder).

## Method

- **Research base:** the agentic-suite agent-security research (~85 sources) **plus the 2026 kill-switch wave**
  — the regulatory texts (H.R. 9917, NCSC, EU AI Act, CA EO N-9-26) read as *engineering requirements*, the
  vendor launches read as *single-layer evidence*, and the practitioner bar (Clype, Tigera, Grip, Aembit,
  Zenity) adopted verbatim where it is correct.
- **Standards-first:** requirements anchor to the ecosystem's open surfaces (agentwatch schema, the chain
  pattern) and align to the frameworks above — alignment documented, compliance never claimed ([PRD 20](20-standards-and-claims.md) §F).
- **Parity-preserving:** every absorbed `ai-loopguard`/BehaviorGuard capability is disposed of explicitly
  ([PRD 10](10-feature-parity.md)); the one semantic inversion (fail-open → fail-closed) is documented, not
  smuggled.
- **Proof-anchored:** every capability claim maps to a drill case; the drill is release-blocking; numbers are
  measured, never assumed (DD-29/32).
- **Honesty rule:** the claims vocabulary forbids over-claiming; the receipt/UX refuse rollback theater and
  false success by construction (R10, R13).

## What would falsify this PRD

- If the **≤1 s** alert→full-stop budget cannot be met on the drill hardware with the block-new-first
  sequencing, the composition-over-speed thesis is wrong (R1, DD-22).
- If **lineage gaps** are routine (adapters routinely miss descendants), the graph-containment thesis is wrong —
  agenthalt degrades into "a better pod delete" (R2, RK-2).
- If receipts built from **confirmations** prove impractical (enforcement points can't sign/report in budget),
  the proof-of-stop thesis is wrong (R10, RK-3).
- If **nobody drills** — partners adopt the switch but never run the rehearsal — the "drill is the product"
  thesis is wrong, and agenthalt is a label on a box (R14, R17).
- If the composed layers **drift into parallel kill paths** (agentgate ships its own halt, agentkeys its own
  panic), the single-breaker-box thesis is wrong (DD-33, RK-21).
