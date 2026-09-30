"""Exercise the real Structure validator with a minimal Frappe boundary."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from test_permissions import Attr, stub_frappe
from test_service import Row


class TestStructureUnits(unittest.TestCase):
    def validate_row(self, component_indicator, **values):
        fake = stub_frappe()
        fake.get_doc = lambda *args: Attr(
            objective="Delivery", metric="Agreed result", indicator=component_indicator,
            perspective="Operations",
        )
        document = types.ModuleType("frappe.model.document")
        document.Document = Row
        naming = types.ModuleType("frappe.model.naming")
        naming.make_autoname = lambda value: value
        path = Path(__file__).resolve().parents[1] / "kpi_management/kpi_management/doctype/kpi_structure/kpi_structure.py"
        spec = importlib.util.spec_from_file_location("structure_under_test", path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {
            "frappe": fake,
            "frappe.model.document": document,
            "frappe.model.naming": naming,
        }):
            spec.loader.exec_module(module)
        module.require_manager = lambda: None
        module.scope = lambda: {"Company": {"Test Company"}}
        # Preserve domain validation; the wrapper only translates its exceptions.
        module.checked = lambda fn, *args: fn(*args)
        row = Row(kpi_component="KPI-1", weight=100, **values)
        doc = module.KPIStructure(company="Test Company", components=[row])
        doc.get_doc_before_save = lambda: None
        doc.validate()
        self.assertEqual(doc.total_weight, 100)
        self.assertEqual(row.indicator, component_indicator)
        return row

    def test_hidden_currency_cleared_for_every_non_currency_indicator(self):
        for indicator, target in [
            ("Number", {"target_number": 10}),
            ("Percentage", {"target_number": 95}),
            ("Duration", {"target_number": 2, "duration_unit": "Days"}),
            ("Yes No", {"target_choice": "Yes"}),
            ("Date", {"target_date": "2026-12-31"}),
            ("Text", {"target_text": "Complete rollout"}),
        ]:
            with self.subTest(indicator=indicator):
                row = self.validate_row(indicator, currency="TZS", **target)
                self.assertIsNone(row.currency)

    def test_currency_target_retains_currency_and_clears_stale_duration(self):
        row = self.validate_row("Currency", target_number=500, currency="TZS", duration_unit="Days")
        self.assertEqual(row.currency, "TZS")
        self.assertIsNone(row.duration_unit)
        self.assertEqual(row.target_display, "500 TZS")

    def test_currency_target_still_requires_currency(self):
        with self.assertRaisesRegex(ValueError, "Currency is required"):
            self.validate_row("Currency", target_number=500)

    def test_duration_still_requires_valid_unit(self):
        with self.assertRaisesRegex(ValueError, "valid unit"):
            self.validate_row("Duration", target_number=2, currency="TZS")

    def test_component_indicator_overrides_stale_row_indicator(self):
        row = self.validate_row("Number", indicator="Currency", currency="TZS", target_number=10)
        self.assertIsNone(row.currency)
