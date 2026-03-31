# Context Framing

## Section A: What the project is

This project is a governance layer for privileged tool use. `docs/SCOPE.md` defines it as a non-bypassable chokepoint for privileged actions, a deterministic policy engine that returns allow or deny decisions with reasons, a decision-recording and attestation system with signed tamper-evident logs, and a replay/verifier mechanism that can detect tampering and non-compliance. The same scope document also states what it is not: it is not a general alignment solution, not a replacement for application security or operating-system access control, not a guarantee against all exfiltration, and not a guarantee that model outputs are correct.

## Section B: What the development design is

The development design is the repository’s documented process for turning Greg’s goals into reviewed changes on `main`. It includes role definitions, dispatch and briefing formats, task templates, evidence contracts, merge gates, operational runbooks, and execution scripts such as `codex-unattended.sh` and `qt-runner.sh`. In this corpus, the development design is separate from the governance-layer product itself: the reviewer is evaluating how work is specified, executed, verified, and merged.

## Section C: Why the development system exists

`docs/dev/OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md` describes a multi-actor system with different capacities and authorities. Greg provides intent and acceptance; ChatGPT translates that intent into bounded dispatches; Codex executes throughput-oriented branch work; Cecil handles merge authority, conflict resolution, and architecture-sensitive judgment. The system exists to maintain throughput while constraining blast radius, preserving merge hygiene, and routing higher-risk decisions to the actor with the intended authority.

## Section D: The four actors and their roles

- Greg: source of intent, priorities, and acceptance. Greg does not normally perform terminal work or implementation.
- ChatGPT: orchestrator and batch architect. ChatGPT turns Greg’s intent into taskable Codex dispatches, keeps constraints and stop rules explicit, and decides when a merge plan is needed.
- Codex: throughput engine. Codex executes bounded task specs within allowlists, fails closed on missing specs or allowlists, and emits evidence and completion packets.
- Cecil: strategic and high-stakes operator. Cecil owns merges to `main`, conflict resolution, architecture-sensitive review, and arbitration when evidence or governance semantics are in question.

## Section E: What good performance looks like

The ops process defines progress as landed changes on `origin/main`, published branches that intentionally reduce future merge cost, evidence and contract hardening that makes future work safer, and strategic clarity that prevents wasted build cycles. `docs/dev/AGENT_CONTRACT.md` adds the operating expectation that read-only actions proceed automatically, state-changing actions remain auditable, and high-risk irreversible actions require explicit confirmation. Across these artifacts, good performance means bounded execution, truthful reporting, fail-closed behavior on missing prerequisites, deterministic evidence where applicable, and controlled merge behavior rather than raw activity volume.

## Section F: Current system maturity

At the time of packaging, `docs/dev/ASSIGNMENTS.md` contains 364 completed history entries under its History section, and `docs/dev/evidence/` contains 356 task evidence directories at the top level. The corpus also includes baseline proof records for the routed-runtime rollout (`docs/dev/ROUTED_RUNTIME_BASELINE__COMPLETION_RECORD__v0.md`, `docs/dev/CODEX_ROUTED_RUNTIME_BASELINE__COMPLETION_RECORD__v0.md`) and a QT runtime proof record (`docs/dev/QT_RUNTIME_PROOF__v0.md`). These counts indicate a system with substantial documented execution history, not a greenfield workflow.

## Section G: Known tensions

The source artifacts encode several recurring tensions:

- Throughput vs safety: the system is designed to keep Codex productive while also requiring allowlists, evidence, hot-file controls, and fail-closed stops.
- Autonomy vs oversight: Codex is expected to operate autonomously within task boundaries, but merge authority and architecture-sensitive judgment remain with Cecil, and ChatGPT remains the orchestrator.
- Rigor vs speed: deterministic evidence, verification, and merge-gate rules add safety and auditability but also increase execution overhead.
- Completeness vs maintenance cost: the system relies on many documents, templates, and operational scripts staying aligned, which improves explicitness but creates ongoing consistency-maintenance burden.
