import React from 'react';
import { render, screen } from '@testing-library/react';
import MacroRegimeResearch from './macro-regime-research';

test('renders fail-closed research state without execution controls', () => {
  render(<MacroRegimeResearch />);
  expect(screen.getByText('INSUFFICIENT_ALIGNED_TRADES.')).toBeInTheDocument();
  expect(screen.getByText('-173.457870R')).toBeInTheDocument();
  expect(screen.getAllByText('UNKNOWN').length).toBeGreaterThan(0);
  expect(screen.getByText(/NOT_APPLICABLE_ZERO_RETENTION/)).toBeInTheDocument();
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
  expect(screen.queryByText(/place order/i)).not.toBeInTheDocument();
});
