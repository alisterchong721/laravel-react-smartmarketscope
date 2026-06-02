import { FETCH_CURRENCY_PAIR_FAILURE, FETCH_CURRENCY_PAIR_REQUEST, FETCH_CURRENCY_PAIR_SUCCESS } from "../actions/fundamentalPairActions";

const initialState = {
  // Single pair
  currentPair: null,
  pairData: null,
  pairLoading: false,
  pairError: null,
};

const fundamentalPairReducer = (state = initialState, action) => {
  switch (action.type) {
    // Single pair cases
    case FETCH_CURRENCY_PAIR_REQUEST:
      return {
        ...state,
        pairLoading: true,
        pairError: null,
        currentPair: action.payload.pair
      };
      
    case FETCH_CURRENCY_PAIR_SUCCESS:
      return {
        ...state,
        pairLoading: false,
        pairData: action.payload,
        lastUpdated: new Date().toISOString(),
        pairError: null
      };
      
    case FETCH_CURRENCY_PAIR_FAILURE:
      return {
        ...state,
        pairLoading: false,
        pairError: action.payload,
        pairData: null
      };
      
    default:
      return state;
  }
};

export default fundamentalPairReducer;