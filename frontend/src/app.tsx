import { Navigate, Route, Routes } from 'react-router-dom'
import { LoginPage } from './features/auth/components/LoginPage'
import { RegisterPage } from './features/auth/components/RegisterPage'
import { RegisterSuccessPage } from './features/auth/components/RegisterSuccessPage'
import { VerifyEmailPage } from './features/auth/components/VerifyEmailPage'
import { ForgotPasswordPage } from './features/auth/components/ForgotPasswordPage'
import { ResetPasswordPage } from './features/auth/components/ResetPasswordPage'
import { AnalyticsPage } from './features/analytics/AnalyticsPage'
import { SettingsPage } from './features/settings/SettingsPage'
import { AddTradePage } from './features/trades/AddTradePage'
import { TradeListPage } from './features/trades/TradeListPage'
import { TradeDetailPage } from './features/trades/TradeDetailPage'
import { AccountProvider } from './features/accounts/context/AccountContext'
import { AppShell } from './layout/AppShell'
import { RequireAuth } from './components/RequireAuth'
import { PlaceholderPage } from './components/PlaceholderPage'
import { ImportTradesPage } from './features/imports/ImportTradesPage'
import { DashboardPage } from './features/dashboard/DashboardPage'

export function App() {
  return (
    <Routes>
      {/* Public auth routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/register-success" element={<RegisterSuccessPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />

      {/* Protected routes — gated by auth, wrapped in AppShell */}
      <Route element={<RequireAuth />}>
        <Route
          element={
            <AccountProvider>
              <AppShell />
            </AccountProvider>
          }
        >
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/risk" element={<PlaceholderPage title="Risk" />} />
          <Route path="/trades" element={<TradeListPage />} />
          <Route path="/trades/:tradeId" element={<TradeDetailPage />} />
          <Route path="/trades/new" element={<AddTradePage />} />
          <Route path="/import" element={<ImportTradesPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
