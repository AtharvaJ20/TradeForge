import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary] Uncaught render error:', error, info.componentStack)
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback
      return (
        <div
          role="alert"
          className="flex min-h-screen flex-col items-center justify-center gap-4 p-8 text-center"
        >
          <p className="text-lg font-semibold text-danger-emphasis">Something went wrong.</p>
          <p className="text-sm text-text-secondary">
            Please refresh the page. If the problem persists, contact support.
          </p>
          <button
            type="button"
            className="rounded-md bg-surface-subtle px-4 py-2 text-sm text-text-primary hover:bg-surface-raised"
            onClick={() => window.location.reload()}
          >
            Refresh
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
