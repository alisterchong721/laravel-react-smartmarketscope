import dayjs from 'dayjs';
import fs from 'fs';
import path from 'path';
import {
  buildTradeSubmitPayload,
  prepareJournalDateForInput,
  prepareJournalDateForBackend,
} from './trading-journal-utils';

describe('trading journal date handling', () => {
  it('round-trips saved UTC timestamps through native datetime-local input strings', () => {
    const savedEntryTime = '2026-05-06T08:56:00.000Z';
    const savedExitTime = '2026-05-06T09:06:00.000Z';

    const entryInputValue = prepareJournalDateForInput(savedEntryTime);
    const exitInputValue = prepareJournalDateForInput(savedExitTime);

    expect(entryInputValue).toBe('2026-05-06T16:56');
    expect(exitInputValue).toBe('2026-05-06T17:06');
    expect(prepareJournalDateForBackend(entryInputValue)).toBe(savedEntryTime);
    expect(prepareJournalDateForBackend(exitInputValue)).toBe(savedExitTime);
  });

  it('keeps native datetime-local input state unchanged when non-date form values change', () => {
    const savedEntryTime = '2026-05-06T08:56:00.000Z';
    const savedExitTime = '2026-05-06T09:06:00.000Z';
    const formValues = {
      asset_symbol: 'USDJPY',
      direction: 'BUY',
      entry_price: 1.00002,
      exit_price: 1.55004,
      profit_loss: 50,
    };

    const entryTimeValue = prepareJournalDateForInput(savedEntryTime);
    const exitTimeValue = prepareJournalDateForInput(savedExitTime);

    formValues.entry_price = 1.00003;
    formValues.exit_price = 1.55005;
    formValues.profit_loss = 55;

    expect(entryTimeValue).toBe('2026-05-06T16:56');
    expect(exitTimeValue).toBe('2026-05-06T17:06');
    expect(prepareJournalDateForBackend(entryTimeValue)).toBe(savedEntryTime);
    expect(prepareJournalDateForBackend(exitTimeValue)).toBe(savedExitTime);
  });

  it('omits untouched date fields from edit payloads', () => {
    const payload = buildTradeSubmitPayload({
      values: {
        asset_symbol: 'usdjpy',
        direction: 'BUY',
        entry_price: 1.00002,
        exit_price: 1.55004,
        profit_loss: 50,
      },
      entryTimeValue: '2026-05-07T23:24',
      exitTimeValue: '2026-05-07T23:25',
      isEditing: true,
      dateFieldsTouched: { entry_time: false, exit_time: false },
    });

    expect(payload).toEqual({
      asset_symbol: 'USDJPY',
      direction: 'BUY',
      entry_price: 1.00002,
      exit_price: 1.55004,
      profit_loss: 50,
    });
  });

  it('includes only changed date fields in edit payloads', () => {
    const payload = buildTradeSubmitPayload({
      values: {
        asset_symbol: 'USDJPY',
        direction: 'BUY',
        entry_price: 1.00002,
        exit_price: 1.55004,
        profit_loss: 50,
      },
      entryTimeValue: '2026-05-07T23:24',
      exitTimeValue: '2026-05-07T23:25',
      isEditing: true,
      dateFieldsTouched: { entry_time: false, exit_time: true },
    });

    expect(payload).not.toHaveProperty('entry_time');
    expect(payload.exit_time).toBe('2026-05-07T15:25:00.000Z');
  });

  it('serializes intentionally changed picker dates', () => {
    const changedEntryTime = dayjs('2026-05-07T19:30:00');

    expect(prepareJournalDateForBackend(changedEntryTime)).toBe(
      '2026-05-07T11:30:00.000Z'
    );
  });

  it('uses native datetime-local inputs outside Ant Design form field management', () => {
    const source = fs.readFileSync(
      path.join(__dirname, 'trading-journal.js'),
      'utf8'
    );

    expect(source).not.toMatch(/name="entry_time"/);
    expect(source).not.toMatch(/name="exit_time"/);
    expect(source).not.toMatch(/<DatePicker/);
    expect(source).toMatch(/type="datetime-local"/);
    expect(source).toMatch(/value=\{entryTimeValue\}/);
    expect(source).toMatch(/value=\{exitTimeValue\}/);
  });
});
