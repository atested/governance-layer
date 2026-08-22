"""WP-RL-001 validators.

Each validator returns the catalog result contract
{"validator", "target_ids", "passed", "findings", "evidence_refs"} as a dict.
The 'passed' flag is true only when the stated pass condition holds for every
supplied target.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

from .domain import (
    AGENT_ACTIONS,
    AGENT_MODES,
    AGENT_STATES,
    CADENCES,
    CONNECTION_STATUSES,
    CRYPTO_CLAIM_MARKERS,
    DRAFT_STATES,
    INVOCATION_STATUSES,
    LOG_RECORD_TYPES,
    PIPELINE_STAGE_NAMES,
    PROHIBITED_ATTESTATION_CAPABILITIES,
    PROHIBITED_OPERATOR_CONTROLS,
    PROVIDERS,
    RUN_STATUSES,
    TASK_TYPES,
    compute_record_hash,
    default_budget,
    default_schedule,
    evaluate_schedule,
    verify_log,
)


def _result(validator, target_ids, passed, findings, evidence_refs):
    return {
        "validator": validator,
        "target_ids": list(target_ids),
        "passed": passed,
        "findings": findings,
        "evidence_refs": evidence_refs,
    }


def _ids(objects, attr):
    return [str(getattr(obj, attr)) for obj in objects]


# ---------------------------------------------------------------------------
# Behavioral validators.
# ---------------------------------------------------------------------------

def agent_atom_validator(fixture):
    """REQ-ATL-001: Agent is the top-level unit of work; no 15-stage pipeline."""
    routes = fixture.get("routes", [])
    pipeline_controls = fixture.get("pipeline_controls", [])
    agents = fixture.get("agents", [])
    findings = []
    exposed = [
        name
        for name in list(routes) + list(pipeline_controls)
        if str(name).lower() in PIPELINE_STAGE_NAMES
    ]
    if exposed:
        findings.append("exposed pipeline surface: " + repr(exposed))
    if not agents:
        findings.append("no Agent instances present")
    return _result(
        "AgentAtomValidator", _ids(agents, "agent_id"), not findings, findings,
        ["routes:" + str(len(routes)), "pipeline_controls:" + str(len(pipeline_controls))],
    )


def brief_only_authoring_validator(fixture):
    """REQ-ATL-002: live Agent from a brief plus schedule/source selections."""
    agent = fixture.get("persisted_agent")
    prohibited = fixture.get("prohibited_authoring", [])
    findings = []
    if prohibited:
        findings.append("prohibited authoring surface present: " + repr(prohibited))
    if agent is None:
        findings.append("no persisted Agent")
    else:
        if agent.state != "live":
            findings.append("Agent is not live (state=" + repr(agent.state) + ")")
        if not agent.brief_text or not str(agent.brief_text).strip():
            findings.append("Agent brief is empty")
        if not agent.sources:
            findings.append("Agent has no sources")
        if not isinstance(agent.schedule, dict) or not agent.schedule.get("cadence"):
            findings.append("Agent schedule is missing or invalid")
    return _result(
        "BriefOnlyAuthoringValidator",
        [agent.agent_id] if agent is not None else [],
        not findings, findings, [],
    )


def brief_interpretation_validator(fixture):
    """REQ-ATL-003: preserve values, map worked example, report missing."""
    scenarios = fixture.get("scenarios", [])
    findings = []
    target_ids = []
    for index, scenario in enumerate(scenarios):
        label = "scenario " + str(index)
        target_ids.append(label)
        interpreted = scenario.get("interpreted") or {}
        clarifications = list(scenario.get("clarifications", []))
        expected = scenario.get("expected")
        required_missing = list(scenario.get("required_missing", []))
        if expected is not None:
            if interpreted != expected:
                findings.append(
                    label + ": interpreted diverges from expected "
                    "(observed " + repr(interpreted) + ", expected " + repr(expected) + ")"
                )
            if clarifications:
                findings.append(
                    label + ": fully specified brief reported clarifications "
                    + repr(clarifications)
                )
        else:
            for field in required_missing:
                value = interpreted.get(field)
                if value not in (None, "", [], {}):
                    findings.append(
                        label + ": required " + repr(field) + " was invented instead "
                        "of reported (observed " + repr(value) + ")"
                    )
            if not clarifications:
                findings.append(label + ": missing required meaning was not reported")
    return _result(
        "BriefInterpretationValidator", target_ids, not findings, findings, [],
    )


def agent_lifecycle_validator(fixture):
    """REQ-ATL-004: only draft/live/paused persist; runs start only while live."""
    agents = fixture.get("agents", [])
    transitions = fixture.get("transitions", [])
    runs = fixture.get("runs", [])
    findings = []
    state_by_id = {a.agent_id: a.state for a in agents}
    for agent in agents:
        if agent.state not in AGENT_STATES:
            findings.append(
                "Agent " + repr(agent.agent_id) + " has invalid state " + repr(agent.state)
            )
    for transition in transitions:
        to = transition.get("to")
        if to not in AGENT_STATES:
            findings.append(
                "transition to invalid state " + repr(to) + " for "
                + repr(transition.get("agent_id"))
            )
    for run in runs:
        state = state_by_id.get(run.agent_id)
        if state != "live":
            findings.append(
                "Run " + repr(run.run_id) + " started for non-live Agent "
                + repr(run.agent_id) + " (state=" + repr(state) + ")"
            )
    return _result(
        "AgentLifecycleValidator",
        _ids(agents, "agent_id") + [t.get("agent_id", "?") for t in transitions],
        not findings, findings, [],
    )


def run_accounting_validator(fixture):
    """REQ-ATL-006: truthful Run accounting; unavailable cost is null."""
    items = fixture.get("runs", [])
    findings = []
    target_ids = []
    for item in items:
        run = item["run"]
        cost_available = bool(item.get("cost_available", True))
        target_ids.append(run.run_id)
        if run.candidates_qualified > run.candidates_seen:
            findings.append(
                "Run " + repr(run.run_id) + ": qualified exceeds seen "
                "(" + str(run.candidates_qualified) + " > " + str(run.candidates_seen) + ")"
            )
        if run.drafts_produced > run.candidates_qualified:
            findings.append(
                "Run " + repr(run.run_id) + ": drafts exceed qualified "
                "(" + str(run.drafts_produced) + " > " + str(run.candidates_qualified) + ")"
            )
        if not run.provider_used or not str(run.provider_used).strip():
            findings.append("Run " + repr(run.run_id) + ": provider not identified")
        if run.token_cost is None and cost_available:
            findings.append("Run " + repr(run.run_id) + ": available cost recorded as null")
        if run.token_cost is not None and not cost_available:
            findings.append("Run " + repr(run.run_id) + ": unavailable cost was fabricated")
        if run.token_cost is not None and run.token_cost < 0:
            findings.append("Run " + repr(run.run_id) + ": negative token cost")
        if run.status not in RUN_STATUSES:
            findings.append("Run " + repr(run.run_id) + ": invalid status " + repr(run.status))
        if run.status in ("succeeded", "failed", "cancelled") and run.finished_at is None:
            findings.append("Run " + repr(run.run_id) + ": terminal status without finished_at")
        if run.status == "running" and run.finished_at is not None:
            findings.append("Run " + repr(run.run_id) + ": running status with finished_at")
        if run.finished_at is not None and run.finished_at < run.started_at:
            findings.append("Run " + repr(run.run_id) + ": finished before started")
    return _result("RunAccountingValidator", target_ids, not findings, findings, [])


def resignable_run_log_validator(fixture):
    """REQ-ATL-028: append-only, unsigned, predecessor-linked log."""
    prior = list(fixture.get("prior", []))
    appended = list(fixture.get("appended", []))
    findings = []
    if len(appended) < len(prior):
        findings.append("appended log is shorter than prior log")
    else:
        for index, record in enumerate(prior):
            if appended[index] != record:
                findings.append("prior record " + str(index) + " was mutated")
    ok, log_findings = verify_log(appended)
    findings.extend(log_findings)
    for index, record in enumerate(appended):
        if record.record_type not in LOG_RECORD_TYPES:
            findings.append("record " + str(index) + ": disallowed type " + repr(record.record_type))
        if "signature" in record.payload:
            findings.append("record " + str(index) + ": signature field present")
    return _result(
        "ResignableRunLogValidator",
        [r.record_id for r in appended],
        not findings, findings, [],
    )


def attestation_drop_validator(fixture):
    """REQ-ATL-029: no signing keys, signatures, verifier, chain claims, index."""
    capabilities = fixture.get("capabilities", [])
    claims = fixture.get("claims", [])
    scenarios = fixture.get("scenarios", [])
    findings = []
    for capability in capabilities:
        if capability in PROHIBITED_ATTESTATION_CAPABILITIES:
            findings.append("prohibited capability present: " + repr(capability))
    for claim in claims:
        lowered = str(claim).lower()
        if any(marker in lowered for marker in CRYPTO_CLAIM_MARKERS):
            findings.append("cryptographic claim present: " + repr(claim))
    for scenario in scenarios:
        if not scenario.get("success"):
            findings.append("scenario did not succeed: " + repr(scenario.get("name")))
    return _result(
        "AttestationDropValidator",
        [s.get("name", "?") for s in scenarios],
        not findings, findings, [],
    )


def single_operator_boundary_validator(fixture):
    """REQ-ATL-031: one self-hosting operator; no auth/billing/tenancy."""
    scenarios = fixture.get("scenarios", [])
    controls = fixture.get("controls", [])
    findings = []
    for control in controls:
        if control in PROHIBITED_OPERATOR_CONTROLS:
            findings.append("prohibited control present: " + repr(control))
    for scenario in scenarios:
        if not scenario.get("success"):
            findings.append("single-operator scenario failed: " + repr(scenario.get("name")))
    return _result(
        "SingleOperatorBoundaryValidator",
        [s.get("name", "?") for s in scenarios],
        not findings, findings, [],
    )


# ---------------------------------------------------------------------------
# Schema validators.
# ---------------------------------------------------------------------------

def _has_valid_schedule(schedule):
    if not isinstance(schedule, dict):
        return False
    cadence = schedule.get("cadence")
    if cadence not in CADENCES:
        return False
    if cadence == "hourly":
        return True
    time = schedule.get("time")
    if not isinstance(time, str) or not time:
        return False
    if cadence == "weekly":
        days = schedule.get("days")
        if not isinstance(days, list) or not days:
            return False
    return True


def agent_schema_validator(fixture):
    """SCH-ATL-001."""
    agents = fixture.get("agents", [])
    findings = []
    seen_ids = set()
    for agent in agents:
        if not agent.agent_id or agent.agent_id in seen_ids:
            findings.append("Agent ID missing or duplicated: " + repr(agent.agent_id))
        seen_ids.add(agent.agent_id)
        if not agent.brief_text or not str(agent.brief_text).strip():
            findings.append("Agent " + repr(agent.agent_id) + ": brief is empty")
        if not _has_valid_schedule(agent.schedule):
            findings.append("Agent " + repr(agent.agent_id) + ": invalid schedule")
        if not isinstance(agent.sources, list) or not agent.sources:
            findings.append("Agent " + repr(agent.agent_id) + ": no sources")
        else:
            for source in agent.sources:
                value = source.get("value") if isinstance(source, dict) else None
                if not value or not str(value).strip():
                    findings.append("Agent " + repr(agent.agent_id) + ": source lacks value")
        if agent.action not in AGENT_ACTIONS:
            findings.append("Agent " + repr(agent.agent_id) + ": invalid action " + repr(agent.action))
        if agent.mode not in AGENT_MODES:
            findings.append("Agent " + repr(agent.agent_id) + ": invalid mode " + repr(agent.mode))
        if agent.state not in AGENT_STATES:
            findings.append("Agent " + repr(agent.agent_id) + ": invalid state " + repr(agent.state))
        budget = agent.budget
        if not isinstance(budget, dict):
            findings.append("Agent " + repr(agent.agent_id) + ": missing budget")
        else:
            for key in ("max_surfaced_per_run", "max_drafts_per_run"):
                value = budget.get(key)
                if not isinstance(value, int) or value < 0:
                    findings.append("Agent " + repr(agent.agent_id) + ": non-negative budget required")
    return _result("AgentSchemaValidator", _ids(agents, "agent_id"), not findings, findings, [])


def run_schema_validator(fixture):
    """SCH-ATL-002."""
    runs = fixture.get("runs", [])
    agent_ids = {a.agent_id for a in fixture.get("agents", [])}
    findings = []
    for run in runs:
        if run.agent_id not in agent_ids:
            findings.append("Run " + repr(run.run_id) + ": agent_id does not resolve")
        if run.candidates_qualified > run.candidates_seen:
            findings.append("Run " + repr(run.run_id) + ": qualified exceeds seen")
        if run.drafts_produced > run.candidates_qualified:
            findings.append("Run " + repr(run.run_id) + ": drafts exceed qualified")
        if not run.provider_used or not str(run.provider_used).strip():
            findings.append("Run " + repr(run.run_id) + ": provider missing")
        if run.token_cost is not None and run.token_cost < 0:
            findings.append("Run " + repr(run.run_id) + ": negative cost")
        if run.status not in RUN_STATUSES:
            findings.append("Run " + repr(run.run_id) + ": invalid status")
        if run.finished_at is not None and run.finished_at < run.started_at:
            findings.append("Run " + repr(run.run_id) + ": finished before started")
    return _result("RunSchemaValidator", _ids(runs, "run_id"), not findings, findings, [])


def _valid_url(value):
    return isinstance(value, str) and value.startswith(("http://", "https://"))


def opportunity_schema_validator(fixture):
    """SCH-ATL-003."""
    opportunities = fixture.get("opportunities", [])
    run_ids = {r.run_id for r in fixture.get("runs", [])}
    person_ids = {p.person_id for p in fixture.get("persons", [])}
    findings = []
    for opp in opportunities:
        if opp.run_id not in run_ids:
            findings.append("Opportunity " + repr(opp.opportunity_id) + ": run_id does not resolve")
        if opp.channel != "reddit":
            findings.append("Opportunity " + repr(opp.opportunity_id) + ": channel is not reddit")
        if not _valid_url(opp.source_url):
            findings.append("Opportunity " + repr(opp.opportunity_id) + ": invalid URL")
        if not opp.author_handle or not str(opp.author_handle).strip():
            findings.append("Opportunity " + repr(opp.opportunity_id) + ": author handle missing")
        if not isinstance(opp.qualify_score, (int, float)) or not (0 <= opp.qualify_score <= 1):
            findings.append("Opportunity " + repr(opp.opportunity_id) + ": score out of range")
        if not opp.qualify_reason or not str(opp.qualify_reason).strip():
            findings.append("Opportunity " + repr(opp.opportunity_id) + ": reason empty")
        if opp.person_id is not None and opp.person_id not in person_ids:
            findings.append("Opportunity " + repr(opp.opportunity_id) + ": person_id does not resolve")
    return _result(
        "OpportunitySchemaValidator", _ids(opportunities, "opportunity_id"),
        not findings, findings, [],
    )


def draft_schema_validator(fixture):
    """SCH-ATL-004."""
    drafts = fixture.get("drafts", [])
    opportunity_ids = {o.opportunity_id for o in fixture.get("opportunities", [])}
    transitions = fixture.get("transitions", [])
    findings = []
    for draft in drafts:
        if draft.opportunity_id not in opportunity_ids:
            findings.append("Draft " + repr(draft.draft_id) + ": opportunity does not resolve")
        if not draft.body or not str(draft.body).strip():
            findings.append("Draft " + repr(draft.draft_id) + ": body empty")
        if not draft.channel or not str(draft.channel).strip():
            findings.append("Draft " + repr(draft.draft_id) + ": channel missing")
        if not _valid_url(draft.target_url):
            findings.append("Draft " + repr(draft.draft_id) + ": target URL invalid")
        if not draft.provider_used or not str(draft.provider_used).strip():
            findings.append("Draft " + repr(draft.draft_id) + ": provider missing")
        if draft.attribution_link is not None:
            findings.append("Draft " + repr(draft.draft_id) + ": v1 attribution must be null")
        if draft.state not in DRAFT_STATES:
            findings.append("Draft " + repr(draft.draft_id) + ": invalid state " + repr(draft.state))
    for transition in transitions:
        if transition.get("to") == "posted":
            findings.append("Draft " + repr(transition.get("draft_id")) + ": posted reached")
    return _result("DraftSchemaValidator", _ids(drafts, "draft_id"), not findings, findings, [])


def connection_schema_validator(fixture):
    """SCH-ATL-005."""
    connections = fixture.get("connections", [])
    findings = []
    for conn in connections:
        if conn.channel != "reddit":
            findings.append("Connection " + repr(conn.connection_id) + ": channel is not reddit")
        if conn.auth_kind != "script_credential":
            findings.append("Connection " + repr(conn.connection_id) + ": auth_kind invalid")
        if conn.status not in CONNECTION_STATUSES:
            findings.append("Connection " + repr(conn.connection_id) + ": invalid status")
    return _result(
        "ConnectionSchemaValidator", _ids(connections, "connection_id"),
        not findings, findings, [],
    )


def person_schema_validator(fixture):
    """SCH-ATL-006."""
    persons = fixture.get("persons", [])
    findings = []
    seen = set()
    for person in persons:
        if not person.person_id or person.person_id in seen:
            findings.append("Person ID missing or duplicated: " + repr(person.person_id))
        seen.add(person.person_id)
        if not isinstance(person.handles, list) or not person.handles:
            findings.append("Person " + repr(person.person_id) + ": no handles")
        if not person.first_seen:
            findings.append("Person " + repr(person.person_id) + ": first_seen missing")
        if not isinstance(person.interactions, list):
            findings.append("Person " + repr(person.person_id) + ": interactions not a list")
    return _result("PersonSchemaValidator", _ids(persons, "person_id"), not findings, findings, [])


def run_log_record_schema_validator(fixture):
    """SCH-ATL-007."""
    records = fixture.get("records", [])
    subject_ids = set(fixture.get("subjects", []))
    findings = []
    for record in records:
        if record.record_type not in LOG_RECORD_TYPES:
            findings.append("Record " + repr(record.record_id) + ": disallowed type")
        if record.subject_id not in subject_ids:
            findings.append("Record " + repr(record.record_id) + ": subject does not resolve")
        recomputed = compute_record_hash(
            record.record_id, record.record_type, record.recorded_at,
            record.subject_id, record.payload, record.prev_hash,
        )
        if recomputed != record.record_hash:
            findings.append("Record " + repr(record.record_id) + ": hash does not reproduce")
        if "signature" in record.payload:
            findings.append("Record " + repr(record.record_id) + ": signature field present")
    ok, linkage_findings = verify_log(records)
    findings.extend(linkage_findings)
    return _result(
        "RunLogRecordSchemaValidator", [r.record_id for r in records],
        not findings, findings, [],
    )


# ---------------------------------------------------------------------------
# Provider task boundary validators (WP-RL-002).
# ---------------------------------------------------------------------------

def provider_task_contract_validator(fixture):
    """REQ-ATL-012: one task contract per chat/qualify/compose, provider-independent."""
    task_contracts = fixture.get("task_contracts", {})
    provider_contracts = fixture.get("provider_contracts", [])
    findings = []
    target_ids = []
    for task_type in TASK_TYPES:
        target_ids.append(task_type)
        contract = task_contracts.get(task_type)
        if contract is None:
            findings.append("missing task contract for " + repr(task_type))
            continue
        input_shape = contract.get("input_shape")
        output_shape = contract.get("output_shape")
        if not isinstance(input_shape, list) or not input_shape:
            findings.append(task_type + ": missing or empty input_shape")
        if not isinstance(output_shape, list) or not output_shape:
            findings.append(task_type + ": missing or empty output_shape")
    if provider_contracts:
        findings.append(
            "provider-specific prompt contract present: " + repr(provider_contracts)
        )
    return _result(
        "ProviderTaskContractValidator", target_ids, not findings, findings, [],
    )


def provider_choice_validator(fixture):
    """REQ-ATL-013: distinct selectable providers; unavailable/invalid reported before execution."""
    providers = fixture.get("providers", [])
    availability = fixture.get("availability", {})
    selections = fixture.get("selections", [])
    findings = []
    if sorted(list(providers)) != sorted(list(PROVIDERS)):
        findings.append(
            "configured providers are not the three distinct choices: " + repr(providers)
        )
    for selection in selections:
        provider = selection.get("provider")
        started = bool(selection.get("started", False))
        reason = selection.get("reason")
        invocation = selection.get("invocation")
        if provider not in PROVIDERS:
            if started or invocation is not None:
                findings.append(
                    "invalid provider " + repr(provider) + " started execution"
                )
            elif not reason:
                findings.append(
                    "invalid provider " + repr(provider) + " reported without reason"
                )
            continue
        if not bool(availability.get(provider, False)):
            if started or invocation is not None:
                findings.append(
                    "unavailable provider " + repr(provider) + " started a false invocation"
                )
            if not reason:
                findings.append(
                    "unavailable provider " + repr(provider) + " reported without reason"
                )
        else:
            if started and invocation is None:
                findings.append(
                    "available provider " + repr(provider) + " started without invocation"
                )
    target_ids = [str(s.get("provider", "?")) for s in selections]
    return _result(
        "ProviderChoiceValidator", target_ids, not findings, findings, [],
    )


def provider_routing_validator(fixture):
    """REQ-ATL-014: per-task mapping applied without substitution; actual provider recorded."""
    routing = fixture.get("routing", {})
    dispatches = fixture.get("dispatches", [])
    findings = []
    for dispatch in dispatches:
        task_type = dispatch.get("task_type")
        requested = dispatch.get("provider_requested")
        used = dispatch.get("provider_used")
        evidence = dispatch.get("evidence") or {}
        expected = routing.get(task_type)
        if expected is None:
            findings.append("no routing mapping for task " + repr(task_type))
        elif requested != expected:
            findings.append(
                "dispatch for " + repr(task_type) + " requested " + repr(requested)
                + " but mapping requires " + repr(expected)
            )
        if used != requested:
            findings.append(
                "dispatch for " + repr(task_type) + " substituted provider "
                + repr(used) + " for requested " + repr(requested)
            )
        if evidence.get("provider") != used:
            findings.append(
                "dispatch for " + repr(task_type) + " evidence provider "
                + repr(evidence.get("provider")) + " differs from used " + repr(used)
            )
    target_ids = [str(d.get("task_type", "?")) for d in dispatches]
    return _result(
        "ProviderRoutingValidator", target_ids, not findings, findings, [],
    )


def provider_failure_validator(fixture):
    """REQ-ATL-015: truthful failure; no silent provider change or substituted result."""
    failures = fixture.get("failures", [])
    findings = []
    for failure in failures:
        requested = failure.get("provider_requested")
        status = failure.get("status")
        reason = failure.get("failure_reason")
        result_ref = failure.get("result_ref")
        provider_used = failure.get("provider_used")
        substituted_result = failure.get("substituted_result")
        if status != "failed":
            findings.append(
                "requested " + repr(requested) + ": status is " + repr(status)
                + ", expected failed"
            )
        if not reason or not str(reason).strip():
            findings.append("requested " + repr(requested) + ": missing failure reason")
        if result_ref is not None:
            findings.append(
                "requested " + repr(requested) + ": conforming result present despite failure"
            )
        if provider_used not in (None, requested):
            findings.append(
                "requested " + repr(requested) + ": silently changed provider to "
                + repr(provider_used)
            )
        if substituted_result:
            findings.append(
                "requested " + repr(requested)
                + ": substituted result from another provider present"
            )
    target_ids = [str(f.get("provider_requested", "?")) for f in failures]
    return _result(
        "ProviderFailureValidator", target_ids, not findings, findings, [],
    )


def provider_swap_gate_validator(fixture):
    """REQ-ATL-016: 20 candidate verdicts + 10 voice-judged drafts gate activation."""
    golden_set = fixture.get("golden_set", {})
    activation = fixture.get("activation", {})
    findings = []
    verdicts = golden_set.get("candidate_verdicts", [])
    drafts = golden_set.get("voice_judged_drafts", [])
    activated = bool(activation.get("activated", False))
    mismatched = [v.get("id", "?") for v in verdicts if not v.get("match", False)]
    failing_drafts = [d.get("id", "?") for d in drafts if not d.get("passes", False)]
    sufficient = (
        len(verdicts) >= 20
        and len(drafts) >= 10
        and not mismatched
        and not failing_drafts
    )
    if activated != sufficient:
        if activated:
            findings.append("activation allowed without sufficient golden-set evidence")
        else:
            findings.append("activation blocked despite sufficient golden-set evidence")
    target_ids = [str(activation.get("provider", "activation"))]
    return _result(
        "ProviderSwapGateValidator", target_ids, not findings, findings, [],
    )


def provider_invocation_schema_validator(fixture):
    """SCH-ATL-008."""
    invocations = fixture.get("invocations", [])
    input_refs = set(fixture.get("input_refs", []))
    result_refs = set(fixture.get("result_refs", []))
    findings = []
    for inv in invocations:
        iid = inv.invocation_id
        if inv.task_type not in TASK_TYPES:
            findings.append("invocation " + repr(iid) + ": invalid task_type " + repr(inv.task_type))
        if inv.provider_requested not in PROVIDERS:
            findings.append("invocation " + repr(iid) + ": invalid provider_requested")
        if inv.provider_used is not None and inv.provider_used not in PROVIDERS:
            findings.append("invocation " + repr(iid) + ": invalid provider_used")
        if inv.input_ref not in input_refs:
            findings.append("invocation " + repr(iid) + ": input_ref does not resolve")
        if inv.result_ref is not None and inv.result_ref not in result_refs:
            findings.append("invocation " + repr(iid) + ": result_ref does not resolve")
        if inv.status not in INVOCATION_STATUSES:
            findings.append("invocation " + repr(iid) + ": invalid status " + repr(inv.status))
        if inv.status == "succeeded":
            if inv.result_ref is None:
                findings.append("invocation " + repr(iid) + ": succeeded without result_ref")
            if inv.provider_used is None:
                findings.append("invocation " + repr(iid) + ": succeeded without provider_used")
            elif inv.provider_used != inv.provider_requested:
                findings.append("invocation " + repr(iid) + ": succeeded with substituted provider")
            if inv.finished_at is None:
                findings.append("invocation " + repr(iid) + ": succeeded without finished_at")
        elif inv.status == "running":
            if inv.finished_at is not None:
                findings.append("invocation " + repr(iid) + ": running claims a finish")
            if inv.failure_reason is not None:
                findings.append("invocation " + repr(iid) + ": running has a failure_reason")
        elif inv.status == "failed":
            if not inv.failure_reason or not str(inv.failure_reason).strip():
                findings.append("invocation " + repr(iid) + ": failed without failure_reason")
            if inv.result_ref is not None:
                findings.append("invocation " + repr(iid) + ": failed with conforming result_ref")
        if inv.finished_at is not None and inv.finished_at < inv.started_at:
            findings.append("invocation " + repr(iid) + ": finished before started")
    target_ids = [str(inv.invocation_id) for inv in invocations]
    return _result(
        "ProviderInvocationSchemaValidator", target_ids, not findings, findings, [],
    )


ALL_VALIDATORS = {
    "AgentAtomValidator": agent_atom_validator,
    "BriefOnlyAuthoringValidator": brief_only_authoring_validator,
    "BriefInterpretationValidator": brief_interpretation_validator,
    "AgentLifecycleValidator": agent_lifecycle_validator,
    "RunAccountingValidator": run_accounting_validator,
    "ResignableRunLogValidator": resignable_run_log_validator,
    "AttestationDropValidator": attestation_drop_validator,
    "SingleOperatorBoundaryValidator": single_operator_boundary_validator,
    "AgentSchemaValidator": agent_schema_validator,
    "RunSchemaValidator": run_schema_validator,
    "OpportunitySchemaValidator": opportunity_schema_validator,
    "DraftSchemaValidator": draft_schema_validator,
    "ConnectionSchemaValidator": connection_schema_validator,
    "PersonSchemaValidator": person_schema_validator,
    "RunLogRecordSchemaValidator": run_log_record_schema_validator,
}


def run_validator_suite(fixtures):
    """Run every WP-RL-001 validator against its supplied fixture."""
    results = {}
    for name, validator in ALL_VALIDATORS.items():
        if name not in fixtures:
            results[name] = _result(name, [], False, ["missing usable input"], [])
            continue
        results[name] = validator(fixtures[name])
    return results


PROVIDER_VALIDATORS = {
    "ProviderTaskContractValidator": provider_task_contract_validator,
    "ProviderChoiceValidator": provider_choice_validator,
    "ProviderRoutingValidator": provider_routing_validator,
    "ProviderFailureValidator": provider_failure_validator,
    "ProviderSwapGateValidator": provider_swap_gate_validator,
    "ProviderInvocationSchemaValidator": provider_invocation_schema_validator,
}


def run_provider_validator_suite(fixtures):
    """Run every WP-RL-002 provider validator against its supplied fixture."""
    results = {}
    for name, validator in PROVIDER_VALIDATORS.items():
        if name not in fixtures:
            results[name] = _result(name, [], False, ["missing usable input"], [])
            continue
        results[name] = validator(fixtures[name])
    return results


# ---------------------------------------------------------------------------
# Live-Agent scheduling validators (WP-RL-003).
# ---------------------------------------------------------------------------

ALLOWED_AUTONOMOUS_TASKS = ("scan", "qualify", "draft", "report")


def scheduled_run_validator(fixture):
    """REQ-ATL-005: a due schedule yields exactly one attributable Run; an
    early, duplicate, paused, draft, or disabled trigger yields none."""
    agents = fixture.get("agents", [])
    triggers = fixture.get("triggers", [])
    existing_runs = fixture.get("existing_runs", [])
    now = fixture.get("now")
    outcome = fixture.get("outcome")
    if outcome is None:
        outcome = evaluate_schedule(agents, triggers, existing_runs, now)
    admitted = list(outcome.admitted)
    agent_by_id = {a.agent_id: a for a in agents}
    covered = {(r.agent_id, r.started_at) for r in existing_runs}
    findings = []
    admitted_occurrences = set()
    for trigger in triggers:
        occurrence = (trigger.agent_id, trigger.due_at)
        eligible = (
            bool(trigger.enabled)
            and agent_by_id.get(trigger.agent_id) is not None
            and agent_by_id[trigger.agent_id].state == "live"
            and trigger.due_at <= now
            and occurrence not in covered
            and occurrence not in admitted_occurrences
        )
        if eligible:
            admitted_occurrences.add(occurrence)
        matching = [
            r for r in admitted
            if r.agent_id == trigger.agent_id and r.started_at == trigger.due_at
        ]
        if eligible and len(matching) != 1:
            findings.append(
                "trigger " + repr(trigger.trigger_id) + ": expected exactly one Run, "
                "got " + str(len(matching))
            )
        if not eligible and matching:
            findings.append(
                "trigger " + repr(trigger.trigger_id) + ": ineligible but produced a Run"
            )
    for run in admitted:
        agent = agent_by_id.get(run.agent_id)
        if agent is None or agent.state != "live":
            findings.append(
                "admitted Run " + repr(run.run_id) + " not attributable to a live Agent"
            )
    return _result(
        "ScheduledRunValidator",
        [t.trigger_id for t in triggers],
        not findings, findings, [],
    )


def run_budget_validator(fixture):
    """REQ-ATL-011: a Run exposes no more than the per-run surfaced-opportunity
    and draft budgets, even when excess candidates are available."""
    items = fixture.get("runs", [])
    findings = []
    target_ids = []
    for item in items:
        run = item["run"]
        budget = item.get("budget") or default_budget()
        target_ids.append(run.run_id)
        max_surfaced = budget.get("max_surfaced_per_run")
        max_drafts = budget.get("max_drafts_per_run")
        if isinstance(max_surfaced, int) and run.candidates_qualified > max_surfaced:
            findings.append(
                "Run " + repr(run.run_id) + ": surfaced "
                + str(run.candidates_qualified) + " exceeds max " + str(max_surfaced)
            )
        if isinstance(max_drafts, int) and run.drafts_produced > max_drafts:
            findings.append(
                "Run " + repr(run.run_id) + ": drafts " + str(run.drafts_produced)
                + " exceeds max " + str(max_drafts)
            )
    return _result("RunBudgetValidator", target_ids, not findings, findings, [])


def autonomy_boundary_validator(fixture):
    """REQ-ATL-021: unattended work is limited to scan/qualify/draft/report; no
    outward task is eligible from an unapproved Draft."""
    tasks = fixture.get("tasks", [])
    drafts = fixture.get("drafts", [])
    outward_attempts = fixture.get("outward_attempts", [])
    findings = []
    target_ids = []
    for task in tasks:
        name = task.get("name")
        target_ids.append(str(name))
        if task.get("autonomous") and name not in ALLOWED_AUTONOMOUS_TASKS:
            findings.append("autonomous task outside internal set: " + repr(name))
    for draft in drafts:
        if draft.get("outward_eligible") and draft.get("state") != "approved":
            findings.append(
                "outward task eligible from unapproved Draft "
                + repr(draft.get("draft_id"))
            )
    for attempt in outward_attempts:
        findings.append("outward task attempted: " + repr(attempt))
    return _result("AutonomyBoundaryValidator", target_ids, not findings, findings, [])


def cadence_default_validator(fixture):
    """REQ-ATL-030: weekday 09:00 schedule with 5 surfaced and 3 drafts by
    default; operator changes persist in allowed fields and affect later Runs."""
    defaults = fixture.get("defaults", {})
    agents = fixture.get("agents", [])
    operator_changes = fixture.get("operator_changes", [])
    findings = []
    target_ids = [a.agent_id for a in agents]
    ds = default_schedule()
    db = default_budget()
    if defaults.get("schedule") != ds:
        findings.append(
            "default schedule diverges: " + repr(defaults.get("schedule"))
        )
    if defaults.get("budget") != db:
        findings.append("default budget diverges: " + repr(defaults.get("budget")))
    if (
        ds.get("cadence") != "weekly"
        or ds.get("time") != "09:00"
        or sorted(ds.get("days", [])) != ["fri", "mon", "thu", "tue", "wed"]
    ):
        findings.append("weekday 09:00 default schedule not met: " + repr(ds))
    if db.get("max_surfaced_per_run") != 5 or db.get("max_drafts_per_run") != 3:
        findings.append("default budget is not 5 surfaced / 3 drafts: " + repr(db))
    agent_by_id = {a.agent_id: a for a in agents}
    for change in operator_changes:
        if not change.get("persisted"):
            findings.append(
                "operator change not persisted for " + repr(change.get("agent_id"))
            )
            continue
        agent = agent_by_id.get(change.get("agent_id"))
        if agent is None:
            findings.append(
                "operator change references missing Agent " + repr(change.get("agent_id"))
            )
            continue
        field = change.get("field")
        after = change.get("after")
        if getattr(agent, field, None) != after:
            findings.append(
                "operator change for " + repr(change.get("agent_id")) + "." + repr(field)
                + " not reflected (observed " + repr(getattr(agent, field, None))
                + ", expected " + repr(after) + ")"
            )
    return _result("CadenceDefaultValidator", target_ids, not findings, findings, [])


WP_RL_003_VALIDATORS = {
    "ScheduledRunValidator": scheduled_run_validator,
    "RunBudgetValidator": run_budget_validator,
    "AutonomyBoundaryValidator": autonomy_boundary_validator,
    "CadenceDefaultValidator": cadence_default_validator,
}


def run_wp_rl_003_validator_suite(fixtures):
    """Run every WP-RL-003 scheduling validator against its supplied fixture."""
    results = {}
    for name, validator in WP_RL_003_VALIDATORS.items():
        if name not in fixtures:
            results[name] = _result(name, [], False, ["missing usable input"], [])
            continue
        results[name] = validator(fixtures[name])
    return results
