import { call, put, takeLatest } from 'redux-saga/effects';
import axios from 'axios';
import {
  FETCH_TRADES_REQUEST,
  fetchTradesSuccess,
  fetchTradesFailure,
  CREATE_TRADE_REQUEST,
  createTradeSuccess,
  createTradeFailure,
  UPDATE_TRADE_REQUEST,
  updateTradeSuccess,
  updateTradeFailure,
  DELETE_TRADE_REQUEST,
  deleteTradeSuccess,
  deleteTradeFailure,
} from '../actions/tradingJounalActions';

// API URL
const API_URL = 'http://127.0.0.1:8000/api';

// get user from localStorage
const getUser = () => {
  const userStr = localStorage.getItem('user');
  return userStr ? JSON.parse(userStr) : null;
};

function* fetchTradeSaga() {
  try {
    const user = getUser();
    const userId = user?.id;

    const response = yield call(
      axios.get,
      `${API_URL}/tradeRecords/get-by-user`,
      { params: { user_id: userId } }
    );

    if (response.data.success) {
      yield put(fetchTradesSuccess(response.data.data));
    } else {
      throw new Error(response.data.message || 'Failed to fetch trades');
    }
  } catch (error) {
    yield put(
      fetchTradesFailure(error.response?.data?.message || error.message)
    );
  }
}

function* createTradeSaga(action) {
  try {
    const user = getUser();
    const userId = user?.id;

    const tradeData = {
      ...action.payload,
      user_id: userId,
    };

    const response = yield call(
      axios.post,
      `${API_URL}/tradeRecords/create`,
      tradeData
    );

    if (response.data.success) {
      yield put(createTradeSuccess(response.data.data));
      // After successful creation, refetch trades
      yield put({ type: FETCH_TRADES_REQUEST });
    } else {
      throw new Error(response.data.message || 'Failed to create trade');
    }
  } catch (error) {
    yield put(
      createTradeFailure(error.response?.data?.message || error.message)
    );
  }
}

function* deleteTradeSaga(action) {
  try {
    const user = getUser();
    const userId = user?.id;

    // ✅ Now action.payload is just the ID (not an object)
    const tradeId = action.payload;

    console.log('Delete trade:', { tradeId, userId });

    // Prepare query parameters - include user_id
    const params = new URLSearchParams({
      id: tradeId,
      user_id: userId,
    });

    const response = yield call(
      axios.post,
      `${API_URL}/tradeRecords/delete?${params.toString()}`
    );

    console.log('Delete response:', response.data);

    if (response.data.success) {
      yield put(deleteTradeSuccess(tradeId));
      yield put({ type: FETCH_TRADES_REQUEST });
      // Show success message
    } else {
      throw new Error(response.data.message || 'Failed to delete trade');
    }
  } catch (error) {
    console.error('Delete trade error:', error);
    yield put(
      deleteTradeFailure(error.response?.data?.message || error.message)
    );
  }
}

// Fix updateTradeSaga to handle the nested structure correctly:
function* updateTradeSaga(action) {
  console.log('🔄 updateTradeSaga called');
  console.log('Action payload:', action.payload);

  try {
    const user = getUser();
    const userId = user?.id;

    // Extract id and trade data from payload
    const { id, ...tradeData } = action.payload;

    console.log('Trade ID:', id);
    console.log('Trade data:', tradeData);
    console.log('User ID:', userId);

    if (!id) {
      throw new Error('Trade ID is required for update');
    }

    // Prepare query parameters
    const params = new URLSearchParams({
      id: id,
      user_id: userId,
    });

    console.log(
      'Making API call to:',
      `${API_URL}/tradeRecords/update?${params.toString()}`
    );
    console.log('With data:', tradeData);

    const response = yield call(
      axios.post,
      `${API_URL}/tradeRecords/update?${params.toString()}`,
      tradeData
    );

    console.log('Update response:', response.data);

    if (response.data.success) {
      yield put(updateTradeSuccess(response.data.data));
      yield put({ type: FETCH_TRADES_REQUEST });
    } else {
      throw new Error(response.data.message || 'Failed to update trade');
    }
  } catch (error) {
    console.error('Update trade error:', error);
    console.error('Error response:', error.response?.data);
    yield put(
      updateTradeFailure(error.response?.data?.message || error.message)
    );
  }
}

export function* watchTradingJournal() {
  yield takeLatest(FETCH_TRADES_REQUEST, fetchTradeSaga);
  yield takeLatest(CREATE_TRADE_REQUEST, createTradeSaga);
  yield takeLatest(UPDATE_TRADE_REQUEST, updateTradeSaga);
  yield takeLatest(DELETE_TRADE_REQUEST, deleteTradeSaga);
}
