# Licensing

Atested is distributed under the **Business Source License 1.1** (BSL 1.1).

---

## Summary

| Term | Value |
|---|---|
| **License** | Business Source License 1.1 |
| **Licensor** | AIEngageTech, LLC |
| **Licensed Work** | Atested v1.0.0 |
| **Change Date** | May 13, 2030 |
| **Change License** | Apache License 2.0 |
| **Additional Use Grant** | Personal non-commercial use; evaluation and testing; qualifying academic and research use; non-production development |

---

## What this means

### Uses permitted without a paid commercial license

You may use Atested at no cost for:

- Personal projects (single operator, non-commercial)
- Evaluation and testing
- Academic and research purposes that are not organizational operational production
- Non-production development
- Contributing to the project

These are copyright-license permissions under the BSL Additional Use Grant. A
product license key may still be used to register an installation or enable a
particular set of product entitlements.

### Commercial production use — paid license required

Any commercial production use or organizational operational production use
requires a paid commercial license from AIEngageTech, LLC. This includes use by
or for a business, nonprofit organization, government body, consultancy, or
other organization, even when the use is entirely internal or no separate fee
is charged. Providing or making Atested governance functionality available to a
third party also requires a paid commercial license.

Current product tiers, prices, capacities, and included services are listed at
[atested.com/pricing/](https://atested.com/pricing/). Those product terms do not
change the scope of the BSL Additional Use Grant.

### Source-available license and Change Date

Before the Change Date, Atested is **source-available under BSL 1.1**, not open
source. On May 13, 2030, or the fourth anniversary of the first publicly
available distribution of the applicable version if earlier, that version
converts to the **Apache License 2.0** under the terms of the BSL.

---

## Copyright permission and product entitlements

Atested licensing has two distinct layers:

1. **Copyright-license permission.** The BSL Additional Use Grant determines
   whether a use is permitted without a paid commercial license. Commercial or
   organizational production use requires payment regardless of which product
   features are used.
2. **Product entitlements.** A Personal, Personal Plus, Crew, Team,
   Institution, or other product license key enables the features, capacities,
   support, communications, and services assigned to that tier. Machine limits,
   report-history ranges, dashboard capabilities, and support levels are
   product entitlements; they are not restrictions written into the BSL.

The core governance path continues to record its license posture as evidentiary
metadata, but the product does gate defined paid capabilities. A paid commercial
license permits the covered production use; the selected product tier determines
which gated capabilities and services are included.

### License statuses

| Status | Meaning |
|---|---|
| `trial` | Evaluation status. Full product capabilities are available for evaluation, not commercial or organizational production use. |
| `licensed` | A valid license key has been activated. |
| `unlicensed` | No active paid product entitlement. Core governance may continue, but commercial or organizational production use is not permitted. |
| `personal` | Personal product entitlement. It does not authorize commercial or organizational production use. |

### Governed tools

| Tool | Purpose |
|---|---|
| `license_status` | Report current licensing state, trial days remaining, unique users |
| `license_activate` | Accept a license key and update license configuration |

### License key format

License tokens are Ed25519-signed JSON payloads. The signing private key is held by the license issuer. The client embeds only the public verification key.

Token format: `base64url(JSON-payload).base64url(Ed25519-signature)`

---

## Full license text

See the [LICENSE](../LICENSE) file in the repository root for the complete Business Source License 1.1 text.
