import { call, put, takeLatest } from 'redux-saga/effects';
import axios from 'axios';
import {
  FETCH_CURRENCY_PAIR_REQUEST,
  fetchCurrencyPairSuccess,
  fetchCurrencyPairFailure,
} from '../actions/fundamentalPairActions';

const API_URL = 'http://127.0.0.1:8000/api';

function* fetchCurrencyPairSaga(action) {
  console.log('🔥 Saga: Fetching currency pair:', action.payload.pair);

  try {
    const { pair } = action.payload;

    const response = yield call(
      axios.get,
      `${API_URL}/fundamental/pair/${pair}`
    );

    console.log('✅ API Response:', response.data);

    // IMPORTANT: Check the actual response structure
    // If your API returns {success: true, data: {...}}
    // Then the data is at response.data.data
    if (response.data.success && response.data.data) {
      console.log('📦 Found data at response.data.data:', response.data.data);
      yield put(fetchCurrencyPairSuccess(response.data.data));
    }
    // If your API returns {pair: "...", base_score: ...} directly
    else if (response.data.pair) {
      console.log('📦 Found data at response.data:', response.data);
      yield put(fetchCurrencyPairSuccess(response.data));
    }
    // If response.data is already the data object
    else {
      console.log('📦 Using response.data as data:', response.data);
      yield put(fetchCurrencyPairSuccess(response.data));
    }
  } catch (error) {
    console.error('❌ Currency Pair Saga Error:', {
      message: error.message,
      response: error.response?.data,
      status: error.response?.status,
    });

    yield put(
      fetchCurrencyPairFailure(
        error.response?.data?.message ||
          error.message ||
          'Failed to fetch currency pair data'
      )
    );
  }
}

export function* watchCurrencyPair() {
  console.log('👀 Currency pair saga watcher initialized');
  yield takeLatest(FETCH_CURRENCY_PAIR_REQUEST, fetchCurrencyPairSaga);
}
