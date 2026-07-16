import fs from 'fs';
import path from 'path';

test('NAS100 Candle is a protected sibling route with frozen D1, H4, and M1 breaker/FVG evidence', () => {
  const appSource = fs.readFileSync(path.join(__dirname, '../../App.js'), 'utf8');
  const pageSource = fs.readFileSync(path.join(__dirname, 'nas100-candle.js'), 'utf8');

  expect(appSource).toContain('path="/backtesting/nas100-candle"');
  expect(appSource).toContain('<Nas100Candle />');
  expect(pageSource).toContain("apiPath('/research/d1-h4-sweep-review')");
  expect(pageSource).toContain('payload.h4ConfirmedCount !== payload.sweeps.length');
  expect(pageSource).toContain('Nested D1 and H4 intrabar sweep activations');
  expect(pageSource).toContain('does not wait for a D1 or H4 candle to close');
  expect(pageSource).toContain('timeframe="H4"');
  expect(pageSource).toContain('M1 breaker + displacement FVG inside the active H4 candle');
  expect(pageSource).toContain('2R and 2.5R independently');
  expect(pageSource).toContain('neither target survives normalized costs');
  expect(pageSource).toContain('detail.breakerFvg.configurations');
  expect(pageSource).toContain('zones: selectedBreaker.zones');
  expect(pageSource).toContain('Breaker proximal-edge entry');
  expect(pageSource).toContain('Beyond distal breaker wick');
  expect(pageSource).toContain('All M1 setup states');
  expect(pageSource).toContain('Not formed · 0 / 0');
  expect(pageSource).toContain('detail.m1WindowReview.candles');
  expect(pageSource).toContain('M1 chart for the complete H4 window');
  expect(pageSource).toContain('No new entry, stop, target, fill, outcome, or execution is created');
});
