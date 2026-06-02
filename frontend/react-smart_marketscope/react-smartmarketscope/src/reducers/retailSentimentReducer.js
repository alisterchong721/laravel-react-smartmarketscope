import {
  FETCH_RETAIL_SENTIMENT_FAILURE,
  FETCH_RETAIL_SENTIMENT_FILTERS_FAILURE,
  FETCH_RETAIL_SENTIMENT_FILTERS_REQUEST,
  FETCH_RETAIL_SENTIMENT_FILTERS_SUCCESS,
  FETCH_RETAIL_SENTIMENT_REQUEST,
  FETCH_RETAIL_SENTIMENT_SUCCESS,
  RESET_RETAIL_SENTIMENT_QUERY,
  SET_RETAIL_SENTIMENT_QUERY,
} from '../actions/retailSentimentActions';

const defaultQuery = {
  group_by: 'pairs',
  pair: 'EURUSD',
  broker: null,
  pairs: [],
  brokers: [],
};

const initialState = {
  query: defaultQuery,
  filtersMeta: null,
  filtersLoading: false,
  filtersError: null,
  sentimentData: null,
  loading: false,
  error: null,
  lastUpdated: null,
};

const retailSentimentReducer = (state = initialState, action) => {
  switch (action.type) {
    case FETCH_RETAIL_SENTIMENT_FILTERS_REQUEST:
      return {
        ...state,
        filtersLoading: true,
        filtersError: null,
      };

    case FETCH_RETAIL_SENTIMENT_FILTERS_SUCCESS: {
      const filtersMeta = action.payload;

      return {
        ...state,
        filtersLoading: false,
        filtersMeta,
        filtersError: null,
        query: {
          ...state.query,
          group_by:
            state.query.group_by || filtersMeta?.default_group_by || 'pairs',
          pair: state.query.pair || filtersMeta?.default_pair || 'EURUSD',
          broker:
            state.query.broker ||
            filtersMeta?.default_broker ||
            filtersMeta?.available_brokers?.[0]?.code ||
            null,
        },
      };
    }

    case FETCH_RETAIL_SENTIMENT_FILTERS_FAILURE:
      return {
        ...state,
        filtersLoading: false,
        filtersError: action.payload,
      };

    case SET_RETAIL_SENTIMENT_QUERY:
      return {
        ...state,
        query: {
          ...state.query,
          ...action.payload,
        },
      };

    case RESET_RETAIL_SENTIMENT_QUERY:
      return {
        ...state,
        query: {
          group_by: state.filtersMeta?.default_group_by || 'pairs',
          pair: state.filtersMeta?.default_pair || 'EURUSD',
          broker:
            state.filtersMeta?.default_broker ||
            state.filtersMeta?.available_brokers?.[0]?.code ||
            null,
          pairs: [],
          brokers: [],
        },
        error: null,
      };

    case FETCH_RETAIL_SENTIMENT_REQUEST:
      return {
        ...state,
        loading: true,
        error: null,
      };

    case FETCH_RETAIL_SENTIMENT_SUCCESS:
      return {
        ...state,
        loading: false,
        sentimentData: action.payload,
        error: null,
        lastUpdated: new Date().toISOString(),
        query: {
          ...state.query,
          group_by: action.payload?.group_by || state.query.group_by,
          pair: action.payload?.selected_pair || state.query.pair,
          broker:
            action.payload?.selected_broker?.code || state.query.broker,
        },
      };

    case FETCH_RETAIL_SENTIMENT_FAILURE:
      return {
        ...state,
        loading: false,
        error: action.payload,
      };

    default:
      return state;
  }
};

export default retailSentimentReducer;
