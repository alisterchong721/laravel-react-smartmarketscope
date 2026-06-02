const warnAfterMs = Number(document.querySelector('meta[name="idle-session-warn-after-ms"]')?.content) || 30 * 60 * 1000;
const graceMs = Number(document.querySelector('meta[name="idle-session-grace-ms"]')?.content) || 5 * 60 * 1000;
const apiBase = document.querySelector('meta[name="api-base-url"]')?.content || '/api';
const loginPath = document.querySelector('meta[name="login-url"]')?.content || '/login';
const tokenKeys = ['auth_token', 'token', 'access_token', 'sanctum_token', 'smartmarketscope_token'];

let warnTimer;
let logoutTimer;
let countdownTimer;
let warningVisible = false;
let remainingSeconds = Math.ceil(graceMs / 1000);
let lastKeepAliveAt = Date.now();
const keepAliveThrottleMs = Math.min(10 * 60 * 1000, Math.max(60 * 1000, warnAfterMs / 2));

const getToken = () => {
    for (const key of tokenKeys) {
        const token = window.localStorage.getItem(key) || window.sessionStorage.getItem(key);

        if (token) {
            return token;
        }
    }

    return null;
};

const clearAuthStorage = () => {
    for (const key of tokenKeys) {
        window.localStorage.removeItem(key);
        window.sessionStorage.removeItem(key);
    }
};

const authHeaders = () => {
    const token = getToken();

    return token ? { Authorization: `Bearer ${token}` } : {};
};

const buildModal = () => {
    let modal = document.getElementById('idle-session-modal');

    if (modal) {
        return modal;
    }

    modal = document.createElement('div');
    modal.id = 'idle-session-modal';
    modal.className = 'idle-session-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'idle-session-title');
    modal.innerHTML = `
        <div class="idle-session-panel">
            <h2 id="idle-session-title">Are you still there?</h2>
            <p>Your session has been idle for 30 minutes. Choose continue to stay signed in.</p>
            <p class="idle-session-countdown">Signing out in <strong data-idle-countdown></strong>.</p>
            <div class="idle-session-actions">
                <button type="button" data-idle-logout>Sign out</button>
                <button type="button" data-idle-continue>Continue session</button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);
    modal.querySelector('[data-idle-continue]').addEventListener('click', keepAlive);
    modal.querySelector('[data-idle-logout]').addEventListener('click', logout);

    return modal;
};

const updateCountdown = () => {
    const countdown = document.querySelector('[data-idle-countdown]');

    if (countdown) {
        const minutes = Math.floor(remainingSeconds / 60);
        const seconds = String(remainingSeconds % 60).padStart(2, '0');
        countdown.textContent = `${minutes}:${seconds}`;
    }
};

const hideWarning = () => {
    warningVisible = false;
    clearTimeout(logoutTimer);
    clearInterval(countdownTimer);
    document.getElementById('idle-session-modal')?.classList.remove('is-visible');
};

const startIdleTimer = () => {
    clearTimeout(warnTimer);
    warnTimer = setTimeout(showWarning, warnAfterMs);
};

const keepAlive = async (event, silent = false) => {
    if (!silent) {
        hideWarning();
    }

    try {
        const response = await fetch(`${apiBase}/session/keep-alive`, {
            method: 'POST',
            headers: {
                Accept: 'application/json',
                ...authHeaders(),
            },
        });

        if (response.status === 401) {
            await logout();
            return;
        }

        lastKeepAliveAt = Date.now();
    } catch (error) {
        if (!silent) {
            await logout();
            return;
        }
    }

    if (!silent) {
        startIdleTimer();
    }
};

const logout = async () => {
    hideWarning();

    try {
        await fetch(`${apiBase}/logout`, {
            method: 'POST',
            headers: {
                Accept: 'application/json',
                ...authHeaders(),
            },
        });
    } catch (error) {
        // A failed logout request should not trap the user in an expired browser state.
    }

    clearAuthStorage();
    window.location.assign(loginPath);
};

const showWarning = () => {
    if (!getToken()) {
        return;
    }

    warningVisible = true;
    remainingSeconds = Math.ceil(graceMs / 1000);

    const modal = buildModal();
    modal.classList.add('is-visible');
    updateCountdown();

    countdownTimer = setInterval(() => {
        remainingSeconds -= 1;
        updateCountdown();
    }, 1000);

    logoutTimer = setTimeout(logout, graceMs);
};

const userEvents = ['click', 'keydown', 'mousemove', 'scroll', 'touchstart'];

for (const eventName of userEvents) {
    window.addEventListener(eventName, () => {
        if (!warningVisible && getToken()) {
            if (Date.now() - lastKeepAliveAt > keepAliveThrottleMs) {
                keepAlive(null, true);
            }

            startIdleTimer();
        }
    }, { passive: true });
}

if (getToken()) {
    startIdleTimer();
}
