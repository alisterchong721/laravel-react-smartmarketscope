export const FETCH_NEWS_SENTIMENT_FILTERS_REQUEST =
  'FETCH_NEWS_SENTIMENT_FILTERS_REQUEST';
export const FETCH_NEWS_SENTIMENT_FILTERS_SUCCESS =
  'FETCH_NEWS_SENTIMENT_FILTERS_SUCCESS';
export const FETCH_NEWS_SENTIMENT_FILTERS_FAILURE =
  'FETCH_NEWS_SENTIMENT_FILTERS_FAILURE';

export const FETCH_NEWS_SENTIMENT_REQUEST = 'FETCH_NEWS_SENTIMENT_REQUEST';
export const FETCH_NEWS_SENTIMENT_SUCCESS = 'FETCH_NEWS_SENTIMENT_SUCCESS';
export const FETCH_NEWS_SENTIMENT_FAILURE = 'FETCH_NEWS_SENTIMENT_FAILURE';

export const SET_NEWS_SENTIMENT_QUERY = 'SET_NEWS_SENTIMENT_QUERY';

export const fetchNewsSentimentFiltersRequest = () => ({
  type: FETCH_NEWS_SENTIMENT_FILTERS_REQUEST,
});

export const fetchNewsSentimentFiltersSuccess = (data) => ({
  type: FETCH_NEWS_SENTIMENT_FILTERS_SUCCESS,
  payload: data,
});

export const fetchNewsSentimentFiltersFailure = (error) => ({
  type: FETCH_NEWS_SENTIMENT_FILTERS_FAILURE,
  payload: error,
});

export const fetchNewsSentimentRequest = (query = {}) => ({
  type: FETCH_NEWS_SENTIMENT_REQUEST,
  payload: query,
});

export const fetchNewsSentimentSuccess = (data) => ({
  type: FETCH_NEWS_SENTIMENT_SUCCESS,
  payload: data,
});

export const fetchNewsSentimentFailure = (error) => ({
  type: FETCH_NEWS_SENTIMENT_FAILURE,
  payload: error,
});

export const setNewsSentimentQuery = (query) => ({
  type: SET_NEWS_SENTIMENT_QUERY,
  payload: query,
});
