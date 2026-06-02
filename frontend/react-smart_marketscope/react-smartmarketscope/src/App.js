import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useDispatch } from 'react-redux';
import { useEffect, useState } from 'react';
import Register from './components/register';
import Login from './components/login';
import ForgotPassword from './components/forgot-password';
import Home from './components/home';
import Overview from './components/overview';

// Sidebar and its Pages
import PrivateRoute from './components/private-route';
import Sidebar from './components/sidebar';
import FundamentalCountry from './components/fundamental-analysis/fundamental-country';
import FundamentalDataType from './components/fundamental-analysis/fundamental-data-type';
import RetailSentiment from './components/sentimental-analysis/retail-sentiment';
import CotReport from './components/sentimental-analysis/cot-report';
import NewsSentiment from './components/sentimental-analysis/news-sentiment';
import CurrencyPair from './components/fundamental-analysis/currency-pair';
import TradingJournal from './components/trading-journal/trading-journal';
import ChatbotWidget from './components/chatbot/chatbot-widget';
import IdleSessionTimeout from './components/idle-session-timeout';
import SeasonalityAnalysis from './components/seasonality-analysis/seasonality-analysis';
// import EURUSD from
// import Dashboard from './components/Dashboard';

function App() {
  const dispatch = useDispatch();
  const [appReady, setAppReady] = useState(false);

  // Load token on app startup
  useEffect(() => {
    const initializeApp = async () => {
      await dispatch({ type: 'APP_STARTUP' });
      setAppReady(true);
    };

    initializeApp();
  }, [dispatch]);

  // Show loading while app initializes
  if (!appReady) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <>
      <Routes>
        {/* Public Routes */}

        <Route path="/register" element={<Register />} />
        <Route path="/login" element={<Login />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/home" element={<Home />} />

        {/* Protected Routes  */}
        <Route
          path="/sidebar"
          element={
            <PrivateRoute>
              <Sidebar />
            </PrivateRoute>
          }
        />
        <Route
          path="/overview"
          element={
            <PrivateRoute>
              <Overview />
            </PrivateRoute>
          }
        />
        <Route
          path="/fundamental/country/:countryType?"
          element={
            <PrivateRoute>
              <FundamentalCountry />
            </PrivateRoute>
          }
        />
        <Route
          path="/fundamental/pair/:pair?"
          element={
            <PrivateRoute>
              <CurrencyPair />
            </PrivateRoute>
          }
        />
        <Route
          path="/sentimental/cot-positions"
          element={
            <PrivateRoute>
              <CotReport />
            </PrivateRoute>
          }
        />
        <Route
          path="/sentimental/cot-positions/pairs/:pair?"
          element={
            <PrivateRoute>
              <CotReport />
            </PrivateRoute>
          }
        />
        <Route
          path="/sentimental/retail-sentiment"
          element={
            <PrivateRoute>
              <RetailSentiment />
            </PrivateRoute>
          }
        />
        <Route
          path="/sentimental/retail-sentiment/pairs/:pair?"
          element={
            <PrivateRoute>
              <RetailSentiment />
            </PrivateRoute>
          }
        />
        <Route
          path="/sentimental/retail-sentiment/brokers/:broker?"
          element={
            <PrivateRoute>
              <RetailSentiment />
            </PrivateRoute>
          }
        />
        <Route
          path="/sentimental/news-sentiment"
          element={
            <PrivateRoute>
              <NewsSentiment />
            </PrivateRoute>
          }
        />
        <Route
          path="/fundamental/data-type"
          element={
            <PrivateRoute>
              <FundamentalDataType />
            </PrivateRoute>
          }
        />

        <Route
          path="/seasonality"
          element={
            <PrivateRoute>
              <SeasonalityAnalysis />
            </PrivateRoute>
          }
        />
        <Route
          path="/seasonality/:asset"
          element={
            <PrivateRoute>
              <SeasonalityAnalysis />
            </PrivateRoute>
          }
        />

        <Route
          path="/trading-journal"
          element={
            <PrivateRoute>
              <TradingJournal />
            </PrivateRoute>
          }
        />

        {/* Redirect any unknown route */}
        <Route path="*" element={<Navigate to="/home" />} />
      </Routes>
      <IdleSessionTimeout />
      <ChatbotWidget />
    </>
  );
}

export default App;
