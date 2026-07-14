import React from 'react';
import { render, screen } from '@testing-library/react';
import MacroRegimeResearch from './macro-regime-research';

test('renders server-verified read-only evidence and all immutable charts without execution controls', () => {
  render(<MacroRegimeResearch verifiedUser={{ id: '7', email: 'researcher@example.com' }} />);
  expect(screen.getByText(/VERIFIED_REGISTERED_USER_READ_ONLY \(verified\)/)).toBeInTheDocument();
  expect(screen.getByText('INSUFFICIENT_ALIGNED_TRADES.')).toBeInTheDocument();
  expect(screen.getByText('-173.457870R')).toBeInTheDocument();
  expect(screen.getAllByText('UNKNOWN').length).toBeGreaterThan(0);
  expect(screen.getByText(/NOT_APPLICABLE_ZERO_RETENTION/)).toBeInTheDocument();
  expect(screen.getAllByRole('img')).toHaveLength(11);
  expect(screen.getAllByRole('img').every((image) => image.getAttribute('alt'))).toBe(true);
  expect(screen.getByText(/Latest active indicator drill-down/)).toBeInTheDocument();
  expect(screen.getAllByText(/J0 \+36h/).length).toBeGreaterThan(0);
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
  expect(screen.queryByText(/place order/i)).not.toBeInTheDocument();
});
