import {
  REGISTER_REQUEST,
  REGISTER_SUCCESS,
  REGISTER_FAILURE,
  VERIFY_REGISTER_REQUEST,
  VERIFY_REGISTER_SUCCESS,
  VERIFY_REGISTER_FAILURE,
  RESEND_REGISTER_CODE_REQUEST,
  RESEND_REGISTER_CODE_SUCCESS,
  RESEND_REGISTER_CODE_FAILURE,
  LOGIN_REQUEST,
  LOGIN_SUCCESS,
  LOGIN_FAILURE,
  LOGOUT_REQUEST,
  LOGOUT_SUCCESS,
  RESET_AUTH_STATE,
} from '../actions/authActions';

// SIMPLIFIED: Always check localStorage directly
const initialState = {
  loading: false,
  user: null,
  token: null,
  isAuthenticated: false, // Will be updated by saga
  registrationVerificationSent: false,
  pendingRegistrationEmail: null,
  registrationVerified: false,
  lastRegistrationAction: null,
  resendCooldownSeconds: 0,
  error: null,
};

export default function authReducer(state = initialState, action) {
  switch (action.type) {
    case RESET_AUTH_STATE:
      return {
        ...state,
        user: null, // Clear the user from the last registration
        error: null, // Clear any old error messages
        loading: false,
        registrationVerificationSent: false,
        pendingRegistrationEmail: null,
        registrationVerified: false,
        lastRegistrationAction: null,
        resendCooldownSeconds: 0,
      };
    case REGISTER_REQUEST:
    case VERIFY_REGISTER_REQUEST:
    case RESEND_REGISTER_CODE_REQUEST:
    case LOGIN_REQUEST:
      return { ...state, loading: true, error: null, lastRegistrationAction: null };

    case LOGIN_SUCCESS:
      return {
        ...state,
        loading: false,
        token: action.payload.token,
        user: action.payload.user,
        isAuthenticated: true,
      };

    case 'TOKEN_LOADED':
      return {
        ...state,
        token: action.payload.token,
        user: action.payload.user,
        isAuthenticated: !!action.payload.token,
      };

    case REGISTER_SUCCESS:
      return {
        ...state,
        loading: false,
        registrationVerificationSent: true,
        pendingRegistrationEmail: action.payload.email,
        registrationVerified: false,
        lastRegistrationAction: 'register',
        resendCooldownSeconds: action.payload.retryAfterSeconds || 0,
        user: null,
        isAuthenticated: false, // Registration ≠ authentication
      };

    case RESEND_REGISTER_CODE_SUCCESS:
      return {
        ...state,
        loading: false,
        registrationVerificationSent: true,
        pendingRegistrationEmail: action.payload.email || state.pendingRegistrationEmail,
        registrationVerified: false,
        lastRegistrationAction: 'resend',
        resendCooldownSeconds: action.payload.retryAfterSeconds || 300,
      };

    case VERIFY_REGISTER_SUCCESS:
      return {
        ...state,
        loading: false,
        token: action.payload.token,
        user: action.payload.user,
        isAuthenticated: true,
        registrationVerificationSent: false,
        pendingRegistrationEmail: null,
        registrationVerified: true,
        lastRegistrationAction: 'verify',
        resendCooldownSeconds: 0,
      };

    case LOGOUT_SUCCESS:
      return {
        ...state,
        token: null,
        user: null,
        isAuthenticated: false,
      };

    case REGISTER_FAILURE:
    case VERIFY_REGISTER_FAILURE:
    case RESEND_REGISTER_CODE_FAILURE:
    case LOGIN_FAILURE:
      return {
        ...state,
        loading: false,
        error: action.payload.message || action.payload,
        resendCooldownSeconds: action.payload.retryAfterSeconds || state.resendCooldownSeconds,
      };

    default:
      return state;
  }
}
