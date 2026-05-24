// Compatibility exports for the authoritative JSON tier feature registry.
// Keep tier definitions in tier-feature-registry.json only.

const registryUrl = new URL('./tier-feature-registry.json', import.meta.url);

async function loadRegistry() {
  if (registryUrl.protocol === 'file:') {
    const { readFile } = await import('node:fs/promises');
    return JSON.parse(await readFile(registryUrl, 'utf8'));
  }

  const response = await fetch(registryUrl);
  if (!response.ok) {
    throw new Error(`Unable to load tier feature registry: ${response.status}`);
  }
  return response.json();
}

export const TIER_FEATURE_REGISTRY = await loadRegistry();

export const TIERS = TIER_FEATURE_REGISTRY.tierOrder;
export const TIER_LABELS = Object.fromEntries(TIERS.map((tier) => [tier, TIER_FEATURE_REGISTRY.tiers[tier].label]));
export const TIER_LEVELS = Object.fromEntries(TIERS.map((tier, index) => [tier, index]));
export const MACHINE_CAPS = Object.fromEntries(TIERS.map((tier) => [tier, TIER_FEATURE_REGISTRY.tiers[tier].machineActivationCap]));
export const REPORT_RANGE_LIMITS = Object.fromEntries(TIERS.map((tier) => [tier, TIER_FEATURE_REGISTRY.tiers[tier].reportRange]));
export const COMMUNICATIONS_SLOTS = Object.fromEntries(TIERS.map((tier) => [tier, TIER_FEATURE_REGISTRY.tiers[tier].communicationsSlots]));
export const FEATURE_FLAGS = Object.fromEntries(TIERS.map((tier) => [tier, TIER_FEATURE_REGISTRY.tiers[tier].featureFlags]));
export const CAPACITY_RANGES = Object.fromEntries(TIERS.map((tier) => [tier, TIER_FEATURE_REGISTRY.tiers[tier].capacityRange]));
export const COMMERCIAL_TERMS = Object.fromEntries(TIERS.map((tier) => [tier, TIER_FEATURE_REGISTRY.tiers[tier].commercialTerms]));
export const TIER_CAPABILITIES = Object.fromEntries(TIERS.map((tier) => [tier, TIER_FEATURE_REGISTRY.tiers[tier].capabilities]));
export const CATEGORIES = TIER_FEATURE_REGISTRY.categories;
export const PAYMENT_LINKS = TIER_FEATURE_REGISTRY.paymentLinks;
export const CHARTER_ACTIVE = TIER_FEATURE_REGISTRY.charter.active;
export const CHARTER = {
  promo_code: TIER_FEATURE_REGISTRY.charter.promoCode,
  ...TIER_FEATURE_REGISTRY.charter.tiers,
  copy: TIER_FEATURE_REGISTRY.charter.copy,
};
export const ALERT_GROUPS = TIER_FEATURE_REGISTRY.alertGroups;

export function tierLevel(tier) {
  return TIER_LEVELS[tier] ?? TIER_LEVELS.personal;
}

export function tierLabel(tier) {
  return TIER_LABELS[tier] || TIER_LABELS.personal;
}
