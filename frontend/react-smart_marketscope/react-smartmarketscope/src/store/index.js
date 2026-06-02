// Holds the complete state
import { createStore, applyMiddleware, combineReducers } from 'redux';
import createSagaMiddleware from 'redux-saga';

// reducers
import authReducer from '../reducers/authReducer';
import cotReportReducer from '../reducers/cotReportReducer';
import fundamentalDataReducer from '../reducers/fundamentalDataReducer';
import fundamentalPairReducer from '../reducers/fundamentalPairReducer';
import newsSentimentReducer from '../reducers/newsSentimentReducer';
import overviewDashboardReducer from '../reducers/overviewDashboardReducer';
import retailSentimentReducer from '../reducers/retailSentimentReducer';
import tradingJournalReducer from '../reducers/tradingJournalReducer';
// sagas
import authSaga from '../sagas/authSagas';
import { watchCotReport } from '../sagas/cotReportSagas';
import { watchFundamentalData } from '../sagas/fundamentalDataSagas';
import { watchCurrencyPair } from '../sagas/fundamentalPairSagas';
import { watchNewsSentiment } from '../sagas/newsSentimentSagas';
import { watchOverviewDashboard } from '../sagas/overviewDashboardSagas';
import { watchRetailSentiment } from '../sagas/retailSentimentSagas';
import { watchTradingJournal } from '../sagas/tradingJournalSagas';

const rootReducer = combineReducers({
  auth: authReducer,
  cotReport: cotReportReducer,
  fundamental: fundamentalDataReducer,
  fundamentalPair: fundamentalPairReducer,
  newsSentiment: newsSentimentReducer,
  overviewDashboard: overviewDashboardReducer,
  retailSentiment: retailSentimentReducer,
  tradingJournal: tradingJournalReducer,
});

const sagaMiddleware = createSagaMiddleware();

export const store = createStore(rootReducer, applyMiddleware(sagaMiddleware));

sagaMiddleware.run(authSaga);
sagaMiddleware.run(watchCotReport);
sagaMiddleware.run(watchFundamentalData);
sagaMiddleware.run(watchCurrencyPair);
sagaMiddleware.run(watchNewsSentiment);
sagaMiddleware.run(watchOverviewDashboard);
sagaMiddleware.run(watchRetailSentiment);
sagaMiddleware.run(watchTradingJournal);
