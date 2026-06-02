import React, { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import { logoutSuccess } from '../actions/authActions';
import './idle-session-timeout.css';

const WARN_AFTER_MS = 30 * 60 * 1000;
const GRACE_MS = 5 * 60 * 1000;
const KEEP_ALIVE_THROTTLE_MS = 10 * 60 * 1000;

const activityEvents = [
  'click',
  'keydown',
  'mousemove',
  'scroll',
  'touchstart',
];

const clearAuthState = () => {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  delete axios.defaults.headers.common.Authorization;
};

const IdleSessionTimeout = () => {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { isAuthenticated } = useSelector((state) => state.auth);
  const [isWarningVisible, setIsWarningVisible] = useState(false);
  const [remainingSeconds, setRemainingSeconds] = useState(GRACE_MS / 1000);
  const warnTimerRef = useRef(null);
  const logoutTimerRef = useRef(null);
  const countdownTimerRef = useRef(null);
  const lastKeepAliveAtRef = useRef(Date.now());
  const warningVisibleRef = useRef(false);

  const hasToken = useCallback(() => Boolean(localStorage.getItem('token')), []);
  const shouldWatchSession = isAuthenticated || hasToken();

  const clearTimers = useCallback(() => {
    window.clearTimeout(warnTimerRef.current);
    window.clearTimeout(logoutTimerRef.current);
    window.clearInterval(countdownTimerRef.current);
  }, []);

  const logout = useCallback(async () => {
    clearTimers();
    warningVisibleRef.current = false;
    setIsWarningVisible(false);

    try {
      if (hasToken()) {
        await axios.post('/logout');
      }
    } catch (error) {
      console.log('session logout error', error);
    } finally {
      clearAuthState();
      dispatch(logoutSuccess());
      navigate('/login', { replace: true });
    }
  }, [clearTimers, dispatch, hasToken, navigate]);

  const startWarningTimer = useCallback(() => {
    window.clearTimeout(warnTimerRef.current);
    warnTimerRef.current = window.setTimeout(() => {
      if (!hasToken()) {
        return;
      }

      warningVisibleRef.current = true;
      setRemainingSeconds(GRACE_MS / 1000);
      setIsWarningVisible(true);

      countdownTimerRef.current = window.setInterval(() => {
        setRemainingSeconds((seconds) => Math.max(seconds - 1, 0));
      }, 1000);

      logoutTimerRef.current = window.setTimeout(logout, GRACE_MS);
    }, WARN_AFTER_MS);
  }, [hasToken, logout]);

  const keepAlive = useCallback(
    async ({ silent = false } = {}) => {
      if (!hasToken()) {
        return;
      }

      try {
        await axios.post('/session/keep-alive');
        lastKeepAliveAtRef.current = Date.now();
      } catch (error) {
        if (!silent || error.response?.status === 401) {
          await logout();
        }

        return;
      }

      if (!silent) {
        window.clearTimeout(logoutTimerRef.current);
        window.clearInterval(countdownTimerRef.current);
        warningVisibleRef.current = false;
        setIsWarningVisible(false);
        startWarningTimer();
      }
    },
    [hasToken, logout, startWarningTimer]
  );

  useEffect(() => {
    if (!shouldWatchSession) {
      clearTimers();
      setIsWarningVisible(false);
      return undefined;
    }

    const handleActivity = () => {
      if (warningVisibleRef.current || !hasToken()) {
        return;
      }

      if (Date.now() - lastKeepAliveAtRef.current > KEEP_ALIVE_THROTTLE_MS) {
        keepAlive({ silent: true });
      }

      startWarningTimer();
    };

    startWarningTimer();
    keepAlive({ silent: true });
    activityEvents.forEach((eventName) => {
      window.addEventListener(eventName, handleActivity, { passive: true });
    });

    return () => {
      clearTimers();
      activityEvents.forEach((eventName) => {
        window.removeEventListener(eventName, handleActivity);
      });
    };
  }, [
    clearTimers,
    hasToken,
    keepAlive,
    shouldWatchSession,
    startWarningTimer,
  ]);

  if (!isWarningVisible) {
    return null;
  }

  const minutes = Math.floor(remainingSeconds / 60);
  const seconds = String(remainingSeconds % 60).padStart(2, '0');

  return (
    <div className="idle-session-modal" role="dialog" aria-modal="true">
      <div className="idle-session-panel">
        <h2>Are you still there?</h2>
        <p>
          Your session has been idle for 30 minutes. Choose continue to stay
          signed in.
        </p>
        <p className="idle-session-countdown">
          Signing out in <strong>{minutes}:{seconds}</strong>.
        </p>
        <div className="idle-session-actions">
          <button type="button" onClick={logout}>
            Sign out
          </button>
          <button type="button" onClick={() => keepAlive()}>
            Continue session
          </button>
        </div>
      </div>
    </div>
  );
};

export default IdleSessionTimeout;
