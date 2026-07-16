import React from 'react';
import './historical-candle-chart.css';

const LEVEL_COLORS = {
  entry: '#60a5fa',
  stop: '#fb7185',
  target: '#34d399',
};

const ZONE_PRESENTATION = {
  breaker: { fill: '#a78bfa', text: '#c4b5fd' },
  fvg: { fill: '#2dd4bf', text: '#5eead4' },
  confluence: { fill: '#a78bfa', text: '#c4b5fd' },
};

const ROLE_PRESENTATION = {
  CANDLE_1: { color: '#93c5fd', label: 'C1' },
  CANDLE_2: { color: '#fbbf24', label: 'C2' },
  SWING_1: { color: '#93c5fd', label: 'SH1' },
  SWING_2: { color: '#fbbf24', label: 'SH2' },
  BREAKER: { color: '#c4b5fd', label: 'Breaker' },
  DISPLACEMENT_BREAK: { color: '#5eead4', label: 'Break' },
};

const optionalNumber = (value) => {
  if (value === null || value === undefined || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

export const lastCompletedCandleIndex = (candles = [], decisionTime) => {
  if (!decisionTime || !candles.length) return -1;

  let result = -1;
  candles.forEach((candle, index) => {
    const observableAt = candle.availableAt || candle.timestamp || '';
    if (String(observableAt) <= String(decisionTime)) result = index;
  });
  return result;
};

const HistoricalCandleChart = ({
  timeframe,
  candles = [],
  levels = {},
  decisionTime = null,
  decisionLabel = 'actionable time',
  referenceLevel = null,
  referenceLabel = 'reference',
  eligibleWindowLabel = 'D1 validity window',
}) => {
  if (!candles.length) {
    return (
      <div className="historical-chart-empty">
        <strong>{timeframe}</strong>
        <span>No source candles in this frozen window.</span>
      </div>
    );
  }

  const width = 820;
  const height = 300;
  const pad = { top: 20, right: 78, bottom: 42, left: 14 };
  const plotHeight = height - pad.top - pad.bottom;
  const plotWidth = width - pad.left - pad.right;
  const numeric = candles
    .flatMap((candle) => [Number(candle.low), Number(candle.high)])
    .filter(Number.isFinite);
  const lineLevels = ['entry', 'stop', 'target']
    .map((key) => ({ key, value: optionalNumber(levels[key]) }))
    .filter(({ value }) => value !== null);
  const numericReference = optionalNumber(referenceLevel);
  const explicitZones = Array.isArray(levels.zones)
    ? levels.zones.map((zone, index) => ({
      key: zone.key || `zone-${index}`,
      label: zone.label || 'frozen zone',
      lower: optionalNumber(zone.lower),
      upper: optionalNumber(zone.upper),
    })).filter((zone) => zone.lower !== null && zone.upper !== null)
    : [];
  const legacyZoneLower = optionalNumber(levels.zoneLower);
  const legacyZoneUpper = optionalNumber(levels.zoneUpper);
  const zones = explicitZones.length
    ? explicitZones
    : legacyZoneLower !== null && legacyZoneUpper !== null
      ? [{ key: 'confluence', label: 'frozen confluence zone', lower: legacyZoneLower, upper: legacyZoneUpper }]
      : [];
  const allValues = [
    ...numeric,
    ...lineLevels.map(({ value }) => value),
    ...zones.flatMap((zone) => [zone.lower, zone.upper]),
    ...(numericReference === null ? [] : [numericReference]),
  ];
  const minimum = Math.min(...allValues);
  const maximum = Math.max(...allValues);
  const range = maximum - minimum || 1;
  const y = (value) => pad.top + ((maximum - Number(value)) / range) * plotHeight;
  const step = plotWidth / candles.length;
  const candleWidth = Math.max(1.8, Math.min(9, step * 0.62));
  const decisionIndex = lastCompletedCandleIndex(candles, decisionTime);
  const decisionX = decisionIndex >= 0
    ? pad.left + step * decisionIndex + step / 2
    : null;
  const firstEligibleWindowIndex = candles.findIndex((candle) => candle.eligibleWindow === true);

  return (
    <figure className="historical-candle-card">
      <figcaption>
        <div>
          <strong>{timeframe}</strong>
          <span>{candles.length} completed candles</span>
        </div>
        <span>{candles[0].timestamp} → {candles[candles.length - 1].timestamp}</span>
      </figcaption>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${timeframe} historical candlestick window`}
      >
        <rect width={width} height={height} fill="#08111f" rx="14" />
        {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
          const gridY = pad.top + fraction * plotHeight;
          const gridValue = maximum - fraction * range;
          return (
            <g key={fraction}>
              <line
                x1={pad.left}
                x2={width - pad.right}
                y1={gridY}
                y2={gridY}
                stroke="#24324a"
                strokeDasharray="4 6"
              />
              <text x={width - pad.right + 8} y={gridY + 4} fill="#8190aa" fontSize="10">
                {gridValue.toFixed(1)}
              </text>
            </g>
          );
        })}

        {zones.map((zone, index) => {
          const presentation = ZONE_PRESENTATION[zone.key] || ZONE_PRESENTATION.confluence;
          const upperY = y(Math.max(zone.lower, zone.upper));
          return (
          <g key={zone.key}>
            <rect
              x={pad.left}
              width={plotWidth}
              y={upperY}
              height={Math.abs(y(zone.lower) - y(zone.upper)) || 2}
              fill={presentation.fill}
              opacity={index === 0 ? '0.18' : '0.14'}
            />
            <text
              x={pad.left + 5 + index * 112}
              y={Math.max(13, upperY - 4)}
              fill={presentation.text}
              fontSize="10"
            >
              {zone.label}
            </text>
          </g>
          );
        })}

        {candles.map((candle, index) => {
          const x = pad.left + step * index + step / 2;
          const open = Number(candle.open);
          const close = Number(candle.close);
          const isUp = close >= open;
          const color = isUp ? '#34d399' : '#fb7185';
          return (
            <g key={`${candle.timestamp}-${index}`}>
              {candle.eligibleWindow === true && (
                <>
                  <rect
                    x={x - step / 2}
                    width={step}
                    y={pad.top}
                    height={plotHeight}
                    fill="#a78bfa"
                    opacity="0.055"
                  />
                  {index === firstEligibleWindowIndex && (
                    <text x={x - step / 2 + 3} y={pad.top + 12} fill="#c4b5fd" fontSize="9">
                      {eligibleWindowLabel}
                    </text>
                  )}
                </>
              )}
              {candle.role && candle.role !== 'CONTEXT' && ROLE_PRESENTATION[candle.role] && (
                <>
                  <rect
                    x={x - step / 2}
                    width={step}
                    y={pad.top}
                    height={plotHeight}
                    fill={ROLE_PRESENTATION[candle.role].color}
                    opacity="0.1"
                  />
                  <text
                    x={x}
                    y={pad.top + 12}
                    fill={ROLE_PRESENTATION[candle.role].color}
                    fontSize="9"
                    textAnchor="middle"
                  >
                    {ROLE_PRESENTATION[candle.role].label}
                  </text>
                </>
              )}
              <line x1={x} x2={x} y1={y(candle.high)} y2={y(candle.low)} stroke={color} />
              <rect
                x={x - candleWidth / 2}
                y={Math.min(y(open), y(close))}
                width={candleWidth}
                height={Math.max(1.5, Math.abs(y(open) - y(close)))}
                fill={color}
              />
            </g>
          );
        })}

        {decisionX !== null && (
          <g>
            <line
              x1={decisionX}
              x2={decisionX}
              y1={pad.top}
              y2={height - pad.bottom}
              stroke="#fbbf24"
              strokeDasharray="3 4"
            />
            <text x={Math.min(decisionX + 5, width - 165)} y={pad.top + 12} fill="#fbbf24" fontSize="10">
              {decisionLabel}
            </text>
          </g>
        )}

        {numericReference !== null && (
          <g>
            <line
              x1={pad.left}
              x2={width - pad.right}
              y1={y(numericReference)}
              y2={y(numericReference)}
              stroke="#93c5fd"
              strokeDasharray="5 4"
            />
            <text
              x={width - pad.right + 7}
              y={y(numericReference) + 4}
              fill="#93c5fd"
              fontSize="10"
            >
              {referenceLabel} {numericReference}
            </text>
          </g>
        )}

        {lineLevels.map(({ key, value }) => (
          <g key={key}>
            <line
              x1={pad.left}
              x2={width - pad.right}
              y1={y(value)}
              y2={y(value)}
              stroke={LEVEL_COLORS[key]}
              strokeDasharray="7 5"
            />
            <text
              x={width - pad.right + 7}
              y={y(value) + 4}
              fill={LEVEL_COLORS[key]}
              fontSize="10"
            >
              {key} {value}
            </text>
          </g>
        ))}

        <text x={pad.left} y={height - 13} fill="#8190aa" fontSize="10">
          Source wall-clock labels · timezone unresolved · completed bars only
        </text>
      </svg>
    </figure>
  );
};

export default HistoricalCandleChart;
