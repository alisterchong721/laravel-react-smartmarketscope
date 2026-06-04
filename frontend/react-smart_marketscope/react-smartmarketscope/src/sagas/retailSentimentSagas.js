import axios from 'axios';
import { apiPath } from '../config/api';
import { call, put, takeLatest } from 'redux-saga/effects';
import {
  FETCH_RETAIL_SENTIMENT_FILTERS_REQUEST,
  FETCH_RETAIL_SENTIMENT_REQUEST,
  fetchRetailSentimentFailure,
  fetchRetailSentimentFiltersFailure,
  fetchRetailSentimentFiltersSuccess,
  fetchRetailSentimentSuccess,
} from '../actions/retailSentimentActions';


const buildQueryParams = (query = {}) => {
  const params = {};

  if (query.group_by) {
    params.group_by = query.group_by;
  }

  if (query.pair) {
    params.pair = query.pair;
  }

  if (query.broker) {
    params.broker = query.broker;
  }

  if (Array.isArray(query.pairs) && query.pairs.length > 0) {
    params.pairs = query.pairs.join(',');
  }

  if (Array.isArray(query.brokers) && query.brokers.length > 0) {
    params.brokers = query.brokers.join(',');
  }

  if (query.refresh) {
    params.refresh = 1;
  }

  return params;
};

function* fetchRetailSentimentFiltersSaga() {
  try {
    const response = yield call(axios.get, apiPath('/retail-sentiment/filters'));
    const payload = response.data?.data || response.data;

    yield put(fetchRetailSentimentFiltersSuccess(payload));
  } catch (error) {
    yield put(
      fetchRetailSentimentFiltersFailure(
        error.response?.data?.message ||
          error.message ||
          'Failed to fetch retail sentiment filters'
      )
    );
  }
}

function* fetchRetailSentimentSaga(action) {
  try {
    const response = yield call(axios.get, apiPath('/retail-sentiment'), {
      params: buildQueryParams(action.payload),
    });

    const payload = response.data?.data || response.data;

    yield put(fetchRetailSentimentSuccess(payload));
  } catch (error) {
    yield put(
      fetchRetailSentimentFailure(
        error.response?.data?.message ||
          error.message ||
          'Failed to fetch retail sentiment data'
      )
    );
  }
}

export function* watchRetailSentiment() {
  yield takeLatest(
    FETCH_RETAIL_SENTIMENT_FILTERS_REQUEST,
    fetchRetailSentimentFiltersSaga
  );
  yield takeLatest(FETCH_RETAIL_SENTIMENT_REQUEST, fetchRetailSentimentSaga);
}
