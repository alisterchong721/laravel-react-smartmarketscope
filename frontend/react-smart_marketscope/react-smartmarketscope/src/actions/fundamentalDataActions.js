export const FETCH_FUNDAMENTAL_COUNTRY_REQUEST =
  'FETCH_FUNDAMENTAL_COUNTRY_REQUEST';
export const FETCH_FUNDAMENTAL_COUNTRY_SUCCESS =
  'FETCH_FUNDAMENTAL_COUNTRY_SUCCESS';
export const FETCH_FUNDAMENTAL_COUNTRY_FAILURE =
  'FETCH_FUNDAMENTAL_COUNTRY_FAILURE';

// function to take countries fundamental data with country parameter
export const fetchFundamentalCountry = (countryType = 'US') => ({
  type: FETCH_FUNDAMENTAL_COUNTRY_REQUEST,
  payload: { countryType },
});
export const fetchFundamentalCountrySuccess = (data) => ({
  type: FETCH_FUNDAMENTAL_COUNTRY_SUCCESS,
  payload: data,
});
export const fetchFundamentalCountryFailure = (error) => ({
  type: FETCH_FUNDAMENTAL_COUNTRY_FAILURE,
  payload: error,
});
