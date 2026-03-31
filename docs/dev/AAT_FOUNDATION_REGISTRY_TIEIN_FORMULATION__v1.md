# AAT/Foundation Policy Registry Tie-In Formulation v1

## Objective
Determine if a bounded artifact can map Gate C outputs to Foundation v0 policy-registry entries (making the AAT/Foundation convergence candidate distinct) or whether no such mapping exists yet.

## Baseline
- Gate C/operator-path baseline (stage -> shim -> Gate C) is treated as already consumed on current main by later planning surfaces, but no current-main `TASK_401` artifact path exists.
- Canon repair signals that the next work should be formulation, not implementation, and that convergence must produce new artifacts, not rehash existing ones (`docs/dev/GOVCORE_DESIGN_BACKLOG_EXTRACTION__v1.md`, `docs/dev/AAT_FOUNDATION_CONVERGENCE_FORMULATION__v1.md`).
- Current repo contains Gate C outputs (`mcp/aat` scripts, `foundation` policy specs) but no explicit mapping manifest or registry extension tying them together.

## Candidate Mapping Artifact Shape
- Hypothetical artifact: a JSON manifest or registry extension listing Gate C outcome codes, policy entry identifiers, and revision constraints, e.g., `foundation/policy_registry_tiein.json` or `foundation/policy_registry_extension.yaml`.
- Participating surfaces would include:
  - existing Gate C outcome constants (`aat/gate_c.py` or similar)
  - Foundation v0 registry definitions (`foundation/policies.yaml`, `foundation/registry.py`)
  - Shim metadata and admissibility documentation for how Gate C decisions relate to policy qualifications.

## Distinctness Test
- Does such an artifact already exist? No canonical file defines a Gate C→registry mapping; current surfaces only record Gate C outputs and Foundation entries separately.  
- If a new manifest is introduced, it must not simply restate Gate C outputs or registry entries—it must define the actual linking structure; otherwise the candidate collapses into consumed Gate C work.
- Retry the tie-in only if the manifest is bounded, machine-readable, and explicitly used by both sides; absent that, the candidate is **NOT DISTINCT ENOUGH**.

## Operator-Facing Value
- A mapping manifest would give operators a single authoritative reference showing which policy entries Gate C enforces, enabling faster audit and convergence verification.

## Acceptance Proof Concept
- Show that Gate C decision records reference the registry manifest (e.g., include `policy_registry_id` and `policy_revision`) and that Foundation validation tools consume the same manifest to approve admissibility. Tests would assert consistent mapping entries survive through Gate C logs and policy enforcement.

## Conclusion
- **NOT DISTINCT ENOUGH.** No concrete manifest or registry extension currently exists, and inventing one would duplicate consumed Gate C semantics unless a bounded artifact is defined.  
- Candidate collapses into reinterpretation of existing outputs rather than a new convergence surface.  
- Next control step: keep monitoring for a concrete mapping artifact request; once surfaced, perform a bounded formulation pass with the actual registry-manifest spec.

## Evidence That Would Overturn This
- Emergence of a canonical file/extension (e.g., `foundation/policy_registry_tiein.json`) that is referenced by both Gate C logging and Foundation enforcement, proving the mapping is needed and distinct.  
- Operator demand for a record that ties Gate C outcomes to registry entries, ideally with example mappings already sketched in repo docs or artifact.  
- A merge landing a new artifact describing this tie-in without already consuming it.
