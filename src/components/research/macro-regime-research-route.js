import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Navigate, useLocation } from 'react-router-dom';
import { apiPath } from '../../config/api';
import MacroRegimeResearch from './macro-regime-research';
import {
  authorizeMacroRegimeResearch,
  hasUnsupportedResourceSelector,
  verifiedRegisteredUser,
} from './macro-regime-access-policy';

const MacroRegimeResearchRoute = () => {
  const location = useLocation();
  const [state, setState] = useState({ status: 'loading', user: null });
  const unsupportedSelector = hasUnsupportedResourceSelector(location);

  useEffect(() => {
    if (unsupportedSelector) {
      setState({ status: 'selector-denied', user: null });
      return undefined;
    }

    const token = localStorage.getItem('token');
    if (!token) {
      setState({ status: 'unauthenticated', user: null });
      return undefined;
    }

    const controller = new AbortController();
    setState({ status: 'loading', user: null });
    axios.get(apiPath('/me'), {
      headers: { Accept: 'application/json', Authorization: `Bearer ${token}` },
      signal: controller.signal,
    }).then((response) => {
      const user = verifiedRegisteredUser(response);
      const authorization = authorizeMacroRegimeResearch(user);
      setState(authorization.allowed ? { status: 'allowed', user } : { status: 'identity-denied', user: null });
    }).catch((error) => {
      if (error?.code === 'ERR_CANCELED') return;
      const responseStatus = error?.response?.status;
      setState({ status: responseStatus === 401 || responseStatus === 403 ? 'unauthenticated' : 'verification-error', user: null });
    });

    return () => controller.abort();
  }, [unsupportedSelector]);

  if (state.status === 'loading') {
    return <main aria-busy="true" aria-live="polite"><p>Verifying access with Smart MarketScope…</p></main>;
  }

  if (state.status === 'unauthenticated') {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (state.status === 'selector-denied') {
    return <main role="alert"><h1>Research resource denied</h1><p>This page does not accept resource identifiers, query selectors, or fragments.</p></main>;
  }

  if (state.status !== 'allowed') {
    return <main role="alert"><h1>Research access denied</h1><p>Smart MarketScope could not verify an authorized registered-user identity.</p></main>;
  }

  return <MacroRegimeResearch verifiedUser={state.user} />;
};

export default MacroRegimeResearchRoute;
