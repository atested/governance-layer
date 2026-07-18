# Licensing Alignment Report

Date: July 18, 2026

This report records the bounded ATESTED-LAUNCH-P7 consistency correction. The
authoritative legal text remains the repository-root `LICENSE` file.

## Baselines

| Repository | Baseline |
|---|---|
| `governance-layer` | `6a51f9020328e59559fd3afbaad9ea649c3968bd` |
| `atested.com` | `df966695724c8f5e8296d244295bd9be222dbcd8` |

## Final authoritative wording

- **Licensor:** AIEngageTech, LLC.
- **Licensed Work:** Atested v1.0.0.
- **Free Additional Use Grant:** Personal non-commercial use; evaluation and
  testing; academic and research use that is not organizational operational
  production; and non-production development.
- **Paid use:** Any commercial production or organizational operational
  production use requires a paid commercial license, including entirely
  internal use by or for a business, nonprofit organization, government body,
  consultancy, or other organization.
- **Third-party use:** Providing or making Atested governance functionality
  available to a third party requires a paid commercial license.
- **Product entitlements:** Machine and user capacity, report-history ranges,
  dashboard features, support, communications, and hosted services are product
  entitlements, not restrictions written into the BSL.
- **License classification:** Source-available under BSL 1.1 before the Change
  Date; not described as open source.
- **BSL Change Date:** May 13, 2030.
- **Change License:** Apache License 2.0.
- **Operative-page effective date:** July 18, 2026. This is distinct from the
  BSL Change Date.

## Changed claims

| Surface | Previous claim | Final claim |
|---|---|---|
| `LICENSE` | Production use was allowed except for a defined Governance Service. | Free use is limited to the stated personal, evaluation, academic/research, and non-production uses; commercial, organizational production, internal organizational, and third-party governance use require a paid commercial license. |
| Root README and `docs/LICENSING.md` | Commercial use required payment, but copyright rights and product tiers were not clearly separated; documentation also said licensing did not gate functionality. | Paid permission is required for commercial or organizational production, while tier keys separately control product features, capacities, support, communications, and services. |
| Configuration and dashboard documentation | “License required” could mean either copyright permission or a feature key. | Configuration editing is a product entitlement; the BSL separately determines whether the deployment is permitted. |
| Dashboard licensing terms | Personal fallback and continued operation were described without stating the production-use limit. | Trial is for evaluation; paid production permission and product entitlements are distinct; unlicensed commercial or organizational production use is not permitted. |
| Public legal pages | Several pages were labeled drafts or pending legal review. | All seven legal pages are operative and display the July 18, 2026 effective date. |
| Public license page | Used an incorrect individual licensor and Change Date and did not fully cover internal organizational use. | Names AIEngageTech, LLC, uses May 13, 2030, states the complete paid-use rule, and separates product entitlements. |
| Terms of Service | Described an open-source core, used the wrong Change Date, and deferred to an unspecified separate subscription agreement. | Describes source-available BSL code, the correct paid-use scope, the selected plan's entitlements, and the correct Change Date. |
| Privacy, Acceptable Use, DMCA, and Legal Contact | Contained draft/future-review notices; Privacy used an incorrect unrestricted-source classification; Legal Contact described an interim future page. | Operative policies name AIEngageTech, LLC where relevant, remove provisional status, and use source-available terminology. |
| Trust and chain documentation | Used an incorrect unrestricted-source classification for the code and verification app. | Describes the code and verification app as source-available. |
| Installation guide | Referred to “licensed machines” and limits “according to license terms.” | Identifies machine limits as product entitlements and separately states the paid commercial-production requirement. |
| Public pricing and demo terms | Payment was described primarily as a tier purchase, and fallback to Personal did not state the production-use restriction. | Payment covers commercial or organizational production permission plus the selected tier's features, capacities, support, communications, and services. |
| Website repository README | Labeled legal terms as a placeholder. | Labels them as Terms of Service. |

## Validation evidence

- `git diff --check`: passed in both repositories.
- Authoritative parameter and grant assertions: passed.
- No public legal-status phrase such as “draft document,” “pending legal
  review,” “final version,” or “in the interim” remains on the reviewed public
  surfaces.
- No stale Change Date or individual-licensor reference remains on the reviewed
  public surfaces.
- No public-facing text uses the superseded unrestricted-source classification
  for Atested.
- All seven legal pages contain exactly one `Effective date: July 18, 2026`.
- All 32 website HTML files parsed successfully with Python's HTML parser.
- Updated JavaScript files passed `node --check`.
- Updated Markdown files parsed successfully with `markdown-it` and have
  balanced fenced-code blocks and structurally complete table rows.
- Governance implementation, proxy, licensing-token behavior, tests,
  capabilities, Worker code, Stripe IDs, prices, tier registry, and checkout
  behavior were unchanged.

## External operational check

Stripe-hosted Payment Link terms are not represented in either repository.
Before accepting payment, open each live Payment Link and confirm that its
displayed or incorporated terms match the paid commercial-use permission and
selected product-entitlement wording above. No Stripe configuration was changed
as part of this work.
