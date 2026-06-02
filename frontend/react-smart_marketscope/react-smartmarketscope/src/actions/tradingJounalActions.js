export const FETCH_TRADES_REQUEST = 'FETCH_TRADES_REQUEST';
export const FETCH_TRADES_SUCCESS = 'FETCH_TRADES_SUCCESS';
export const FETCH_TRADES_FAILURE = 'FETCH_TRADES_FAILURE';

export const CREATE_TRADE_REQUEST = 'CREATE_TRADE_REQUEST';
export const CREATE_TRADE_SUCCESS = 'CREATE_TRADE_SUCCESS';
export const CREATE_TRADE_FAILURE = 'CREATE_TRADE_FAILURE';

export const UPDATE_TRADE_REQUEST = 'UPDATE_TRADE_REQUEST';
export const UPDATE_TRADE_SUCCESS = 'UPDATE_TRADE_SUCCESS';
export const UPDATE_TRADE_FAILURE = 'UPDATE_TRADE_FAILURE';

export const DELETE_TRADE_REQUEST = 'DELETE_TRADE_REQUEST';
export const DELETE_TRADE_SUCCESS = 'DELETE_TRADE_SUCCESS';
export const DELETE_TRADE_FAILURE = 'DELETE_TRADE_FAILURE';

export const RESET_SUCCESS_STATE = 'RESET_SUCCESS_STATE';

export const fetchTradesRequest = (userId) => ({
  type: FETCH_TRADES_REQUEST,
  payload: userId,
});

export const fetchTradesSuccess = (trades) => ({
  type: FETCH_TRADES_SUCCESS,
  payload: trades,
});

export const fetchTradesFailure = (error) => ({
  type: FETCH_TRADES_FAILURE,
  payload: error,
});

export const createTradeRequest = (tradeData) => ({
  type: CREATE_TRADE_REQUEST,
  payload: tradeData,
});

export const createTradeSuccess = (trade) => ({
  type: CREATE_TRADE_SUCCESS,
  payload: trade,
});

export const createTradeFailure = (error) => ({
  type: CREATE_TRADE_FAILURE,
  payload: error,
});

export const updateTradeRequest = (tradeId, tradeData) => ({
  type: UPDATE_TRADE_REQUEST,
  payload: {
    id: tradeId,
    ...tradeData,
  },
});

export const updateTradeSuccess = (trade) => ({
  type: UPDATE_TRADE_SUCCESS,
  payload: trade,
});

export const updateTradeFailure = (error) => ({
  type: UPDATE_TRADE_FAILURE,
  payload: error,
});

export const deleteTradeRequest = (id) => ({
  type: DELETE_TRADE_REQUEST,
  payload: id,
});

export const deleteTradeSuccess = (id) => ({
  type: DELETE_TRADE_SUCCESS,
  payload: id,
});

export const deleteTradeFailure = (error) => ({
  type: DELETE_TRADE_FAILURE,
  payload: error,
});

export const resetSuccessState = () => ({
  type: RESET_SUCCESS_STATE,
});
