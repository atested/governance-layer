# Licensing

Atested is distributed under the **Business Source License 1.1** (BSL 1.1).

---

## Summary

| Term | Value |
|---|---|
| **License** | Business Source License 1.1 |
| **Licensor** | AIEngageTech, LLC |
| **Licensed Work** | Atested governance layer |
| **Change Date** | May 13, 2030 |
| **Change License** | Apache License 2.0 |
| **Additional Use Grant** | Personal and evaluation use |

---

## What this means

### Personal and evaluation use — free

You may use Atested at no cost for:

- Personal projects (single operator, non-commercial)
- Evaluation and testing
- Academic and research purposes
- Contributing to the project

No license key is required for personal use.

### Commercial production use — paid license required

If you use Atested in a commercial production environment (revenue-generating services, internal business operations with multiple users, or client-facing deployments), you need a paid license.

| Tier | Price | Use case |
|---|---|---|
| **Team** | $999/year | Small team (2–10 operators) |
| **Business** | $4,999/year | Organization-wide deployment |
| **Enterprise** | Custom | Custom terms, SLA, dedicated support |

Purchase at [atested.com/pricing.html](https://atested.com/pricing.html).

### Change date — Apache 2.0 on May 13, 2030

On May 13, 2030, the entire codebase automatically converts to the **Apache License 2.0**. After that date, all use — including commercial production use — is free and unrestricted under Apache 2.0 terms.

---

## How licensing works in the governance engine

Licensing is recorded as evidentiary metadata in every governance record. It does **not** gate functionality — a governed action that would be ALLOW remains ALLOW regardless of license status. Licensing records the truth about the operator's status.

### License statuses

| Status | Meaning |
|---|---|
| `trial` | First 30 days after initial deployment. Full functionality. |
| `licensed` | A valid license key has been activated. |
| `unlicensed` | Trial expired without activation. Full functionality continues — records state the truth. |
| `personal` | Single-user installation after trial expiry. Free tier, no license required. |

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
