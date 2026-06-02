import React, { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { Navigate } from 'react-router-dom';

const PrivateRoute = ({ children }) => {
  const { isAuthenticated } = useSelector((state) => state.auth);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [hasLocalToken, setHasLocalToken] = useState(false);

  useEffect(() => {
    // Check localStorage immediately
    const token = localStorage.getItem('token');
    setHasLocalToken(!!token);

    // Give Redux saga time to update state
    const timer = setTimeout(() => {
      setCheckingAuth(false);
    }, 200);

    return () => clearTimeout(timer);
  }, []);

  // Still checking
  if (checkingAuth) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  // If we have token in localStorage OR Redux says authenticated
  if (hasLocalToken || isAuthenticated) {
    return children;
  }

  // No token anywhere, redirect to login
  return <Navigate to="/login" replace />;
};

export default PrivateRoute;
