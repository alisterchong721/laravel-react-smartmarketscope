const includesQuery = (setup, query) => {
  const normalized = query.trim().toLowerCase();

  if (!normalized) return true;

  return [
    setup.eventId,
    setup.direction,
    setup.timeframe,
    setup.family,
    setup.decisionTime,
    setup.fillStatus,
    setup.outcome,
  ].some((value) => String(value || '').toLowerCase().includes(normalized));
};

export const filterNas100TechnicalSetups = (setups = [], filters = {}) => (
  setups.filter((setup) => (
    (!filters.year || String(setup.year) === String(filters.year))
    && (!filters.direction || setup.direction === filters.direction)
    && (!filters.timeframe || setup.timeframe === filters.timeframe)
    && (!filters.family || setup.family === filters.family)
    && (!filters.fillStatus || setup.fillStatus === filters.fillStatus)
    && includesQuery(setup, filters.query || '')
  ))
);

export const sortSetupsNewestFirst = (setups = []) => (
  [...setups].sort((left, right) => (
    String(right.decisionTime || '').localeCompare(String(left.decisionTime || ''))
    || String(right.setupHash || '').localeCompare(String(left.setupHash || ''))
  ))
);

export const uniqueValues = (setups = [], key) => (
  [...new Set(setups.map((setup) => setup[key]).filter(Boolean))].sort()
);

export const uniqueEventCount = (setups = []) => (
  new Set(setups.map((setup) => setup.eventId).filter(Boolean)).size
);

export const formatTechnicalTimeframe = (value) => (
  value === 'HIERARCHICAL_M15_M5_M1' ? 'M15 → M5 → M1' : value || '—'
);

export const formatConfluenceFamily = (value) => {
  if (value === 'C1_OB_FVG') return 'OB + FVG';
  if (value === 'C2_FVG_BREAKER') return 'FVG + Breaker';
  return value || '—';
};

export const formatHistoricalOutcome = (value) => ({
  WIN_2R: '2R reached',
  LOSS_1R: 'Stop first',
  NO_FILL: 'No fill',
  TIMEOUT: 'Expired',
  AMBIGUOUS_ADVERSE_FIRST: 'Ambiguous · adverse first',
}[value] || value || '—');

export const outcomeTone = (value) => ({
  WIN_2R: 'green',
  LOSS_1R: 'red',
  NO_FILL: 'default',
  TIMEOUT: 'gold',
  AMBIGUOUS_ADVERSE_FIRST: 'volcano',
}[value] || 'default');

export const technicalChecklist = (detail) => (
  (detail?.checklist || []).filter((item) => {
    const timeframe = detail?.summary?.timeframe || '';
    const alwaysVisible = [
      'Daily liquidity sweep',
      'Daily trend context',
      'H4 confirmation sweep',
    ];

    if (alwaysVisible.includes(item.label)) return true;
    if (timeframe === 'HIERARCHICAL_M15_M5_M1') {
      return ['M15 technical setup', 'M5 technical setup', 'M1 technical setup'].includes(item.label);
    }

    return item.label === `${timeframe} technical setup`;
  })
);

export const filterD1Sweeps = (sweeps = [], filters = {}) => (
  sweeps.filter((sweep) => {
    const query = String(filters.query || '').trim().toLowerCase();
    const matchesQuery = !query || [
      sweep.eventId,
      sweep.direction,
      sweep.candle1Start,
      sweep.candle2Start,
      sweep.confirmationTime,
    ].some((value) => String(value || '').toLowerCase().includes(query));

    const matchesSetupState = !filters.setupState
      || (filters.setupState === 'FORMED_ANY'
        ? Number(sweep.formedConfigurationCount || 0) > 0
        : sweep.setupState === filters.setupState);

    return matchesQuery
      && (!filters.year || String(sweep.year) === String(filters.year))
      && (!filters.direction || sweep.direction === filters.direction)
      && (!filters.h4Status || sweep.h4Status === filters.h4Status)
      && matchesSetupState;
  })
);

export const enrichD1SweepsWithM1Status = (sweeps = [], breakerEvents = []) => {
  const eventByHash = new Map(
    breakerEvents.map((event) => [event.sweepHash, event])
  );

  return sweeps.map((sweep) => {
    const event = eventByHash.get(sweep.sweepHash);
    const formedConfigurationCount = Number(event?.candidateConfigurationCount || 0);
    const filledConfigurationCount = Number(event?.filledConfigurationCount || 0);
    const setupState = filledConfigurationCount > 0
      ? 'FILLED'
      : formedConfigurationCount > 0
        ? 'FORMED_NOT_FILLED'
        : 'NOT_FORMED';

    return {
      ...sweep,
      formedConfigurationCount,
      filledConfigurationCount,
      setupState,
    };
  });
};

export const sortD1SweepsNewestFirst = (sweeps = []) => (
  [...sweeps].sort((left, right) => (
    String(right.confirmationTime || '').localeCompare(String(left.confirmationTime || ''))
    || String(right.sweepHash || '').localeCompare(String(left.sweepHash || ''))
  ))
);

export const mergeM1WindowWithSetupRoles = (windowCandles = [], setupCandles = []) => {
  const roleByTimestamp = new Map(
    setupCandles
      .filter((candle) => candle.timestamp && candle.role)
      .map((candle) => [candle.timestamp, candle.role])
  );

  return windowCandles.map((candle) => ({
    ...candle,
    eligibleWindow: true,
    role: roleByTimestamp.get(candle.timestamp) || candle.role || null,
  }));
};
