import axios from 'axios';
import { call, put, takeLatest } from 'redux-saga/effects';
import {
  FETCH_OVERVIEW_DASHBOARD_FILTERS_REQUEST,
  FETCH_OVERVIEW_DASHBOARD_REQUEST,
  fetchOverviewDashboardFailure,
  fetchOverviewDashboardFiltersFailure,
  fetchOverviewDashboardFiltersSuccess,
  fetchOverviewDashboardSuccess,
} from '../actions/overviewDashboardActions';

const API_URL = process.env.REACT_APP_API_URL || '/api';

const buildQueryParams = (query = {}) => {
  const params = {};

  if (Array.isArray(query.assets) && query.assets.length > 0) {
    params.assets = query.assets.join(',');
  }

  if (query.asset) {
    params.asset = query.asset;
  }

  if (query.news_lookback_hours) {
    params.news_lookback_hours = query.news_lookback_hours;
  }

  if (query.refresh) {
    params.refresh = 1;
  }

  return params;
};

function* fetchOverviewDashboardFiltersSaga() {
  try {
    const response = yield call(
      axios.get,
      `${API_URL}/overview-dashboard/filters`
    );
    const payload = response.data?.data || response.data;

    yield put(fetchOverviewDashboardFiltersSuccess(payload));
  } catch (error) {
    yield put(
      fetchOverviewDashboardFiltersFailure(
        error.response?.data?.message ||
          error.message ||
          'Failed to fetch overview dashboard filters'
      )
    );
  }
}

function* fetchOverviewDashboardSaga(action) {
  try {
    const response = yield call(axios.get, `${API_URL}/overview-dashboard`, {
      params: buildQueryParams(action.payload),
    });
    const payload = response.data?.data || response.data;

    yield put(fetchOverviewDashboardSuccess(payload));
  } catch (error) {
    yield put(
      fetchOverviewDashboardFailure(
        error.response?.data?.message ||
          error.message ||
          'Failed to fetch overview dashboard data'
      )
    );
  }
}

export function* watchOverviewDashboard() {
  yield takeLatest(
    FETCH_OVERVIEW_DASHBOARD_FILTERS_REQUEST,
    fetchOverviewDashboardFiltersSaga
  );
  yield takeLatest(FETCH_OVERVIEW_DASHBOARD_REQUEST, fetchOverviewDashboardSaga);
}
