import React from 'react';
import { render, screen } from '@testing-library/react';
import axios from 'axios';
import MacroRegimeResearchRoute from './macro-regime-research-route';
import {
  authorizeMacroRegimeResearch,
  hasUnsupportedResourceSelector,
  verifiedRegisteredUser,
} from './macro-regime-access-policy';

jest.mock('axios', () => ({ get: jest.fn() }), { virtual: true });
const mockUseLocation = jest.fn();
jest.mock('react-router-dom', () => ({
  Navigate: ({ to }) => <div>navigate to {to}</div>,
  useLocation: () => mockUseLocation(),
}), { virtual: true });

const renderRoute = (initialEntry = '/research/macro-regime') => {
  const parsed = new URL(initialEntry, 'https://smartmarketscope.test');
  mockUseLocation.mockReturnValue({ pathname: parsed.pathname, search: parsed.search, hash: parsed.hash });
  return render(<MacroRegimeResearchRoute />);
};

beforeEach(() => {
  localStorage.clear();
  jest.clearAllMocks();
  mockUseLocation.mockReset();
});

test('redirects without a token and makes no verification request', async () => {
  renderRoute();
  expect(await screen.findByText('navigate to /login')).toBeInTheDocument();
  expect(axios.get).not.toHaveBeenCalled();
});

test.each([401, 403])('rejects an unverified token when /me returns %s', async (status) => {
  localStorage.setItem('token', 'stale-or-forbidden');
  axios.get.mockRejectedValue({ response: { status } });
  renderRoute();
  expect(await screen.findByText('navigate to /login')).toBeInTheDocument();
  expect(axios.get).toHaveBeenCalledTimes(1);
});

test('fails closed for malformed identity payloads', async () => {
  localStorage.setItem('token', 'opaque-token');
  axios.get.mockResolvedValue({ data: { data: { id: 0, email: 'malformed' } } });
  renderRoute();
  expect(await screen.findByRole('heading', { name: 'Research access denied' })).toBeInTheDocument();
});

test('renders only after /me verifies a registered user and sends a bearer credential', async () => {
  localStorage.setItem('token', 'opaque-token');
  axios.get.mockResolvedValue({ data: { data: { id: 7, email: 'researcher@example.com' } } });
  renderRoute();
  expect(await screen.findByRole('heading', { name: 'Macro regime evidence' })).toBeInTheDocument();
  expect(axios.get).toHaveBeenCalledWith('/me', expect.objectContaining({
    headers: { Accept: 'application/json', Authorization: 'Bearer opaque-token' },
    signal: expect.any(AbortSignal),
  }));
});

test('keeps the verification loading state fail closed', () => {
  localStorage.setItem('token', 'opaque-token');
  axios.get.mockReturnValue(new Promise(() => {}));
  renderRoute();
  expect(screen.getByText(/Verifying access/).closest('main')).toHaveAttribute('aria-busy', 'true');
});

test('denies verification transport errors without rendering evidence', async () => {
  localStorage.setItem('token', 'opaque-token');
  axios.get.mockRejectedValue(new Error('offline'));
  renderRoute();
  expect(await screen.findByRole('heading', { name: 'Research access denied' })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Macro regime evidence' })).not.toBeInTheDocument();
});

test.each([
  '/research/macro-regime?user_id=7',
  '/research/macro-regime?resource=other',
  '/research/macro-regime#other',
])('denies unsupported resource selectors at %s without a request', async (path) => {
  localStorage.setItem('token', 'opaque-token');
  renderRoute(path);
  expect(await screen.findByRole('heading', { name: 'Research resource denied' })).toBeInTheDocument();
  expect(axios.get).not.toHaveBeenCalled();
});

test('an extra path identifier cannot reach the protected component', async () => {
  localStorage.setItem('token', 'opaque-token');
  renderRoute('/research/macro-regime/7');
  expect(await screen.findByRole('heading', { name: 'Research resource denied' })).toBeInTheDocument();
  expect(axios.get).not.toHaveBeenCalled();
});

test('policy requires a positive id and syntactically valid email', async () => {
  expect(verifiedRegisteredUser({ data: { data: { id: '4', email: 'r@example.com' } } })).toEqual({ id: '4', email: 'r@example.com' });
  expect(verifiedRegisteredUser({ data: { data: { id: -1, email: 'r@example.com' } } })).toBeNull();
  expect(verifiedRegisteredUser({ data: { data: { id: 4, email: 'bad' } } })).toBeNull();
  expect(authorizeMacroRegimeResearch(null).allowed).toBe(false);
  expect(hasUnsupportedResourceSelector({ pathname: '/research/macro-regime', search: '', hash: '' })).toBe(false);
  expect(axios.get).not.toHaveBeenCalled();
});
