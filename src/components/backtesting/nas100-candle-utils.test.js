import {
  enrichD1SweepsWithM1Status,
  filterD1Sweeps,
  filterNas100TechnicalSetups,
  formatConfluenceFamily,
  formatHistoricalOutcome,
  formatTechnicalTimeframe,
  mergeM1WindowWithSetupRoles,
  sortD1SweepsNewestFirst,
  sortSetupsNewestFirst,
  technicalChecklist,
  uniqueEventCount,
} from './nas100-candle-utils';

const setups = [
  {
    setupHash: 'a', eventId: 'D1-20240101-BULLISH', year: 2024, direction: 'BULLISH',
    timeframe: 'M1', family: 'C1_OB_FVG', fillStatus: 'FILLED', outcome: 'WIN_2R',
    decisionTime: '2024-01-02 12:00:00',
  },
  {
    setupHash: 'b', eventId: 'D1-20231201-BEARISH', year: 2023, direction: 'BEARISH',
    timeframe: 'M5', family: 'C2_FVG_BREAKER', fillStatus: 'NO_FILL', outcome: 'NO_FILL',
    decisionTime: '2023-12-02 12:00:00',
  },
  {
    setupHash: 'c', eventId: 'D1-20240101-BULLISH', year: 2024, direction: 'BULLISH',
    timeframe: 'HIERARCHICAL_M15_M5_M1', family: 'C1_OB_FVG', fillStatus: 'FILLED',
    outcome: 'LOSS_1R', decisionTime: '2024-01-02 13:00:00',
  },
];

test('filters the frozen setup census without changing setup inclusion', () => {
  expect(filterNas100TechnicalSetups(setups, {
    year: 2024,
    direction: 'BULLISH',
    timeframe: '',
    family: 'C1_OB_FVG',
    fillStatus: 'FILLED',
    query: 'd1-2024',
  })).toEqual([setups[0], setups[2]]);

  expect(filterNas100TechnicalSetups(setups, { query: 'breaker' })).toEqual([setups[1]]);
});

test('corrected D1 sweep filters and sorting use confirmation time without mutation', () => {
  const sweeps = [
    { sweepHash: 'a', eventId: 'D1-20240102-BULLISH', year: 2024, direction: 'BULLISH', h4Status: 'CONFIRMED', confirmationTime: '2024-01-03 00:00:00' },
    { sweepHash: 'b', eventId: 'D1-20231229-BEARISH', year: 2023, direction: 'BEARISH', h4Status: 'EXPIRED', confirmationTime: '2024-01-01 00:00:00' },
  ];

  expect(filterD1Sweeps(sweeps, {
    year: 2024,
    direction: 'BULLISH',
    h4Status: 'CONFIRMED',
    query: '20240102',
  })).toEqual([sweeps[0]]);
  expect(filterD1Sweeps(sweeps, { h4Status: 'EXPIRED' })).toEqual([sweeps[1]]);
  expect(sortD1SweepsNewestFirst([...sweeps].reverse()).map((row) => row.sweepHash)).toEqual(['a', 'b']);
  expect(sweeps.map((row) => row.sweepHash)).toEqual(['a', 'b']);
});

test('enriches and filters D1 sweeps by formed and filled M1 setup state', () => {
  const sweeps = [
    { sweepHash: 'filled', eventId: 'A' },
    { sweepHash: 'formed', eventId: 'B' },
    { sweepHash: 'none', eventId: 'C' },
  ];
  const enriched = enrichD1SweepsWithM1Status(sweeps, [
    { sweepHash: 'filled', candidateConfigurationCount: 2, filledConfigurationCount: 2 },
    { sweepHash: 'formed', candidateConfigurationCount: 2, filledConfigurationCount: 0 },
    { sweepHash: 'none', candidateConfigurationCount: 0, filledConfigurationCount: 0 },
  ]);

  expect(enriched.map((row) => row.setupState)).toEqual([
    'FILLED',
    'FORMED_NOT_FILLED',
    'NOT_FORMED',
  ]);
  expect(filterD1Sweeps(enriched, { setupState: 'FILLED' }).map((row) => row.sweepHash)).toEqual(['filled']);
  expect(filterD1Sweeps(enriched, { setupState: 'FORMED_ANY' }).map((row) => row.sweepHash)).toEqual(['filled', 'formed']);
  expect(filterD1Sweeps(enriched, { setupState: 'FORMED_NOT_FILLED' }).map((row) => row.sweepHash)).toEqual(['formed']);
  expect(filterD1Sweeps(enriched, { setupState: 'NOT_FORMED' }).map((row) => row.sweepHash)).toEqual(['none']);
  expect(sweeps[0]).not.toHaveProperty('setupState');
});

test('orders setups newest first and counts unique D1 plus H4 events', () => {
  expect(sortSetupsNewestFirst(setups).map((setup) => setup.setupHash)).toEqual(['c', 'a', 'b']);
  expect(uniqueEventCount(setups)).toBe(2);
  expect(setups.map((setup) => setup.setupHash)).toEqual(['a', 'b', 'c']);
});

test('formats frozen architecture, family, and outcome labels', () => {
  expect(formatTechnicalTimeframe('HIERARCHICAL_M15_M5_M1')).toBe('M15 → M5 → M1');
  expect(formatConfluenceFamily('C1_OB_FVG')).toBe('OB + FVG');
  expect(formatConfluenceFamily('C2_FVG_BREAKER')).toBe('FVG + Breaker');
  expect(formatHistoricalOutcome('AMBIGUOUS_ADVERSE_FIRST')).toBe('Ambiguous · adverse first');
});

test('keeps the detector checklist technical and shows only the selected architecture', () => {
  const detail = { summary: { timeframe: 'M1' }, checklist: [
    { label: 'Point-in-time macro direction', status: 'UNKNOWN' },
    { label: 'Daily liquidity sweep', status: 'PASS' },
    { label: 'H4 confirmation sweep', status: 'PASS' },
    { label: 'M15 technical setup', status: 'FAIL' },
    { label: 'M1 technical setup', status: 'PASS' },
    { label: 'Historical entry filled', status: 'PASS' },
    { label: 'Historical 2R target', status: 'FAIL' },
  ] };

  expect(technicalChecklist(detail).map((item) => item.label)).toEqual([
    'Daily liquidity sweep',
    'H4 confirmation sweep',
    'M1 technical setup',
  ]);
});

test('projects frozen setup roles onto the complete owning H4 M1 window', () => {
  const windowCandles = [
    { timestamp: '2026-06-24 16:00:00', role: null },
    { timestamp: '2026-06-24 16:01:00', role: null },
    { timestamp: '2026-06-24 19:59:00', role: null },
  ];
  const setupCandles = [
    { timestamp: '2026-06-24 16:01:00', role: 'BREAKER' },
  ];

  const projected = mergeM1WindowWithSetupRoles(windowCandles, setupCandles);

  expect(projected).toHaveLength(3);
  expect(projected.map((candle) => candle.role)).toEqual([null, 'BREAKER', null]);
  expect(projected.every((candle) => candle.eligibleWindow)).toBe(true);
  expect(windowCandles[1].role).toBeNull();
});
