import { call, put, takeLatest, takeEvery } from 'redux-saga/effects';
import axios from 'axios';
import { API_URL } from '../config/api';
import {
  REGISTER_REQUEST,
  registerSuccess,
  registerFailure,
  VERIFY_REGISTER_REQUEST,
  verifyRegisterSuccess,
  verifyRegisterFailure,
  RESEND_REGISTER_CODE_REQUEST,
  resendRegisterCodeSuccess,
  resendRegisterCodeFailure,
  LOGIN_REQUEST,
  loginSuccess,
  loginFailure,
  LOGOUT_REQUEST,
} from '../actions/authActions';


// Set up axios defaults
axios.defaults.baseURL = API_URL;
axios.defaults.headers.common.Accept = 'application/json';

const getAxiosErrorMessage = (error, fallbackMessage) => {
  if (process.env.NODE_ENV !== 'production') {
    console.error('Axios response error:', error.response);
    console.error('Axios request error:', error.request);
    console.error('Axios error message:', error.message);
  }

  if (error.response) {
    const responseData = error.response.data;

    if (responseData?.message) {
      return responseData.message;
    }

    if (responseData?.errors) {
      return Object.values(responseData.errors).flat().join(' ');
    }

    if (typeof responseData === 'string') {
      return responseData;
    }

    return fallbackMessage;
  }

  return error.message || fallbackMessage;
};

// Store token in localStorage and axios headers
function setAuthToken(token) {
  if (token) {
    localStorage.setItem('token', token);
    axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  } else {
    localStorage.removeItem('token');
    delete axios.defaults.headers.common['Authorization'];
  }
}

// Load token on app startup
function* loadTokenOnStartup() {
  console.log('🔍 loadTokenOnStartup STARTED');
  try {
    const token = localStorage.getItem('token');
    console.log('🔍 Token from localStorage:', token);
    const userStr = localStorage.getItem('user');

    if (token) {
      console.log('🔍 Setting axios header with token');
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;

      // Parse user data
      let user = null;
      try {
        user = userStr ? JSON.parse(userStr) : null;
      } catch (error) {
        console.error('Error parsing user:', error);
      }

      console.log('🔍 Dispatching TOKEN_LOADED with token:', !!token);
      yield put({
        type: 'TOKEN_LOADED',
        payload: { token, user },
      });
      console.log('🔍 TOKEN_LOADED dispatched');
    } else {
      console.log('🔍 No token found in localStorage');
    }
  } catch (error) {
    console.error('Error loading token:', error);
  }
  console.log('🔍 loadTokenOnStartup COMPLETED');
}

function registerApi(payload) {
  return axios.post('/register', payload, { withCredentials: false });
}

function verifyRegisterApi(payload) {
  return axios.post('/register/verify', payload, { withCredentials: false });
}

function resendRegisterCodeApi(payload) {
  return axios.post('/register/resend', payload, { withCredentials: false });
}

function loginApi(payload) {
  return axios.post('/login', payload);
}

function logoutApi() {
  return axios.post('/logout');
}

function* registerSaga(action) {
  try {
    console.log('🔍 Register saga started with payload:', action.payload);
    const response = yield call(registerApi, action.payload);
    console.log('🔍 Register API response:', response);
    console.log('🔍 Response data:', response.data);

    yield put(registerSuccess({
      email: response.data.data?.email || action.payload.email,
      expiresInMinutes: response.data.data?.expires_in_minutes,
      retryAfterSeconds: response.data.data?.retry_after_seconds || 0,
    }));
    console.log('✅ Verification code sent');
  } catch (error) {
    console.error('🔍 Registration error:', error);
    const errorMessage = getAxiosErrorMessage(error, 'Registration failed');
    yield put(registerFailure(errorMessage));
    console.log('❌ Registration failed');
  }
}

function* resendRegisterCodeSaga(action) {
  try {
    const response = yield call(resendRegisterCodeApi, action.payload);

    yield put(resendRegisterCodeSuccess({
      email: response.data.data?.email || action.payload.email,
      expiresInMinutes: response.data.data?.expires_in_minutes,
      retryAfterSeconds: response.data.data?.retry_after_seconds || 300,
    }));
  } catch (error) {
    const errorMessage = getAxiosErrorMessage(error, 'Failed to resend verification code');

    yield put(resendRegisterCodeFailure({
      message: errorMessage,
      retryAfterSeconds: error.response?.data?.data?.retry_after_seconds,
    }));
  }
}

function* verifyRegisterSaga(action) {
  try {
    console.log('🔍 Verify registration saga started with payload:', action.payload);
    const response = yield call(verifyRegisterApi, action.payload);

    const token = response.data.data?.token;
    const user = response.data.data?.user;

    if (!token) {
      throw new Error('No token received from server');
    }

    setAuthToken(token);
    if (user) {
      localStorage.setItem('user', JSON.stringify(user));
    }

    yield put(verifyRegisterSuccess({ token, user }));
    console.log('✅ Registration verified and user authenticated');
  } catch (error) {
    console.error('🔍 Verify registration error:', error);
    const errorMessage = getAxiosErrorMessage(error, 'Verification failed');
    yield put(verifyRegisterFailure(errorMessage));
  }
}

function* loginSaga(action) {
  try {
    console.log('🔍 Login saga started with payload:', action.payload);
    const response = yield call(loginApi, action.payload);
    console.log('🔍 Login API response:', response);
    console.log('🔍 Response data:', response.data);

    // FIXED: Correct response structure for your API
    const token = response.data.data?.token; // Token is inside data object
    const user = response.data.data?.user; // User is inside data object

    console.log('🔍 Extracted token:', token);
    console.log('🔍 Extracted user:', user);

    if (!token) {
      console.error('🔍 No token found in response.data.data');
      console.error('🔍 Full response.data:', response.data);
      throw new Error('No token received from server');
    }

    // Store token and user data
    setAuthToken(token);
    if (user) {
      localStorage.setItem('user', JSON.stringify(user));
    } else {
      // Fallback user data if not provided
      localStorage.setItem(
        'user',
        JSON.stringify({
          email: action.payload.email,
          name: action.payload.email.split('@')[0],
        })
      );
    }

    console.log(
      '🔍 Token saved to localStorage:',
      localStorage.getItem('token')
    );
    console.log('🔍 User saved to localStorage:', localStorage.getItem('user'));

    yield put(loginSuccess({ token, user }));
    console.log('🔍 login success - dispatched loginSuccess');
  } catch (error) {
    console.error('🔍 Login error:', error);
    yield put(loginFailure(getAxiosErrorMessage(error, 'Login failed')));
    console.log('login failed');
  }
}

// Logout saga
function* logoutSaga() {
  try {
    try {
      yield call(logoutApi);
    } catch (error) {
      console.log('logout api error', error);
    }

    // Clear local storage
    localStorage.removeItem('token');
    localStorage.removeItem('user');

    // Clear axios headers
    delete axios.defaults.headers.common['Authorization'];

    // Dispatch logout success
    yield put({ type: 'LOGOUT_SUCCESS' });
    console.log('logout success');
  } catch (error) {
    console.log('logout error', error);
  }
}

export default function* authWatcher() {
  // Load token when app starts
  yield takeEvery('APP_STARTUP', loadTokenOnStartup);

  yield takeLatest(REGISTER_REQUEST, registerSaga);
  yield takeLatest(RESEND_REGISTER_CODE_REQUEST, resendRegisterCodeSaga);
  yield takeLatest(VERIFY_REGISTER_REQUEST, verifyRegisterSaga);
  yield takeLatest(LOGIN_REQUEST, loginSaga);
  yield takeLatest(LOGOUT_REQUEST, logoutSaga);
}
