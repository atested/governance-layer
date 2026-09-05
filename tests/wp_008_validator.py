#!/usr/bin/env python3
"""Independent observable scenarios for WP-008 documentation and claims."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"!?\[[^]]+\]\(([^)]+)\)")


def local_markdown_targets(document: Path) -> list[Path]:
    targets = []
    for raw_target in MARKDOWN_LINK.findall(document.read_text(encoding="utf-8")):
        target = raw_target.split("#", 1)[0].split("?", 1)[0].strip()
        if not target or "://" in target or target.startswith("mailto:"):
            continue
        targets.append((document.parent / target).resolve())
    return targets


class PublishedDocumentationLinkValidator(unittest.TestCase):
    def test_published_local_documentation_destinations_exist(self):
        inventory = [REPO / "README.md", *sorted((REPO / "docs/website/docs-pages").glob("*.md"))]
        missing = []
        for document in inventory:
            for target in local_markdown_targets(document):
                if not target.is_file():
                    missing.append(f"{document.relative_to(REPO)} -> {target}")
        self.assertEqual(missing, [], "broken documentation destinations: " + "; ".join(missing))


class PublicContentEvidenceLanguageValidator(unittest.TestCase):
    def test_each_public_assertion_has_concrete_subject_action_and_basis(self):
        register = REPO / "docs/PUBLIC_PRODUCT_ASSERTIONS.md"
        rows = [line for line in register.read_text(encoding="utf-8").splitlines() if line.startswith("|") and not line.startswith("| ---") and not line.startswith("| Assertion")]
        self.assertGreaterEqual(len(rows), 2)
        for row in rows:
            fields = [field.strip() for field in row.strip("|").split("|")]
            self.assertEqual(len(fields), 4, row)
            assertion, subject_action, basis, status = fields
            self.assertTrue(assertion and subject_action and basis and status, row)
            if status.lower() == "aspirational":
                self.assertIn("aspirational", assertion.lower() + basis.lower(), row)
            else:
                self.assertRegex(subject_action, r"\b(controls|classifies|evaluates|records|verifies|forwards|buffers|governs|intercepts|inspects|returns|stores|links|does not)\b", row)
                self.assertTrue(any((REPO / path).exists() for path in re.findall(r"`([^`]+)`", basis)), row)


if __name__ == "__main__":
    unittest.main(verbosity=2)
