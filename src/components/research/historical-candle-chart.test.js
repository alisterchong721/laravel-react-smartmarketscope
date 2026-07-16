import React from 'react';
import { render, screen } from '@testing-library/react';
import HistoricalCandleChart, { lastCompletedCandleIndex } from './historical-candle-chart';

const candles = [
  { timestamp: '2024-01-01 00:00:00', open: 10, high: 12, low: 9, close: 11 },
  { timestamp: '2024-01-01 04:00:00', open: 11, high: 13, low: 10, close: 10.5 },
  { timestamp: '2024-01-01 08:00:00', open: 10.5, high: 14, low: 10, close: 13 },
];

test('finds the last completed candle at the frozen actionable time', () => {
  expect(lastCompletedCandleIndex(candles, '2024-01-01 05:00:00')).toBe(1);
  expect(lastCompletedCandleIndex(candles, '2023-12-31 23:59:59')).toBe(-1);
});

test('uses availableAt so an M1 activation marker cannot include the still-forming minute', () => {
  const minuteCandles = [
    { ...candles[0], timestamp: '2024-01-01 17:44:00', availableAt: '2024-01-01 17:45:00' },
    { ...candles[1], timestamp: '2024-01-01 17:45:00', availableAt: '2024-01-01 17:46:00' },
  ];

  expect(lastCompletedCandleIndex(minuteCandles, '2024-01-01 17:45:00')).toBe(0);
});

test('renders candles, confluence zone, action marker, and trade levels', () => {
  render(
    <HistoricalCandleChart
      timeframe="H4"
      candles={candles}
      decisionTime="2024-01-01 05:00:00"
      levels={{ entry: 11, stop: 9.5, target: 14, zoneLower: 10.8, zoneUpper: 11.2 }}
    />
  );

  expect(screen.getByRole('img', { name: 'H4 historical candlestick window' })).toBeInTheDocument();
  expect(screen.getByText('3 completed candles')).toBeInTheDocument();
  expect(screen.getByText('actionable time')).toBeInTheDocument();
  expect(screen.getByText('frozen confluence zone')).toBeInTheDocument();
});

test('does not convert absent optional levels into a zero-price line', () => {
  render(
    <HistoricalCandleChart
      timeframe="M1"
      candles={candles}
      decisionTime="2024-01-01 05:00:00"
      levels={{ entry: null, stop: '', target: undefined }}
    />
  );

  expect(screen.queryByText(/^entry /)).not.toBeInTheDocument();
  expect(screen.queryByText(/^stop /)).not.toBeInTheDocument();
  expect(screen.queryByText(/^target /)).not.toBeInTheDocument();
  expect(screen.queryByText('frozen confluence zone')).not.toBeInTheDocument();
});

test('renders corrected D1 Candle 1 and Candle 2 roles plus the swept reference', () => {
  render(
    <HistoricalCandleChart
      timeframe="D1"
      candles={[
        { ...candles[0], role: 'CANDLE_1' },
        { ...candles[1], role: 'CANDLE_2' },
        candles[2],
      ]}
      decisionTime="2024-01-01 04:00:00"
      decisionLabel="Candle 2"
      referenceLevel={9}
      referenceLabel="Candle 1 low"
    />
  );

  expect(screen.getByText('C1')).toBeInTheDocument();
  expect(screen.getByText('C2')).toBeInTheDocument();
  expect(screen.getByText('Candle 2')).toBeInTheDocument();
  expect(screen.getByText('Candle 1 low 9')).toBeInTheDocument();
});

test('marks the strictly post-D1 H4 validity window', () => {
  render(
    <HistoricalCandleChart
      timeframe="H4"
      candles={[
        candles[0],
        { ...candles[1], eligibleWindow: true, role: 'CANDLE_1' },
        { ...candles[2], eligibleWindow: true, role: 'CANDLE_2' },
      ]}
    />
  );

  expect(screen.getByText('D1 validity window')).toBeInTheDocument();
  expect(screen.getByText('C1')).toBeInTheDocument();
  expect(screen.getByText('C2')).toBeInTheDocument();
});

test('renders a caller-specific owning-window label', () => {
  render(
    <HistoricalCandleChart
      timeframe="M1"
      candles={candles.map((candle) => ({ ...candle, eligibleWindow: true }))}
      eligibleWindowLabel="Owning H4 window"
    />
  );

  expect(screen.getByText('Owning H4 window')).toBeInTheDocument();
  expect(screen.queryByText('D1 validity window')).not.toBeInTheDocument();
});

test('marks separate breaker and displacement FVG zones with M1 evidence roles', () => {
  render(
    <HistoricalCandleChart
      timeframe="M1"
      candles={[
        { ...candles[0], role: 'SWING_1' },
        { ...candles[1], role: 'BREAKER' },
        { ...candles[2], role: 'DISPLACEMENT_BREAK' },
      ]}
      levels={{
        zones: [
          { key: 'breaker', label: 'Full-wick breaker block', lower: 10, upper: 11 },
          { key: 'fvg', label: 'Displacement FVG', lower: 11.2, upper: 12 },
        ],
        entry: 11,
        stop: 9.5,
        target: 14,
      }}
    />
  );

  expect(screen.getByText('Full-wick breaker block')).toBeInTheDocument();
  expect(screen.getByText('Displacement FVG')).toBeInTheDocument();
  expect(screen.getByText('SH1')).toBeInTheDocument();
  expect(screen.getByText('Breaker')).toBeInTheDocument();
  expect(screen.getByText('Break')).toBeInTheDocument();
});
