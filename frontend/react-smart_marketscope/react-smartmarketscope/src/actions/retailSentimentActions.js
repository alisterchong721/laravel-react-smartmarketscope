export const FETCH_RETAIL_SENTIMENT_FILTERS_REQUEST =
  'FETCH_RETAIL_SENTIMENT_FILTERS_REQUEST';
export const FETCH_RETAIL_SENTIMENT_FILTERS_SUCCESS =
  'FETCH_RETAIL_SENTIMENT_FILTERS_SUCCESS';
export const FETCH_RETAIL_SENTIMENT_FILTERS_FAILURE =
  'FETCH_RETAIL_SENTIMENT_FILTERS_FAILURE';

export const FETCH_RETAIL_SENTIMENT_REQUEST = 'FETCH_RETAIL_SENTIMENT_REQUEST';
export const FETCH_RETAIL_SENTIMENT_SUCCESS = 'FETCH_RETAIL_SENTIMENT_SUCCESS';
export const FETCH_RETAIL_SENTIMENT_FAILURE = 'FETCH_RETAIL_SENTIMENT_FAILURE';

export const SET_RETAIL_SENTIMENT_QUERY = 'SET_RETAIL_SENTIMENT_QUERY';
export const RESET_RETAIL_SENTIMENT_QUERY = 'RESET_RETAIL_SENTIMENT_QUERY';

export const fetchRetailSentimentFiltersRequest = () => ({
  type: FETCH_RETAIL_SENTIMENT_FILTERS_REQUEST,
});

export const fetchRetailSentimentFiltersSuccess = (data) => ({
  type: FETCH_RETAIL_SENTIMENT_FILTERS_SUCCESS,
  payload: data,
});

export const fetchRetailSentimentFiltersFailure = (error) => ({
  type: FETCH_RETAIL_SENTIMENT_FILTERS_FAILURE,
  payload: error,
});

export const fetchRetailSentimentRequest = (query = {}) => ({
  type: FETCH_RETAIL_SENTIMENT_REQUEST,
  payload: query,
});

export const fetchRetailSentimentSuccess = (data) => ({
  type: FETCH_RETAIL_SENTIMENT_SUCCESS,
  payload: data,
});

export const fetchRetailSentimentFailure = (error) => ({
  type: FETCH_RETAIL_SENTIMENT_FAILURE,
  payload: error,
});

export const setRetailSentimentQuery = (query) => ({
  type: SET_RETAIL_SENTIMENT_QUERY,
  payload: query,
});

export const resetRetailSentimentQuery = () => ({
  type: RESET_RETAIL_SENTIMENT_QUERY,
});
