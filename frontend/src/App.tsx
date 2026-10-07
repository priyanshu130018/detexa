import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { RealtimeProvider } from './context/RealtimeContext';
import { ThemeProvider } from './context/ThemeContext';
import { MainLayout } from './components/layout/MainLayout';
import { LandingPage } from './pages/LandingPage';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { OverviewPage } from './pages/OverviewPage';
import { TransactionsPage } from './pages/TransactionsPage';
import { TransactionDetailPage } from './pages/TransactionDetailPage';
import { AlertsPage } from './pages/AlertsPage';
import { InvestigationPage } from './pages/InvestigationPage';
import { GraphInvestigationPage } from './pages/GraphInvestigationPage';
import { ModelStatisticsPage } from './pages/ModelStatisticsPage';
import { PredictPage } from './pages/PredictPage';
import { BehaviorPage } from './pages/BehaviorPage';
import { LoadingSpinner } from './components/common/LoadingSpinner';

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingSpinner size="lg" text="Authenticating session..." />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

const PublicOnlyRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingSpinner size="lg" text="Checking session..." />;
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
};

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <AuthProvider>
        <RealtimeProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<MainLayout />}>
                {/* Public routes */}
                <Route
                  index
                  element={
                    <PublicOnlyRoute>
                      <LandingPage />
                    </PublicOnlyRoute>
                  }
                />
                <Route
                  path="login"
                  element={
                    <PublicOnlyRoute>
                      <LoginPage />
                    </PublicOnlyRoute>
                  }
                />
                <Route
                  path="register"
                  element={
                    <PublicOnlyRoute>
                      <RegisterPage />
                    </PublicOnlyRoute>
                  }
                />

                {/* Protected dashboard routes */}
                <Route
                  path="dashboard"
                  element={
                    <ProtectedRoute>
                      <OverviewPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="transactions"
                  element={
                    <ProtectedRoute>
                      <TransactionsPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="transactions/:id"
                  element={
                    <ProtectedRoute>
                      <TransactionDetailPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="alerts"
                  element={
                    <ProtectedRoute>
                      <AlertsPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="investigation"
                  element={
                    <ProtectedRoute>
                      <InvestigationPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="graph"
                  element={
                    <ProtectedRoute>
                      <GraphInvestigationPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="statistics"
                  element={
                    <ProtectedRoute>
                      <ModelStatisticsPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="models"
                  element={
                    <ProtectedRoute>
                      <ModelStatisticsPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="predict"
                  element={
                    <ProtectedRoute>
                      <PredictPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="behavior"
                  element={
                    <ProtectedRoute>
                      <BehaviorPage />
                    </ProtectedRoute>
                  }
                />

                {/* Catch-all */}
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </RealtimeProvider>
      </AuthProvider>
    </ThemeProvider>
  );
};

export default App;
