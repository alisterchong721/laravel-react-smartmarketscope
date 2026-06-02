// function take currency pair parameter and return that pair impact
export const FETCH_CURRENCY_PAIR_REQUEST = 'FETCH_CURRENCY_PAIR_REQUEST';
export const FETCH_CURRENCY_PAIR_SUCCESS = 'FETCH_CURRENCY_PAIR_SUCCESS';
export const FETCH_CURRENCY_PAIR_FAILURE = 'FETCH_CURRENCY_PAIR_FAILURE';

export const fetchCurrencyPair = (pair) => ({
  type: FETCH_CURRENCY_PAIR_REQUEST,
  payload: { pair },
});

export const fetchCurrencyPairSuccess = (data) => ({
  type: FETCH_CURRENCY_PAIR_SUCCESS,
  payload: data,
});

export const fetchCurrencyPairFailure = (error) => ({
  type: FETCH_CURRENCY_PAIR_FAILURE,
  payload: error,
});