import {
  FETCH_OVERVIEW_DASHBOARD_FAILURE,
  FETCH_OVERVIEW_DASHBOARD_FILTERS_FAILURE,
  FETCH_OVERVIEW_DASHBOARD_FILTERS_REQUEST,
  FETCH_OVERVIEW_DASHBOARD_FILTERS_SUCCESS,
  FETCH_OVERVIEW_DASHBOARD_REQUEST,
  FETCH_OVERVIEW_DASHBOARD_SUCCESS,
  SET_OVERVIEW_DASHBOARD_QUERY,
} from '../actions/overviewDashboardActions';

const initialState = {
  query: {
    assets: [],
    news_lookback_hours: null,
  },
  filtersMeta: null,
  filtersLoading: false,
  filtersError: null,
  overviewData: null,
  loading: false,
  error: null,
  lastUpdated: null,
};

const overviewDashboardReducer = (state = initialState, action) => {
  switch (action.type) {
    case FETCH_OVERVIEW_DASHBOARD_FILTERS_REQUEST:
      return {
        ...state,
        filtersLoading: true,
        filtersError: null,
      };

    case FETCH_OVERVIEW_DASHBOARD_FILTERS_SUCCESS:
      return {
        ...state,
        filtersLoading: false,
        filtersError: null,
        filtersMeta: action.payload,
        query: {
          ...state.query,
          assets: state.query.assets?.length
            ? state.query.assets
            : action.payload?.default_assets || [],
          news_lookback_hours:
            state.query.news_lookback_hours ||
            action.payload?.default_news_lookback_hours ||
            null,
        },
      };

    case FETCH_OVERVIEW_DASHBOARD_FILTERS_FAILURE:
      return {
        ...state,
        filtersLoading: false,
        filtersError: action.payload,
      };

    case SET_OVERVIEW_DASHBOARD_QUERY:
      return {
        ...state,
        query: {
          ...state.query,
          ...action.payload,
        },
      };

    case FETCH_OVERVIEW_DASHBOARD_REQUEST:
      return {
        ...state,
        loading: true,
        error: null,
      };

    case FETCH_OVERVIEW_DASHBOARD_SUCCESS:
      return {
        ...state,
        loading: false,
        overviewData: action.payload,
        error: null,
        lastUpdated: new Date().toISOString(),
      };

    case FETCH_OVERVIEW_DASHBOARD_FAILURE:
      return {
        ...state,
        loading: false,
        error: action.payload,
      };

    default:
      return state;
  }
};

export default overviewDashboardReducer;
