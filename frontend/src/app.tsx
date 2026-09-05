import { Navigate, Route, Routes } from 'react-router-dom'
import { LoginPage } from './features/auth/components/LoginPage'
import { RegisterPage } from './features/auth/components/RegisterPage'
import { RegisterSuccessPage } from './features/auth/components/RegisterSuccessPage'
import { VerifyEmailPage } from './features/auth/components/VerifyEmailPage'
import { ForgotPasswordPage } from './features/auth/components/ForgotPasswordPage'
import { ResetPasswordPage } from './features/auth/components/ResetPasswordPage'
import { AnalyticsPage } from './features/analytics/AnalyticsPage'
import { AppShell } from './layout/AppShell'
import { RequireAuth } from './components/RequireAuth'
import { PlaceholderPage } from './components/PlaceholderPage'

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
        <Route element={<AppShell />}>
          <Route path="/" element={<Navigate to="/analytics" replace />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/risk" element={<PlaceholderPage title="Risk" />} />
          <Route path="/trades" element={<PlaceholderPage title="Trades" />} />
          <Route path="/import" element={<PlaceholderPage title="Import" />} />
          <Route path="/settings" element={<PlaceholderPage title="Settings" />} />
        </Route>
      </Route>
    </Routes>
  )
}
