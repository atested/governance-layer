#!/usr/bin/env python3
"""AAT Profile Registry - Manages action kind profiles.

This module loads and manages profiles that define validation requirements
for different action kinds. Profiles specify which validators run and in
what enforcement mode.

v0 Profiles:
- CORE_GENERIC: Universal baseline (K1-K5 + M1 enforcing, P1-P2 + C1-C3 report-only)
- TOOL_EXEC: Inherits CORE_GENERIC and additionally enforces C1/C2
"""

from __future__ import annotations

from typing import Any


class Profile:
    """Represents a validation profile for an action kind."""

    def __init__(
        self,
        name: str,
        enforcing_checks: set[str],
        report_only_checks: set[str],
        inherits_from: str | None = None,
    ):
        """Initialize a profile.

        Args:
            name: Profile name (e.g., "CORE_GENERIC", "TOOL_EXEC")
            enforcing_checks: Set of check codes to enforce (K*, M*, P*, C*)
            report_only_checks: Set of check codes to run in report-only mode
            inherits_from: Optional parent profile to inherit from
        """
        self.name = name
        self.enforcing_checks = enforcing_checks
        self.report_only_checks = report_only_checks
        self.inherits_from = inherits_from

    def get_all_enforcing_checks(self, registry: ProfileRegistry) -> set[str]:
        """Get all enforcing checks including inherited ones.

        Args:
            registry: Profile registry for resolving inheritance

        Returns:
            Set of all enforcing check codes
        """
        checks = self.enforcing_checks.copy()
        if self.inherits_from:
            parent = registry.get_profile(self.inherits_from)
            if parent:
                checks.update(parent.get_all_enforcing_checks(registry))
        return checks

    def get_all_report_only_checks(self, registry: ProfileRegistry) -> set[str]:
        """Get all report-only checks including inherited ones.

        Args:
            registry: Profile registry for resolving inheritance

        Returns:
            Set of all report-only check codes
        """
        checks = self.report_only_checks.copy()
        if self.inherits_from:
            parent = registry.get_profile(self.inherits_from)
            if parent:
                checks.update(parent.get_all_report_only_checks(registry))
        return checks


class ProfileRegistry:
    """Registry of validation profiles."""

    def __init__(self):
        """Initialize the profile registry with v0 profiles."""
        self.profiles: dict[str, Profile] = {}
        self._init_v0_profiles()

    def _init_v0_profiles(self) -> None:
        """Initialize v0 profiles: CORE_GENERIC and TOOL_EXEC."""
        # CORE_GENERIC: Universal baseline profile
        # Enforcing: K1-K5 (kernel invariants) + M1 (mechanical)
        # Report-only: P1-P2 (property) + C1-C3 (consistency)
        core_generic = Profile(
            name="CORE_GENERIC",
            enforcing_checks={"K1", "K2", "K3", "K4", "K5", "M1"},
            report_only_checks={"P1", "P2", "C1", "C2", "C3"},
        )
        self.profiles["CORE_GENERIC"] = core_generic

        # TOOL_EXEC: first profile expansion beyond CORE_GENERIC.
        # Additional enforcing checks (beyond inherited K1-K5 + M1):
        # - C1: contradiction detection
        # - C2: evidence reference integrity
        tool_exec = Profile(
            name="TOOL_EXEC",
            enforcing_checks={"C1", "C2"},
            report_only_checks=set(),
            inherits_from="CORE_GENERIC",
        )
        self.profiles["TOOL_EXEC"] = tool_exec

    def get_profile(self, action_kind: str) -> Profile:
        """Get profile for action kind.

        Args:
            action_kind: Action kind (e.g., "CORE_GENERIC", "TOOL_EXEC")

        Returns:
            Profile for action kind, or CORE_GENERIC if not found
        """
        return self.profiles.get(action_kind, self.profiles["CORE_GENERIC"])

    def has_profile(self, action_kind: str) -> bool:
        """Return True when action_kind maps to a known profile."""
        return action_kind in self.profiles

    def get_enforcing_checks(self, action_kind: str) -> set[str]:
        """Get enforcing checks for action kind.

        Args:
            action_kind: Action kind

        Returns:
            Set of enforcing check codes (e.g., {"K1", "K2", "M1"})
        """
        profile = self.get_profile(action_kind)
        return profile.get_all_enforcing_checks(self)

    def get_report_only_checks(self, action_kind: str) -> set[str]:
        """Get report-only checks for action kind.

        Args:
            action_kind: Action kind

        Returns:
            Set of report-only check codes (e.g., {"P1", "P2", "C1"})
        """
        profile = self.get_profile(action_kind)
        return profile.get_all_report_only_checks(self)

    def is_enforcing(self, action_kind: str, check_code: str) -> bool:
        """Check if a specific check is enforcing for action kind.

        Args:
            action_kind: Action kind
            check_code: Check code (e.g., "K1", "M1", "P1")

        Returns:
            True if check is enforcing, False if report-only
        """
        enforcing = self.get_enforcing_checks(action_kind)
        return check_code in enforcing


def main() -> None:
    """CLI entry point for testing profile registry."""
    import sys

    registry = ProfileRegistry()

    if len(sys.argv) < 2:
        print("usage: aat_profile_registry.py <action_kind>")
        print("\nAvailable profiles:")
        for profile_name in registry.profiles.keys():
            profile = registry.profiles[profile_name]
            enforcing = profile.get_all_enforcing_checks(registry)
            report_only = profile.get_all_report_only_checks(registry)
            print(f"  {profile_name}:")
            print(f"    Enforcing: {sorted(enforcing)}")
            print(f"    Report-only: {sorted(report_only)}")
        sys.exit(0)

    action_kind = sys.argv[1]
    profile = registry.get_profile(action_kind)

    print(f"Profile: {profile.name}")
    print(f"Enforcing: {sorted(profile.get_all_enforcing_checks(registry))}")
    print(f"Report-only: {sorted(profile.get_all_report_only_checks(registry))}")


if __name__ == "__main__":
    main()
