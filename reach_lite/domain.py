"""Domain records and pure helpers for the Reach Lite walking skeleton.

Records are plain, serializable dataclasses. Validation is performed by the
validator module, not by constructors, so conforming and invalid fixtures are
both representable and testable. The walking skeleton makes no cryptographic
claim: the run log uses a plain SHA-256 content hash for predecessor linkage
only, carries no signature field, and exposes no verifier interface.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from typing import Any, Callable, Sequence

# ---------------------------------------------------------------------------
# Enumerated vocabularies (single source of truth for all later packages).
# ---------------------------------------------------------------------------

AGENT_STATES = ("draft", "live", "paused")
AGENT_ACTIONS = ("draft_reply",)
AGENT_MODES = ("ask", "auto")
CADENCES = ("hourly", "daily", "weekly")

RUN_STATUSES = ("running", "succeeded", "failed", "cancelled")

DRAFT_STATES = ("pending", "approved", "edited", "rejected", "posted")

CONNECTION_STATUSES = ("connected", "expired", "invalid", "unavailable")

LOG_RECORD_TYPES = ("run", "opportunity", "draft", "approval", "post")

GENESIS_MARKER = "genesis"

# Provider task boundary (WP-RL-002): one contract per task type, independent
# of the selected provider, plus the per-provider routing vocabulary.
TASK_TYPES = ("chat", "qualify", "compose")
PROVIDERS = ("codex", "deepclaude", "local")
INVOCATION_STATUSES = ("running", "succeeded", "failed")

# Discarded first-class pipeline surface names; none may be exposed.
PIPELINE_STAGE_NAMES = tuple(
    ["decision_pipeline", "pipeline", "pattern_editor", "policy_editor",
     "scaffold_editor", "signal_registry", "iteration"]
    + [f"stage{n}" for n in range(1, 16)]
)

PROHIBITED_ATTESTATION_CAPABILITIES = (
    "signing_keys",
    "signatures",
    "signature_verification",
    "chain_integrity",
    "chain_index",
    "verifier_interface",
)

CRYPTO_CLAIM_MARKERS = (
    "cryptographically",
    "cryptographic",
    "signed",
    "signature",
    "verified chain",
    "chain integrity",
    "attestation",
    "verifier",
)

PROHIBITED_OPERATOR_CONTROLS = (
    "authentication",
    "billing",
    "subscriptions",
    "organizations",
    "tenant_isolation",
    "multi_tenant",
    "payments",
)


# ---------------------------------------------------------------------------
# Records.
# ---------------------------------------------------------------------------

@dataclass
class Agent:
    agent_id: str
    brief_text: str
    schedule: dict[str, Any]
    sources: list[dict[str, Any]]
    qualifier: dict[str, str]
    action: str
    mode: str
    budget: dict[str, int]
    state: str


@dataclass
class Run:
    run_id: str
    agent_id: str
    started_at: str
    finished_at: str | None
    sources_polled: list[Any]
    candidates_seen: int
    candidates_qualified: int
    drafts_produced: int
    provider_used: str
    token_cost: int | None
    status: str


@dataclass
class Opportunity:
    opportunity_id: str
    run_id: str
    channel: str
    source_url: str
    author_handle: str
    excerpt: str
    qualify_score: float
    qualify_reason: str
    person_id: str | None


@dataclass
class Draft:
    draft_id: str
    opportunity_id: str
    body: str
    channel: str
    target_url: str
    provider_used: str
    attribution_link: str | None
    state: str


@dataclass
class Connection:
    connection_id: str
    channel: str
    auth_kind: str
    scopes: list[str]
    status: str
    expires_at: str | None


@dataclass
class Person:
    person_id: str
    handles: list[dict[str, Any]]
    first_seen: str
    interactions: list[dict[str, Any]]
    notes: str


@dataclass
class RunLogRecord:
    record_id: str
    record_type: str
    recorded_at: str
    subject_id: str
    payload: dict[str, Any]
    prev_hash: str
    record_hash: str


@dataclass
class ProviderTaskInvocation:
    invocation_id: str
    task_type: str
    provider_requested: str
    provider_used: str | None
    input_ref: str
    result_ref: str | None
    started_at: str
    finished_at: str | None
    status: str
    failure_reason: str | None


# ---------------------------------------------------------------------------
# Defaults and construction helpers.
# ---------------------------------------------------------------------------

def default_schedule() -> dict[str, Any]:
    """Weekday 09:00 weekly cadence (REQ-ATL-030 default)."""
    return {"cadence": "weekly", "days": ["mon", "tue", "wed", "thu", "fri"], "time": "09:00"}


def default_budget() -> dict[str, int]:
    """Five surfaced opportunities, three drafts per run (REQ-ATL-030 default)."""
    return {"max_surfaced_per_run": 5, "max_drafts_per_run": 3}


def new_agent(
    agent_id: str,
    brief_text: str,
    sources: list[dict[str, Any]],
    qualifier: dict[str, str],
    *,
    mode: str = "ask",
) -> Agent:
    """Build a defaulted draft Agent from a brief plus required selections."""
    return Agent(
        agent_id=agent_id,
        brief_text=brief_text,
        schedule=default_schedule(),
        sources=sources,
        qualifier=qualifier,
        action="draft_reply",
        mode=mode,
        budget=default_budget(),
        state="draft",
    )


def transition_agent(agent: Agent, new_state: str) -> Agent | None:
    """Apply an allowed lifecycle transition, or return None when invalid."""
    if new_state not in AGENT_STATES:
        return None
    return replace(agent, state=new_state)


# ---------------------------------------------------------------------------
# Brief interpretation (REQ-ATL-003).
# ---------------------------------------------------------------------------

_TIME_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", re.IGNORECASE)
_SOURCE_RE = re.compile(r"r/[A-Za-z0-9_]+")

_INCLUDE_STOPS = (" exclude ", " draft ", " maximum ", " budget ", " qualify ")
_EXCLUDE_STOPS = (" draft ", " maximum ", " budget ", " qualify ")


def _between(text: str, start_kw: str, stop_kws: tuple[str, ...]) -> str:
    start = text.find(start_kw)
    if start < 0:
        return ""
    start += len(start_kw)
    stops = [p for p in (text.find(kw, start) for kw in stop_kws) if p >= start]
    stop = min(stops) if stops else len(text)
    return text[start:stop].strip(" .\t\n")


def interpret_brief(brief_text: str) -> tuple[dict[str, Any], list[str]]:
    """Map a plain-English brief to Agent values, reporting (not inventing)
    any required value that cannot be derived. Action is fixed at draft_reply
    in v1; budget uses the spec default unless the brief states otherwise.
    """
    text = brief_text.lower()
    clarifications: list[str] = []

    # Schedule.
    cadence: str | None = None
    if "weekday" in text or "weekdays" in text or "week days" in text:
        cadence = "weekly"
    elif "daily" in text or "every day" in text:
        cadence = "daily"
    elif "hourly" in text or "every hour" in text:
        cadence = "hourly"

    schedule: dict[str, Any] | None = None
    if cadence is None:
        clarifications.append("schedule cadence not specified")
    else:
        if cadence == "hourly":
            schedule = {"cadence": "hourly"}
        else:
            time_match = _TIME_RE.search(text)
            if time_match is None:
                clarifications.append("schedule time not specified")
                schedule = None
            else:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2) or 0)
                suffix = (time_match.group(3) or "").lower()
                if suffix == "pm" and hour != 12:
                    hour += 12
                if suffix == "am" and hour == 12:
                    hour = 0
                schedule = {"cadence": cadence, "time": f"{hour:02d}:{minute:02d}"}
                if cadence == "weekly":
                    schedule["days"] = ["mon", "tue", "wed", "thu", "fri"]

    # Sources (extracted from the original text to preserve operator casing).
    sources = [{"kind": "subreddit", "value": s} for s in _SOURCE_RE.findall(brief_text)]
    if not sources:
        clarifications.append("no Reddit source specified")

    # Qualification and exclusion intent.
    include = _between(text, "qualify ", _INCLUDE_STOPS)
    exclude = _between(text, "exclude ", _EXCLUDE_STOPS)
    if not include:
        clarifications.append("qualification intent not specified")

    # Budget (digits or number words; default otherwise, REQ-ATL-030).
    _NUMBER_WORDS = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    }
    _COUNT = r"(?:\d+|" + "|".join(_NUMBER_WORDS) + r")"

    def _count(text: str, noun: str) -> int | None:
        match = re.search(
            r"(?:maximum of\s+|max(?:imum)?\s+)?(" + _COUNT + r")\s+" + noun,
            text,
        )
        if match is None:
            return None
        token = match.group(1)
        return int(token) if token.isdigit() else _NUMBER_WORDS[token]

    max_drafts = _count(text, "drafts?")
    max_surfaced = _count(text, "surfaced")

    budget = {
        "max_surfaced_per_run": (
            max_surfaced if max_surfaced is not None else default_budget()["max_surfaced_per_run"]
        ),
        "max_drafts_per_run": (
            max_drafts if max_drafts is not None else default_budget()["max_drafts_per_run"]
        ),
    }

    values = {
        "schedule": schedule,
        "sources": sources,
        "qualifier": {"include": include, "exclude": exclude},
        "action": "draft_reply",
        "budget": budget,
    }
    return values, clarifications


# ---------------------------------------------------------------------------
# Unsigned predecessor-linked run log (REQ-ATL-028, REQ-ATL-029, SCH-ATL-007).
# ---------------------------------------------------------------------------

def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_record_hash(
    record_id: str,
    record_type: str,
    recorded_at: str,
    subject_id: str,
    payload: dict[str, Any],
    prev_hash: str,
) -> str:
    """Content hash over every declared field except the hash itself."""
    content = _canonical(
        {
            "record_id": record_id,
            "record_type": record_type,
            "recorded_at": recorded_at,
            "subject_id": subject_id,
            "payload": payload,
            "prev_hash": prev_hash,
        }
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def append_record(
    chain: list[RunLogRecord],
    *,
    record_id: str,
    record_type: str,
    recorded_at: str,
    subject_id: str,
    payload: dict[str, Any],
) -> list[RunLogRecord]:
    """Append one unsigned record with predecessor-hash linkage."""
    prev_hash = chain[-1].record_hash if chain else GENESIS_MARKER
    record_hash = compute_record_hash(
        record_id, record_type, recorded_at, subject_id, payload, prev_hash
    )
    return chain + [
        RunLogRecord(
            record_id=record_id,
            record_type=record_type,
            recorded_at=recorded_at,
            subject_id=subject_id,
            payload=payload,
            prev_hash=prev_hash,
            record_hash=record_hash,
        )
    ]


def verify_log(chain: list[RunLogRecord]) -> tuple[bool, list[str]]:
    """Recompute hashes and check genesis/predecessor linkage."""
    findings: list[str] = []
    expected_prev = GENESIS_MARKER
    for index, record in enumerate(chain):
        recomputed = compute_record_hash(
            record.record_id,
            record.record_type,
            record.recorded_at,
            record.subject_id,
            record.payload,
            record.prev_hash,
        )
        if recomputed != record.record_hash:
            findings.append(
                f"record {index}: hash mismatch (observed {record.record_hash!r}, "
                f"expected {recomputed!r})"
            )
        if record.prev_hash != expected_prev:
            findings.append(
                f"record {index}: predecessor mismatch (observed {record.prev_hash!r}, "
                f"expected {expected_prev!r})"
            )
        expected_prev = record.record_hash
    return (not findings), findings


# ---------------------------------------------------------------------------
# Live-Agent scheduling and internal Run orchestration (WP-RL-003).
# ---------------------------------------------------------------------------

@dataclass
class ScheduleTrigger:
    """One occurrence of an Agent schedule that may admit a Run.

    A disabled trigger (operator turned a schedule off) never admits a Run;
    an enabled trigger admits a Run only when its Agent is live, the
    occurrence is due (due_at <= now), and no Run already covers it.
    """

    trigger_id: str
    agent_id: str
    due_at: str
    enabled: bool = True


@dataclass
class ScheduleOutcome:
    """Result of evaluating a batch of schedule occurrences."""

    admitted: list  # list[Run]
    skipped: list  # list[dict] with trigger_id and reason


def evaluate_schedule(agents, triggers, existing_runs, now):
    """Turn each eligible live-Agent schedule occurrence into exactly one
    attributable, budget-bounded internal Run.

    Eligibility requires, in order: the trigger is enabled; the referenced
    Agent exists and is live; the occurrence is due (not early); and no Run
    already covers the same occurrence (not duplicate). Ineligible
    occurrences produce no Run and are reported with a reason.
    """
    agent_by_id = {a.agent_id: a for a in agents}
    covered = {(r.agent_id, r.started_at) for r in existing_runs}
    admitted: list = []
    skipped: list = []
    admitted_occurrences: set = set()
    for trigger in triggers:
        occurrence = (trigger.agent_id, trigger.due_at)
        reason: str | None = None
        if not trigger.enabled:
            reason = "disabled"
        agent = agent_by_id.get(trigger.agent_id)
        if reason is None and (agent is None or agent.state != "live"):
            reason = "not_live"
        if reason is None and trigger.due_at > now:
            reason = "early"
        if reason is None and occurrence in covered:
            reason = "duplicate"
        if reason is None and occurrence in admitted_occurrences:
            reason = "duplicate"
        if reason is not None:
            skipped.append({"trigger_id": trigger.trigger_id, "reason": reason})
            continue
        admitted_occurrences.add(occurrence)
        admitted.append(
            Run(
                run_id="run-" + trigger.trigger_id,
                agent_id=trigger.agent_id,
                started_at=trigger.due_at,
                finished_at=None,
                sources_polled=list(agent.sources),
                candidates_seen=0,
                candidates_qualified=0,
                drafts_produced=0,
                provider_used="",
                token_cost=None,
                status="running",
            )
        )
    return ScheduleOutcome(admitted=admitted, skipped=skipped)


# ---------------------------------------------------------------------------
# Reddit discovery and brief-driven qualification (WP-RL-004).
# ---------------------------------------------------------------------------

def authorized_source_keys(agent: Agent) -> set[tuple[str, str]]:
    """Return the set of (kind, value) source identities an Agent authorizes."""
    keys: set[tuple[str, str]] = set()
    for source in agent.sources:
        if isinstance(source, dict) and source.get("value"):
            keys.add((source.get("kind"), source["value"]))
    return keys


def retrieve_authorized_candidates(
    agent: Agent, candidates: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Retrieve only candidates whose source is Agent-authorized, retaining
    source identity and URL (REQ-ATL-007)."""
    keys = authorized_source_keys(agent)
    return [
        candidate
        for candidate in candidates
        if (candidate.get("source") or {}).get("value") is not None
        and ((candidate.get("source") or {}).get("kind"), (candidate.get("source") or {}).get("value"))
        in keys
    ]


def deduplicate_candidates(
    candidates: Sequence[dict[str, Any]],
    key: Callable[[dict[str, Any]], Any] | None = None,
) -> list[dict[str, Any]]:
    """Surface each candidate identity at most once per Agent while keeping a
    distinct later interaction (a distinct identity) representable
    (REQ-ATL-008)."""
    seen: set[Any] = set()
    out: list[dict[str, Any]] = []
    for candidate in candidates:
        identity = key(candidate) if key is not None else candidate.get("url")
        if identity in seen:
            continue
        seen.add(identity)
        out.append(candidate)
    return out


def qualify_candidate(
    candidate: dict[str, Any], qualifier: dict[str, str]
) -> dict[str, Any]:
    """Apply the brief's inclusion/exclusion intent to one candidate and return
    a deterministic verdict with a score and prose reason (REQ-ATL-009)."""
    text = (candidate.get("excerpt") or "").lower()
    include = (qualifier.get("include") or "").lower()
    exclude = (qualifier.get("exclude") or "").lower()
    include_terms = [t for t in re.split(r"[\s,;]+", include) if t]
    exclude_terms = [t for t in re.split(r"[\s,;]+", exclude) if t]
    if exclude_terms and any(t in text for t in exclude_terms):
        return {
            "verdict": "excluded",
            "score": 0.0,
            "reason": "matches exclusion intent: " + qualifier.get("exclude", ""),
        }
    if include_terms:
        matched = [t for t in include_terms if t in text]
        if matched:
            score = round(len(matched) / len(include_terms), 4)
            return {
                "verdict": "included",
                "score": score,
                "reason": "matches inclusion intent: " + qualifier.get("include", ""),
            }
    return {"verdict": "excluded", "score": 0.0, "reason": "no inclusion or exclusion match"}


def qualify_candidates(
    candidates: Sequence[dict[str, Any]], qualifier: dict[str, str]
) -> list[dict[str, Any]]:
    """Return the candidates that qualify (are included) under the brief."""
    return [
        candidate
        for candidate in candidates
        if qualify_candidate(candidate, qualifier)["verdict"] == "included"
    ]
