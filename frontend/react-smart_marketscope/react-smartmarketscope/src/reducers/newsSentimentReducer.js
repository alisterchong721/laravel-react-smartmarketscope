import {
  FETCH_NEWS_SENTIMENT_FAILURE,
  FETCH_NEWS_SENTIMENT_FILTERS_FAILURE,
  FETCH_NEWS_SENTIMENT_FILTERS_REQUEST,
  FETCH_NEWS_SENTIMENT_FILTERS_SUCCESS,
  FETCH_NEWS_SENTIMENT_REQUEST,
  FETCH_NEWS_SENTIMENT_SUCCESS,
  SET_NEWS_SENTIMENT_QUERY,
} from '../actions/newsSentimentActions';

const initialState = {
  query: {
    assets: [],
    status: 'completed',
    limit: 20,
  },
  filtersMeta: null,
  filtersLoading: false,
  filtersError: null,
  newsData: null,
  loading: false,
  error: null,
  lastUpdated: null,
};

const newsSentimentReducer = (state = initialState, action) => {
  switch (action.type) {
    case FETCH_NEWS_SENTIMENT_FILTERS_REQUEST:
      return {
        ...state,
        filtersLoading: true,
        filtersError: null,
      };

    case FETCH_NEWS_SENTIMENT_FILTERS_SUCCESS:
      return {
        ...state,
        filtersLoading: false,
        filtersError: null,
        filtersMeta: action.payload,
        query: {
          ...state.query,
          status: state.query.status || action.payload?.default_status || 'completed',
          limit: state.query.limit || action.payload?.default_limit || 20,
        },
      };

    case FETCH_NEWS_SENTIMENT_FILTERS_FAILURE:
      return {
        ...state,
        filtersLoading: false,
        filtersError: action.payload,
      };

    case SET_NEWS_SENTIMENT_QUERY:
      return {
        ...state,
        query: {
          ...state.query,
          ...action.payload,
        },
      };

    case FETCH_NEWS_SENTIMENT_REQUEST:
      return {
        ...state,
        loading: true,
        error: null,
      };

    case FETCH_NEWS_SENTIMENT_SUCCESS:
      return {
        ...state,
        loading: false,
        newsData: action.payload,
        error: null,
        lastUpdated: new Date().toISOString(),
      };

    case FETCH_NEWS_SENTIMENT_FAILURE:
      return {
        ...state,
        loading: false,
        error: action.payload,
      };

    default:
      return state;
  }
};

export default newsSentimentReducer;
