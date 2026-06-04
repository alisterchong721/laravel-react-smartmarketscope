import axios from 'axios';
import { apiPath } from '../config/api';
import { call, put, takeLatest } from 'redux-saga/effects';
import {
  FETCH_NEWS_SENTIMENT_FILTERS_REQUEST,
  FETCH_NEWS_SENTIMENT_REQUEST,
  fetchNewsSentimentFailure,
  fetchNewsSentimentFiltersFailure,
  fetchNewsSentimentFiltersSuccess,
  fetchNewsSentimentSuccess,
} from '../actions/newsSentimentActions';


const buildQueryParams = (query = {}) => {
  const params = {};

  if (Array.isArray(query.assets) && query.assets.length > 0) {
    params.assets = query.assets.join(',');
  }

  if (query.status) {
    params.status = query.status;
  }

  if (query.limit) {
    params.limit = query.limit;
  }

  if (query.refresh) {
    params.refresh = 1;
  }

  return params;
};

function* fetchNewsSentimentFiltersSaga() {
  try {
    const response = yield call(axios.get, apiPath('/news-sentiment/filters'));
    const payload = response.data?.data || response.data;

    yield put(fetchNewsSentimentFiltersSuccess(payload));
  } catch (error) {
    yield put(
      fetchNewsSentimentFiltersFailure(
        error.response?.data?.message ||
          error.message ||
          'Failed to fetch news sentiment filters'
      )
    );
  }
}

function* fetchNewsSentimentSaga(action) {
  try {
    const response = yield call(axios.get, apiPath('/news-sentiment'), {
      params: buildQueryParams(action.payload),
    });
    const payload = response.data?.data || response.data;

    yield put(fetchNewsSentimentSuccess(payload));
  } catch (error) {
    yield put(
      fetchNewsSentimentFailure(
        error.response?.data?.message ||
          error.message ||
          'Failed to fetch news sentiment data'
      )
    );
  }
}

export function* watchNewsSentiment() {
  yield takeLatest(
    FETCH_NEWS_SENTIMENT_FILTERS_REQUEST,
    fetchNewsSentimentFiltersSaga
  );
  yield takeLatest(FETCH_NEWS_SENTIMENT_REQUEST, fetchNewsSentimentSaga);
}
