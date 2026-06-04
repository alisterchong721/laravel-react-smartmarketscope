import { call, put, takeLatest } from 'redux-saga/effects';
import axios from 'axios';
import { API_URL } from '../config/api';
import {
  FETCH_FUNDAMENTAL_COUNTRY_REQUEST,
  fetchFundamentalCountrySuccess,
  fetchFundamentalCountryFailure,
} from '../actions/fundamentalDataActions';


const countryApiMap = {
  us: 'US',
  uk: 'UK',
  eurozone: 'Eurozone',
  japan: 'Japan',
  australia: 'Australia',
  canada: 'Canada',
};

function* fetchFundamentalCountrySaga(action) {
  try {
    const { countryType = 'us' } = action.payload || {};
    const normalizedCountry = countryApiMap[(countryType || '').toLowerCase()]
      || countryType;
    
    const response = yield call(
      axios.get,
      `${API_URL}/fundamental/view-country-data`,
      {
        params: {
          country: normalizedCountry
        },
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        }
      }
    );

    // Access the data array from response.data.data
    const responseData = response.data.data || [];
    
    const transformedData = responseData.map((item, index) => ({
      key: index.toString(),
      economicData: item.event,
      actual: item.actual || 'N/A',
      forecast: item.forecast || 'N/A',
      previous: item.previous || 'N/A',
      date: item.formatted_date || 'Waiting',
      impact: item.impact || 'Neutral',
      actual_color: item.actual_color || item.actualColor || 'default',
      actualColor: item.actualColor || item.actual_color || 'default',
      impact_color: item.impact_color || item.impactColor || 'default',
      impactColor: item.impactColor || item.impact_color || 'default',
      importance: item.importance || 'N/A',
      source: item.source || 'Database',
      actualSource: item.actual_source || null,
      isLiveSource: Boolean(item.is_live_source),
      isPendingSource: Boolean(item.is_pending_source),
    }));

    yield put(fetchFundamentalCountrySuccess(transformedData));
    
  } catch (error) {
    console.error('Saga Error:', error);
    
    const errorMessage = error.response?.data?.message 
      || error.message 
      || 'Failed to fetch data';
    
    yield put(fetchFundamentalCountryFailure(errorMessage));
  }
}

export function* watchFundamentalData() {
  yield takeLatest(FETCH_FUNDAMENTAL_COUNTRY_REQUEST, fetchFundamentalCountrySaga);
}
