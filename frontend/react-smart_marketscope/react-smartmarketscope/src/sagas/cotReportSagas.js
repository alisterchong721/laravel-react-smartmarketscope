import axios from 'axios';
import { apiPath } from '../config/api';
import { call, put, takeLatest } from 'redux-saga/effects';
import {
  FETCH_COT_REPORT_FILTERS_REQUEST,
  FETCH_COT_REPORT_REQUEST,
  fetchCotReportFailure,
  fetchCotReportFiltersFailure,
  fetchCotReportFiltersSuccess,
  fetchCotReportSuccess,
} from '../actions/cotReportActions';


const buildQueryParams = (query = {}) => {
  const params = {};

  if (query.asset) {
    params.asset = query.asset;
  }

  if (query.report_date) {
    params.report_date = query.report_date;
  }

  if (query.refresh) {
    params.refresh = 1;
  }

  return params;
};

function* fetchCotReportFiltersSaga() {
  try {
    const response = yield call(axios.get, apiPath('/cot-sentiment/filters'));
    const payload = response.data?.data || response.data;

    yield put(fetchCotReportFiltersSuccess(payload));
  } catch (error) {
    yield put(
      fetchCotReportFiltersFailure(
        error.response?.data?.message ||
          error.message ||
          'Failed to fetch COT filters'
      )
    );
  }
}

function* fetchCotReportSaga(action) {
  try {
    const response = yield call(axios.get, apiPath('/cot-sentiment'), {
      params: buildQueryParams(action.payload),
    });

    const payload = response.data?.data || response.data;

    yield put(fetchCotReportSuccess(payload));
  } catch (error) {
    yield put(
      fetchCotReportFailure(
        error.response?.data?.message ||
          error.message ||
          'Failed to fetch COT report data'
      )
    );
  }
}

export function* watchCotReport() {
  yield takeLatest(FETCH_COT_REPORT_FILTERS_REQUEST, fetchCotReportFiltersSaga);
  yield takeLatest(FETCH_COT_REPORT_REQUEST, fetchCotReportSaga);
}
