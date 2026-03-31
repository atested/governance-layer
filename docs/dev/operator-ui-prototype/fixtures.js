export const approvals = [
  {
    id: "APR-100",
    artifactIdentity: "artifact://governed-action/ACT-204/policy-bundle",
    family: "policy_bundle",
    approvalBasis: "Manual operator confirmation after judgment review",
    approvedBy: "gkeeter",
    approvedAt: "2026-03-14T14:20:00Z",
    status: "active",
    originatingActionId: "ACT-204",
    revocationHistory: []
  },
  {
    id: "APR-101",
    artifactIdentity: "artifact://governed-action/ACT-207/exception-grant",
    family: "exception_grant",
    approvalBasis: "Temporary exception for judgment-only edge case",
    approvedBy: "ops-reviewer-2",
    approvedAt: "2026-03-10T09:12:00Z",
    status: "revoked",
    originatingActionId: "ACT-207",
    revocationHistory: [
      {
        revokedAt: "2026-03-15T11:04:00Z",
        revokedBy: "ops-reviewer-2",
        reason: "Exception no longer needed after policy update"
      }
    ]
  }
];

export const actions = [
  {
    id: "ACT-101",
    title: "Filesystem write baseline",
    family: "filesystem",
    type: "FS_WRITE",
    disposition: "completed",
    governanceResponseSummary: "Auto-allow completed in one pass",
    timestamps: {
      openedAt: "2026-03-20T09:00:00Z",
      updatedAt: "2026-03-20T09:06:00Z"
    },
    attempts: [
      {
        id: "ATT-1",
        startedAt: "2026-03-20T09:00:00Z",
        finishedAt: "2026-03-20T09:06:00Z",
        summary: "Single deterministic pass",
        outcome: "completed",
        steps: [
          {
            id: "STEP-1",
            timestamp: "2026-03-20T09:01:00Z",
            label: "Determined",
            governanceResponse: "Capability policy matched",
            result: "allow",
            evidence: {
              requestType: "FS_WRITE",
              targetPath: "/workspace/reports/daily.txt",
              policyRecord: "POL-12"
            },
            keyChange: "Policy matched on first evaluation"
          },
          {
            id: "STEP-2",
            timestamp: "2026-03-20T09:04:00Z",
            label: "Determined",
            governanceResponse: "Write executed",
            result: "completed",
            evidence: {
              bytesWritten: 1842,
              postCheck: "hash recorded"
            },
            keyChange: "Completed without escalation"
          }
        ]
      }
    ]
  },
  {
    id: "ACT-204",
    title: "Policy bundle exception review",
    family: "policy_bundle",
    type: "BUNDLE_OVERRIDE",
    judgmentCategory: "Escalation justified",
    disposition: "approved_with_judgment",
    governanceResponseSummary: "Judgment path approved after operator review",
    timestamps: {
      openedAt: "2026-03-14T13:55:00Z",
      updatedAt: "2026-03-14T14:24:00Z"
    },
    attempts: [
      {
        id: "ATT-1",
        startedAt: "2026-03-14T13:55:00Z",
        finishedAt: "2026-03-14T14:12:00Z",
        summary: "Initial pass escalated for judgment",
        outcome: "judgment_required",
        steps: [
          {
            id: "STEP-1",
            timestamp: "2026-03-14T13:57:00Z",
            label: "Determined",
            governanceResponse: "Opaque-path routing invoked",
            result: "escalated",
            evidence: {
              trigger: "opaque_artifact_reference",
              policyVersion: "test_v1"
            },
            keyChange: "Escalated out of deterministic path"
          },
          {
            id: "STEP-2",
            timestamp: "2026-03-14T14:08:00Z",
            label: "Judged",
            judgmentMethod: "Operator review",
            judgmentCause: "Artifact required explicit approval",
            governanceResponse: "Manual approval requested",
            result: "pending_approval",
            evidence: {
              artifactIdentity: "artifact://governed-action/ACT-204/policy-bundle",
              priorApprovals: 0,
              reviewPacket: "PKT-204"
            },
            keyChange: "Switched to approval-backed judgment"
          }
        ]
      },
      {
        id: "ATT-2",
        startedAt: "2026-03-14T14:15:00Z",
        finishedAt: "2026-03-14T14:24:00Z",
        summary: "Approval located and action completed",
        outcome: "completed",
        steps: [
          {
            id: "STEP-3",
            timestamp: "2026-03-14T14:18:00Z",
            label: "Judged",
            judgmentMethod: "Approval lookup",
            judgmentCause: "Active approval entry matched artifact",
            governanceResponse: "Approval recognized",
            result: "approved_lookup",
            evidence: {
              approvalId: "APR-100",
              artifactIdentity: "artifact://governed-action/ACT-204/policy-bundle"
            },
            keyChange: "Approval restored execution path"
          },
          {
            id: "STEP-4",
            timestamp: "2026-03-14T14:22:00Z",
            label: "Determined",
            governanceResponse: "Bundle deployed",
            result: "completed",
            evidence: {
              deploymentTarget: "governed-main",
              checksum: "3d0fa4"
            },
            keyChange: "Completed after approval-backed judgment"
          }
        ]
      }
    ]
  },
  {
    id: "ACT-207",
    title: "Exception grant refresh",
    family: "exception_grant",
    type: "GRANT_REFRESH",
    judgmentCategory: "No admissible choice",
    disposition: "denied_after_revocation",
    governanceResponseSummary: "Revoked approval forced denial",
    timestamps: {
      openedAt: "2026-03-15T10:55:00Z",
      updatedAt: "2026-03-15T11:20:00Z"
    },
    attempts: [
      {
        id: "ATT-1",
        startedAt: "2026-03-15T10:55:00Z",
        finishedAt: "2026-03-15T11:20:00Z",
        summary: "Approval no longer valid",
        outcome: "denied",
        steps: [
          {
            id: "STEP-1",
            timestamp: "2026-03-15T11:02:00Z",
            label: "Judged",
            judgmentMethod: "Approval lookup",
            judgmentCause: "Approval entry had been revoked",
            governanceResponse: "Approval rejected",
            result: "denied",
            evidence: {
              approvalId: "APR-101",
              revocationReason: "Exception no longer needed after policy update"
            },
            keyChange: "Approval path blocked by revocation"
          }
        ]
      }
    ]
  },
  {
    id: "ACT-310",
    title: "Filesystem read validation",
    family: "filesystem",
    type: "FS_READ",
    disposition: "failed",
    governanceResponseSummary: "Deterministic deny on invalid target",
    timestamps: {
      openedAt: "2026-03-08T08:31:00Z",
      updatedAt: "2026-03-08T08:36:00Z"
    },
    attempts: [
      {
        id: "ATT-1",
        startedAt: "2026-03-08T08:31:00Z",
        finishedAt: "2026-03-08T08:36:00Z",
        summary: "Invalid path denied",
        outcome: "failed",
        steps: [
          {
            id: "STEP-1",
            timestamp: "2026-03-08T08:34:00Z",
            label: "Determined",
            governanceResponse: "Path check failed",
            result: "deny",
            evidence: {
              requestType: "FS_READ",
              targetPath: "/secrets/hidden.txt",
              rule: "outside_allowlist"
            },
            keyChange: "Denied without judgment"
          }
        ]
      }
    ]
  },
  {
    id: "ACT-412",
    title: "Triaged replay packet",
    family: "packet",
    type: "REPLAY_PACKET",
    judgmentCategory: "Bounded estimation",
    disposition: "completed_with_judgment",
    governanceResponseSummary: "Judgment used to resolve underdetermined packet mismatch",
    timestamps: {
      openedAt: "2026-03-02T16:00:00Z",
      updatedAt: "2026-03-03T10:10:00Z"
    },
    attempts: [
      {
        id: "ATT-1",
        startedAt: "2026-03-02T16:00:00Z",
        finishedAt: "2026-03-03T10:10:00Z",
        summary: "Packet reviewed across mixed evidence",
        outcome: "completed",
        steps: [
          {
            id: "STEP-1",
            timestamp: "2026-03-02T16:05:00Z",
            label: "Determined",
            governanceResponse: "Replay outcome unavailable",
            result: "needs_review",
            evidence: {
              replayOutcome: "unavailable",
              packetId: "PKT-412"
            },
            keyChange: "Escalated due to incomplete replay evidence"
          },
          {
            id: "STEP-2",
            timestamp: "2026-03-03T09:50:00Z",
            label: "Judged",
            judgmentMethod: "Two-reviewer adjudication",
            judgmentCause: "Underdetermined replay evidence",
            governanceResponse: "Proceed with caution",
            result: "approved_with_notes",
            evidence: {
              reviewers: ["reviewer-a", "reviewer-b"],
              note: "Treat as bounded exception with follow-up"
            },
            keyChange: "Judgment resolved underdetermined case"
          }
        ]
      }
    ]
  }
];
