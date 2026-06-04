const DEFAULT_API_URL = '/api';

const normalizeApiUrl = (configuredUrl) => {
  const apiUrl = configuredUrl?.trim();

  if (!apiUrl) {
    return DEFAULT_API_URL;
  }

  if (
    typeof window !== 'undefined' &&
    window.location.protocol === 'https:' &&
    apiUrl.startsWith('http://')
  ) {
    return DEFAULT_API_URL;
  }

  return apiUrl.replace(/\/+$/, '');
};

export const API_URL = normalizeApiUrl(process.env.REACT_APP_API_URL);

export const apiPath = (path) => {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;

  if (API_URL === DEFAULT_API_URL) {
    return normalizedPath;
  }

  return `${API_URL}${normalizedPath}`;
};
