import {
  FETCH_COT_REPORT_FAILURE,
  FETCH_COT_REPORT_FILTERS_FAILURE,
  FETCH_COT_REPORT_FILTERS_REQUEST,
  FETCH_COT_REPORT_FILTERS_SUCCESS,
  FETCH_COT_REPORT_REQUEST,
  FETCH_COT_REPORT_SUCCESS,
  SET_COT_REPORT_QUERY,
} from '../actions/cotReportActions';

const initialState = {
  query: {
    asset: null,
    report_date: null,
  },
  filtersMeta: null,
  filtersLoading: false,
  filtersError: null,
  reportData: null,
  loading: false,
  error: null,
  lastUpdated: null,
};

const cotReportReducer = (state = initialState, action) => {
  switch (action.type) {
    case FETCH_COT_REPORT_FILTERS_REQUEST:
      return {
        ...state,
        filtersLoading: true,
        filtersError: null,
      };

    case FETCH_COT_REPORT_FILTERS_SUCCESS:
      return {
        ...state,
        filtersLoading: false,
        filtersMeta: action.payload,
        filtersError: null,
      };

    case FETCH_COT_REPORT_FILTERS_FAILURE:
      return {
        ...state,
        filtersLoading: false,
        filtersError: action.payload,
      };

    case SET_COT_REPORT_QUERY:
      return {
        ...state,
        query: {
          ...state.query,
          ...action.payload,
        },
      };

    case FETCH_COT_REPORT_REQUEST:
      return {
        ...state,
        loading: true,
        error: null,
      };

    case FETCH_COT_REPORT_SUCCESS:
      return {
        ...state,
        loading: false,
        reportData: action.payload,
        error: null,
        lastUpdated: new Date().toISOString(),
      };

    case FETCH_COT_REPORT_FAILURE:
      return {
        ...state,
        loading: false,
        error: action.payload,
      };

    default:
      return state;
  }
};

export default cotReportReducer;
