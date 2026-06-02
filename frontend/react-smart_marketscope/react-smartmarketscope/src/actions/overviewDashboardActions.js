export const FETCH_OVERVIEW_DASHBOARD_FILTERS_REQUEST =
  'FETCH_OVERVIEW_DASHBOARD_FILTERS_REQUEST';
export const FETCH_OVERVIEW_DASHBOARD_FILTERS_SUCCESS =
  'FETCH_OVERVIEW_DASHBOARD_FILTERS_SUCCESS';
export const FETCH_OVERVIEW_DASHBOARD_FILTERS_FAILURE =
  'FETCH_OVERVIEW_DASHBOARD_FILTERS_FAILURE';

export const FETCH_OVERVIEW_DASHBOARD_REQUEST =
  'FETCH_OVERVIEW_DASHBOARD_REQUEST';
export const FETCH_OVERVIEW_DASHBOARD_SUCCESS =
  'FETCH_OVERVIEW_DASHBOARD_SUCCESS';
export const FETCH_OVERVIEW_DASHBOARD_FAILURE =
  'FETCH_OVERVIEW_DASHBOARD_FAILURE';

export const SET_OVERVIEW_DASHBOARD_QUERY = 'SET_OVERVIEW_DASHBOARD_QUERY';

export const fetchOverviewDashboardFiltersRequest = () => ({
  type: FETCH_OVERVIEW_DASHBOARD_FILTERS_REQUEST,
});

export const fetchOverviewDashboardFiltersSuccess = (data) => ({
  type: FETCH_OVERVIEW_DASHBOARD_FILTERS_SUCCESS,
  payload: data,
});

export const fetchOverviewDashboardFiltersFailure = (error) => ({
  type: FETCH_OVERVIEW_DASHBOARD_FILTERS_FAILURE,
  payload: error,
});

export const fetchOverviewDashboardRequest = (query = {}) => ({
  type: FETCH_OVERVIEW_DASHBOARD_REQUEST,
  payload: query,
});

export const fetchOverviewDashboardSuccess = (data) => ({
  type: FETCH_OVERVIEW_DASHBOARD_SUCCESS,
  payload: data,
});

export const fetchOverviewDashboardFailure = (error) => ({
  type: FETCH_OVERVIEW_DASHBOARD_FAILURE,
  payload: error,
});

export const setOverviewDashboardQuery = (query) => ({
  type: SET_OVERVIEW_DASHBOARD_QUERY,
  payload: query,
});
