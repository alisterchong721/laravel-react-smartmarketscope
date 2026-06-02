export const FETCH_COT_REPORT_FILTERS_REQUEST =
  'FETCH_COT_REPORT_FILTERS_REQUEST';
export const FETCH_COT_REPORT_FILTERS_SUCCESS =
  'FETCH_COT_REPORT_FILTERS_SUCCESS';
export const FETCH_COT_REPORT_FILTERS_FAILURE =
  'FETCH_COT_REPORT_FILTERS_FAILURE';

export const FETCH_COT_REPORT_REQUEST = 'FETCH_COT_REPORT_REQUEST';
export const FETCH_COT_REPORT_SUCCESS = 'FETCH_COT_REPORT_SUCCESS';
export const FETCH_COT_REPORT_FAILURE = 'FETCH_COT_REPORT_FAILURE';

export const SET_COT_REPORT_QUERY = 'SET_COT_REPORT_QUERY';

export const fetchCotReportFiltersRequest = () => ({
  type: FETCH_COT_REPORT_FILTERS_REQUEST,
});

export const fetchCotReportFiltersSuccess = (data) => ({
  type: FETCH_COT_REPORT_FILTERS_SUCCESS,
  payload: data,
});

export const fetchCotReportFiltersFailure = (error) => ({
  type: FETCH_COT_REPORT_FILTERS_FAILURE,
  payload: error,
});

export const fetchCotReportRequest = (query = {}) => ({
  type: FETCH_COT_REPORT_REQUEST,
  payload: query,
});

export const fetchCotReportSuccess = (data) => ({
  type: FETCH_COT_REPORT_SUCCESS,
  payload: data,
});

export const fetchCotReportFailure = (error) => ({
  type: FETCH_COT_REPORT_FAILURE,
  payload: error,
});

export const setCotReportQuery = (query) => ({
  type: SET_COT_REPORT_QUERY,
  payload: query,
});
