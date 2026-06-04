import axios from 'axios';
window.axios = axios;

window.axios.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';
window.axios.defaults.headers.common['Accept'] = 'application/json';

const configuredApiBaseUrl = document.querySelector('meta[name="api-base-url"]')?.content
    || import.meta.env.VITE_API_BASE_URL
    || '/api';

window.axios.defaults.baseURL = configuredApiBaseUrl.replace(/\/+$/, '');

window.axios.interceptors.request.use((config) => {
    if (config.url?.startsWith('/api/') && window.axios.defaults.baseURL.endsWith('/api')) {
        config.url = config.url.slice(4);
    }

    return config;
});

window.axios.interceptors.response.use(
    (response) => response,
    (error) => {
        if (import.meta.env.DEV || import.meta.env.VITE_DEBUG_AXIOS === 'true') {
            console.error('Axios response error:', error.response);
            console.error('Axios request error:', error.request);
            console.error('Axios error message:', error.message);
        }

        const responseMessage = error.response?.data?.message;

        if (responseMessage) {
            error.message = responseMessage;
        } else if (!error.response && !error.request) {
            error.message = error.message || 'Request failed';
        }

        return Promise.reject(error);
    },
);
