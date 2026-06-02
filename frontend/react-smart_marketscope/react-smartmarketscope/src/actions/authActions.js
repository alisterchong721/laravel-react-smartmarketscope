// Action types that describes what happens
export const REGISTER_REQUEST = 'REGISTER_REQUEST';
export const REGISTER_SUCCESS = 'REGISTER_SUCCESS';
export const REGISTER_FAILURE = 'REGISTER_FAILURE';
export const VERIFY_REGISTER_REQUEST = 'VERIFY_REGISTER_REQUEST';
export const VERIFY_REGISTER_SUCCESS = 'VERIFY_REGISTER_SUCCESS';
export const VERIFY_REGISTER_FAILURE = 'VERIFY_REGISTER_FAILURE';
export const RESEND_REGISTER_CODE_REQUEST = 'RESEND_REGISTER_CODE_REQUEST';
export const RESEND_REGISTER_CODE_SUCCESS = 'RESEND_REGISTER_CODE_SUCCESS';
export const RESEND_REGISTER_CODE_FAILURE = 'RESEND_REGISTER_CODE_FAILURE';

export const LOGIN_REQUEST = 'LOGIN_REQUEST';
export const LOGIN_SUCCESS = 'LOGIN_SUCCESS';
export const LOGIN_FAILURE = 'LOGIN_FAILURE';

export const LOGOUT_REQUEST = 'LOGOUT_REQUEST';
export const LOGOUT_SUCCESS = 'LOGOUT_SUCCESS';
// Add this constant
export const RESET_AUTH_STATE = 'RESET_AUTH_STATE';

// Add this action creator
export const resetAuthState = () => ({
  type: RESET_AUTH_STATE,
});
// Action creators
export const registerRequest = (payload) => ({
  type: REGISTER_REQUEST,
  payload,
});
export const registerSuccess = (payload) => ({
  type: REGISTER_SUCCESS,
  payload,
});
export const registerFailure = (payload) => ({
  type: REGISTER_FAILURE,
  payload,
});

export const verifyRegisterRequest = (payload) => ({
  type: VERIFY_REGISTER_REQUEST,
  payload,
});
export const verifyRegisterSuccess = (payload) => ({
  type: VERIFY_REGISTER_SUCCESS,
  payload,
});
export const verifyRegisterFailure = (payload) => ({
  type: VERIFY_REGISTER_FAILURE,
  payload,
});

export const resendRegisterCodeRequest = (payload) => ({
  type: RESEND_REGISTER_CODE_REQUEST,
  payload,
});
export const resendRegisterCodeSuccess = (payload) => ({
  type: RESEND_REGISTER_CODE_SUCCESS,
  payload,
});
export const resendRegisterCodeFailure = (payload) => ({
  type: RESEND_REGISTER_CODE_FAILURE,
  payload,
});

export const loginRequest = (payload) => ({ type: LOGIN_REQUEST, payload });
export const loginSuccess = (payload) => ({ type: LOGIN_SUCCESS, payload });
export const loginFailure = (payload) => ({ type: LOGIN_FAILURE, payload });

export const logoutRequest = (payload) => ({ type: LOGOUT_REQUEST });
export const logoutSuccess = (payload) => ({ type: LOGOUT_SUCCESS });
