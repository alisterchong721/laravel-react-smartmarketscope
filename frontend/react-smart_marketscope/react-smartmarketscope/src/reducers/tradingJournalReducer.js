import {
  FETCH_TRADES_REQUEST,
  FETCH_TRADES_SUCCESS,
  FETCH_TRADES_FAILURE,
  CREATE_TRADE_REQUEST,
  CREATE_TRADE_SUCCESS,
  CREATE_TRADE_FAILURE,
  UPDATE_TRADE_REQUEST,
  UPDATE_TRADE_SUCCESS,
  UPDATE_TRADE_FAILURE,
  DELETE_TRADE_REQUEST,
  DELETE_TRADE_SUCCESS,
  DELETE_TRADE_FAILURE,
} from '../actions/tradingJounalActions';

const initialState = {
  trades: [],
  loading: false,
  error: null,
  lastAction: null, // Track last action for debugging
};

const tradingJournalReducer = (state = initialState, action) => {
  console.log('📦 Reducer action:', action.type, 'payload:', action.payload);

  switch (action.type) {
    case FETCH_TRADES_REQUEST:
      return {
        ...state,
        loading: true,
        error: null,
        lastAction: 'FETCH_TRADES_REQUEST',
      };

    case CREATE_TRADE_REQUEST:
    case DELETE_TRADE_REQUEST:
      return {
        ...state,
        loading: true,
        error: null,
        lastAction: action.type,
      };
    case UPDATE_TRADE_REQUEST:
      console.log('📦 UPDATE_TRADE_REQUEST payload:', action.payload);
      console.log('Payload id:', action.payload?.id);
      console.log('Payload id type:', typeof action.payload?.id);
      console.log('Full payload structure:');
      Object.keys(action.payload || {}).forEach((key) => {
        console.log(
          `  ${key}:`,
          action.payload[key],
          `(type: ${typeof action.payload[key]})`
        );
      });

      return {
        ...state,
        loading: true,
        error: null,
        lastAction: 'UPDATE_TRADE_REQUEST',
      };

    case FETCH_TRADES_SUCCESS:
      console.log('✅ FETCH_TRADES_SUCCESS payload:', action.payload);
      return {
        ...state,
        loading: false,
        error: null,
        trades: action.payload || [],
        lastAction: 'FETCH_TRADES_SUCCESS',
      };

    case CREATE_TRADE_SUCCESS:
      return {
        ...state,
        loading: false,
        success: true,
        successMessage: 'Trade created successfully',
        error: null,
      };

    case UPDATE_TRADE_SUCCESS:
      return {
        ...state,
        loading: false,
        success: true,
        successMessage: 'Trade updated successfully',
        error: null,
      };

    case DELETE_TRADE_SUCCESS:
      return {
        ...state,
        loading: false,
        deleteSuccess: true,
        successMessage: 'Trade deleted successfully',
        error: null,
      };

    case FETCH_TRADES_FAILURE:
    case CREATE_TRADE_FAILURE:
    case UPDATE_TRADE_FAILURE:
    case DELETE_TRADE_FAILURE:
      console.log('❌ Error action:', action.type, 'error:', action.payload);
      return {
        ...state,
        loading: false,
        error: action.payload,
        lastAction: action.type + '_FAILURE',
      };

    default:
      return state;
  }
};

export default tradingJournalReducer;
