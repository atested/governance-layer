"""Tests for machine cap enforcement on direct key activation.

Verifies that the direct license activation endpoint enforces
MACHINE_CAPS the same way the sharing flow does.
"""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "dashboard"))

from dashboard.server import MACHINE_CAPS


class TestMachineCapActivation:
    def test_machine_caps_defined(self):
        """MACHINE_CAPS must have expected tiers."""
        assert "personal" in MACHINE_CAPS
        assert "personal_plus" in MACHINE_CAPS
        assert "crew" in MACHINE_CAPS
        assert MACHINE_CAPS["personal"] == 1
        assert MACHINE_CAPS["personal_plus"] == 3
        assert MACHINE_CAPS["crew"] is None  # unlimited

    def test_activation_handler_checks_machine_cap(self):
        """The _handle_activate_with_key method must reference MACHINE_CAPS."""
        import inspect
        from dashboard.server import DashboardHandler

        source = inspect.getsource(DashboardHandler._handle_activate_with_key)
        # The handler must check machine capacity
        assert "MACHINE_CAPS" in source, (
            "Direct activation handler must check MACHINE_CAPS"
        )
        assert "_count_active_machines_from_chain" in source, (
            "Direct activation handler must count active machines"
        )
        assert "Machine limit reached" in source, (
            "Direct activation handler must have machine limit error"
        )

    def test_sharing_handler_also_checks_cap(self):
        """Sharing flow must also check caps (baseline parity)."""
        import inspect
        from dashboard.server import DashboardHandler

        source = inspect.getsource(DashboardHandler._handle_sharing_start)
        assert "MACHINE_CAPS" in source
        assert "_count_active_machines_from_chain" in source
