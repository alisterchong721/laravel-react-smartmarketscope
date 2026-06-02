import {
  FETCH_FUNDAMENTAL_COUNTRY_REQUEST,
  FETCH_FUNDAMENTAL_COUNTRY_SUCCESS,
  FETCH_FUNDAMENTAL_COUNTRY_FAILURE,
} from '../actions/fundamentalDataActions';

const initialState = {
  loading: false,
  data: [],
  error: null,
  lastUpdated: null,
};

const fundamentalDataReducer = (state = initialState, action) => {
  switch (action.type) {
    case FETCH_FUNDAMENTAL_COUNTRY_REQUEST:
      return {
        ...state,
        loading: true,
        error: null,
      };

    case FETCH_FUNDAMENTAL_COUNTRY_SUCCESS:
      return {
        ...state,
        loading: false,
        data: action.payload,
        lastUpdated: new Date().toISOString(),
        error: null,
      };

    case FETCH_FUNDAMENTAL_COUNTRY_FAILURE:
      return {
        ...state,
        loading: false,
        error: action.payload,
        data: [],
      };

    default:
      return state;
  }
};

export default fundamentalDataReducer;