from __future__ import annotations

import unittest
from pathlib import Path

from smartmarketscope_quant.macro_regime.h41_parser import parse_h41
from smartmarketscope_quant.macro_regime.historical_collector import CollectionValidationError


RAW = Path("/Applications/XAMPP/xamppfiles/htdocs/laravel-smartmarketscope/storage/app/private/macro_raw/provider=federal_reserve/series=H41/pilot=H41_DISCOVERY_V1")
FULL_RAW = Path("/Applications/XAMPP/xamppfiles/htdocs/laravel-smartmarketscope/storage/app/private/macro_raw/provider=federal_reserve/series=H41/full_sequence=H41_20021219_20260625_V1")


class MacroRegimeH41ParserTest(unittest.TestCase):
    def test_five_in_scope_eras_parse_exact_target_rows(self) -> None:
        expected = {
            "08-20021219": ("2002-12-19", "2002-12-18", 720601, 7631, 6595, "LEGACY_PRE"),
            "04-20080918": ("2008-09-18", "2008-09-17", 995570, 81737, 5512, "LEGACY_PRE"),
            "05-20140102": ("2014-01-02", "2014-01-01", 4023640, 2249070, 162399, "LEGACY_PRE"),
            "06-20200319": ("2020-03-19", "2020-03-18", 4668212, 1945393, 401354, "LEGACY_PRE"),
            "07-20260625": ("2026-06-25", "2026-06-24", 6735645, 2954465, 901845, "MODERN_HTML_TABLE"),
        }
        for request, values in expected.items():
            with self.subTest(request=request):
                snapshot = parse_h41((RAW / f"request={request}" / "body.html").read_bytes())
                self.assertEqual(
                    (
                        snapshot.release_date, snapshot.reference_date, snapshot.total_assets_millions,
                        snapshot.reserve_balances_millions, snapshot.treasury_general_account_millions,
                        snapshot.parser_format,
                    ),
                    values,
                )

    def test_out_of_scope_failed_first_body_uses_pre_contract_concept_name(self) -> None:
        with self.assertRaisesRegex(CollectionValidationError, "row missing"):
            parse_h41((RAW / "request=03-19960627/body.html").read_bytes())

    def test_legacy_signed_reserve_balance_reconciles_exactly(self) -> None:
        body = FULL_RAW / "release_date=2008-07-03/source_run=role5-h41-full-0298-20080703-a1/release.html"
        snapshot = parse_h41(body.read_bytes())
        self.assertEqual(
            (
                snapshot.release_date,
                snapshot.reference_date,
                snapshot.total_assets_millions,
                snapshot.reserve_balances_millions,
                snapshot.treasury_general_account_millions,
                snapshot.parser_format,
            ),
            ("2008-07-03", "2008-07-02", 905739, -6962, 4139, "LEGACY_PRE"),
        )
        self.assertEqual(923755 - 930717, snapshot.reserve_balances_millions)


if __name__ == "__main__":
    unittest.main()
