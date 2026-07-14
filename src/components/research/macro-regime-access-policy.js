export const MACRO_REGIME_RESEARCH_PATH = '/research/macro-regime';

export const verifiedRegisteredUser = (payload) => {
  const user = payload?.data?.data ?? payload?.data ?? null;
  const id = user?.id;
  const email = user?.email;
  const validId = (Number.isInteger(id) && id > 0) || (typeof id === 'string' && /^[1-9]\d*$/.test(id));
  const validEmail = typeof email === 'string' && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  return validId && validEmail ? Object.freeze({ id: String(id), email }) : null;
};

export const authorizeMacroRegimeResearch = (verifiedUser) => Object.freeze({
  allowed: Boolean(verifiedUser?.id && verifiedUser?.email),
  policy: 'VERIFIED_REGISTERED_USER_READ_ONLY',
});

export const hasUnsupportedResourceSelector = (location) => (
  location.pathname !== MACRO_REGIME_RESEARCH_PATH || Boolean(location.search) || Boolean(location.hash)
);
