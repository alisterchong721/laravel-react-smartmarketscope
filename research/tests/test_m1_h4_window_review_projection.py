from __future__ import annotations

import unittest

import pandas as pd

from smartmarketscope_quant.macro_liquidity_reversal.m1_h4_window_review_projection import (
    _chart_candles,
    _d1_context_candles,
    _load_daily_context,
)


class M1H4WindowReviewProjectionTests(unittest.TestCase):
    def test_chart_candles_are_bounded_to_the_owning_h4_interval(self) -> None:
        timestamps = pd.to_datetime([
            "2026-06-24 15:59:00",
            "2026-06-24 16:00:00",
            "2026-06-24 17:45:00",
            "2026-06-24 19:59:00",
            "2026-06-24 20:00:00",
        ])
        frame = pd.DataFrame({
            "bar_start_source": timestamps,
            "available_at_source": timestamps + pd.Timedelta(minutes=1),
            "open_completed": [1, 2, 3, 4, 5],
            "high_completed": [2, 3, 4, 5, 6],
            "low_completed": [0, 1, 2, 3, 4],
            "close_completed": [1.5, 2.5, 3.5, 4.5, 5.5],
        })

        candles = _chart_candles(
            frame,
            "2026-06-24 16:00:00",
            "2026-06-24 20:00:00",
        )

        self.assertEqual(
            [candle["timestamp"] for candle in candles],
            [
                "2026-06-24 16:00:00",
                "2026-06-24 17:45:00",
                "2026-06-24 19:59:00",
            ],
        )
        self.assertTrue(all(candle["eligibleWindow"] is True for candle in candles))
        self.assertTrue(all(candle["role"] is None for candle in candles))

    def test_d1_context_has_three_prior_bars_and_frozen_swing_pair(self) -> None:
        timestamps = pd.to_datetime([
            "2026-06-20 00:00:00",
            "2026-06-21 00:00:00",
            "2026-06-22 00:00:00",
            "2026-06-23 00:00:00",
        ])
        frame = pd.DataFrame({
            "bar_start_source": timestamps,
            "available_at_source": timestamps + pd.Timedelta(days=1),
            "open_completed": [1, 2, 3, 4],
            "high_completed": [2, 3, 4, 5],
            "low_completed": [0, 1, 2, 3],
            "close_completed": [1.5, 2.5, 3.5, 4.5],
        })
        frozen = [
            {"timestamp": "2026-06-23 00:00:00", "role": "CANDLE_1", "close": 10},
            {"timestamp": "2026-06-24 00:00:00", "role": "CANDLE_2", "close": 11},
        ]

        candles = _d1_context_candles(frame, "2026-06-23 00:00:00", frozen)

        self.assertEqual(len(candles), 5)
        self.assertEqual([candle["role"] for candle in candles], [
            "CONTEXT", "CONTEXT", "CONTEXT", "CANDLE_1", "CANDLE_2",
        ])
        self.assertEqual(candles[-2:], frozen)
        self.assertTrue(all(
            candle["timestamp"] < "2026-06-23 00:00:00" for candle in candles[:3]
        ))

    def test_native_daily_context_loader_assigns_next_day_availability(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            path = Path(directory) / "daily.csv"
            path.write_text(
                "<DATE>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\n"
                "2026.06.22\t1\t2\t0\t1.5\n",
                encoding="utf-8",
            )
            frame = _load_daily_context(path)

        self.assertEqual(str(frame.iloc[0]["bar_start_source"]), "2026-06-22 00:00:00")
        self.assertEqual(str(frame.iloc[0]["available_at_source"]), "2026-06-23 00:00:00")


if __name__ == "__main__":
    unittest.main()
