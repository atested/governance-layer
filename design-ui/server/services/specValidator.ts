import type { DesignDatabase } from "../db.ts";
import { listDiscoveryItems } from "../repositories/discoveryItems.ts";
import { listPurposeItems } from "../repositories/purposeItems.ts";

export type ValidationCheck = {
  status: "pass" | "warning" | "fail";
  message: string;
  relatedItemIds: string[];
};

export type SpecValidationResult = {
  passed: boolean;
  checks: {
    purposeClarity: ValidationCheck;
    expectationClarity: ValidationCheck;
    operationalIntentPreserved: ValidationCheck;
    confusionRiskAddressed: ValidationCheck;
    examplesAdequate: ValidationCheck;
    boundariesPresent: ValidationCheck;
    residualJudgmentsPresent: ValidationCheck;
    downstreamRediscoveryRisk: ValidationCheck;
  };
};

function hasType(items: Array<Record<string, unknown>>, type: string) {
  return items.filter((item) => item.purposeType === type);
}

function ids(items: Array<Record<string, unknown>>) {
  return items.map((item) => String(item.id));
}

function check(
  pass: boolean,
  missingStatus: "warning" | "fail",
  passMessage: string,
  missingMessage: string,
  relatedItemIds: string[] = []
): ValidationCheck {
  return {
    status: pass ? "pass" : missingStatus,
    message: pass ? passMessage : missingMessage,
    relatedItemIds
  };
}

export function validateDesignSpecification(db: DesignDatabase, projectId: string): SpecValidationResult {
  const purposeItems = listPurposeItems(db, projectId) as Array<Record<string, unknown>>;
  const discoveryItems = listDiscoveryItems(db, projectId) as Array<Record<string, unknown>>;
  const purpose = hasType(purposeItems, "purpose_candidate");
  const expectations = hasType(purposeItems, "expectation");
  const operationalIntent = hasType(purposeItems, "operational_intent");
  const boundaries = hasType(purposeItems, "boundary");
  const positiveExamples = hasType(purposeItems, "positive_exemplar");
  const negativeExamples = hasType(purposeItems, "negative_exemplar");
  const residualJudgments = hasType(purposeItems, "residual_judgment");
  const distinguishingProperties = hasType(purposeItems, "distinguishing_property");
  const tensions = discoveryItems.filter((item) => item.discoveryType === "tension");
  const unresolved = discoveryItems.filter(
    (item) => item.discoveryType === "question" || item.discoveryType === "unresolved_area"
  );

  const checks: SpecValidationResult["checks"] = {
    purposeClarity: check(
      purpose.length > 0,
      "fail",
      "At least one committed purpose candidate is present.",
      "No committed purpose candidate is present.",
      ids(purpose)
    ),
    expectationClarity: check(
      expectations.length > 0,
      "warning",
      "Committed expectations are present.",
      "No committed expectations are present.",
      ids(expectations)
    ),
    operationalIntentPreserved: check(
      operationalIntent.length > 0,
      "warning",
      "Operational intent is represented.",
      "No committed operational intent is present.",
      ids(operationalIntent)
    ),
    confusionRiskAddressed: check(
      distinguishingProperties.length > 0 || negativeExamples.length > 0,
      "warning",
      "Confusion risk is addressed with distinguishing properties or negative examples.",
      "No distinguishing properties or negative examples address likely confusion risk.",
      [...ids(distinguishingProperties), ...ids(negativeExamples), ...ids(tensions)]
    ),
    examplesAdequate: check(
      positiveExamples.length > 0 && negativeExamples.length > 0,
      "warning",
      "Positive and negative examples are both present.",
      "Positive and negative examples are not both present.",
      [...ids(positiveExamples), ...ids(negativeExamples)]
    ),
    boundariesPresent: check(
      boundaries.length > 0,
      "fail",
      "Committed boundaries are present.",
      "No committed boundaries are present.",
      ids(boundaries)
    ),
    residualJudgmentsPresent: check(
      residualJudgments.length > 0,
      "warning",
      "Residual judgments are present.",
      "No residual judgments are present.",
      ids(residualJudgments)
    ),
    downstreamRediscoveryRisk: check(
      purpose.length > 0 && boundaries.length > 0 && unresolved.length === 0,
      "warning",
      "Spec should not need to return to discovery for core meaning.",
      "Spec may be forced back into discovery because purpose/boundary state is incomplete or open questions remain.",
      [...ids(purpose), ...ids(boundaries), ...ids(unresolved)]
    )
  };

  return {
    passed: Object.values(checks).every((item) => item.status === "pass"),
    checks
  };
}
