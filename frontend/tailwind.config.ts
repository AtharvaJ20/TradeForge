import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'text-primary': 'var(--color-text-primary)',
        'text-secondary': 'var(--color-text-secondary)',
        'text-muted': 'var(--color-text-muted)',
        'surface-base': 'var(--color-surface-base)',
        'surface-subtle': 'var(--color-surface-subtle)',
        'surface-warning': 'var(--color-surface-warning)',
        'surface-info': 'var(--color-surface-info)',
        'surface-success': 'var(--color-surface-success)',
        'surface-danger': 'var(--color-surface-danger)',
        'surface-neutral': 'var(--color-surface-neutral)',
        'surface-danger-subtle': 'var(--color-surface-danger-subtle)',
        warning: 'var(--color-warning)',
        'warning-emphasis': 'var(--color-warning-emphasis)',
        info: 'var(--color-info)',
        success: 'var(--color-success)',
        'success-emphasis': 'var(--color-success-emphasis)',
        danger: 'var(--color-danger)',
        'danger-emphasis': 'var(--color-danger-emphasis)',
        'success-subtle': 'var(--color-success-subtle)',
        'danger-subtle': 'var(--color-danger-subtle)',
        border: 'var(--color-border)',
        'border-focus': 'var(--color-border-focus)',
        primary: 'var(--color-primary)',
        'primary-emphasis': 'var(--color-primary-emphasis)',
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        spin: {
          from: { transform: 'rotate(0deg)' },
          to: { transform: 'rotate(360deg)' },
        },
      },
      animation: {
        shimmer: 'shimmer 1.2s ease-in-out infinite',
        'spin-slow': 'spin 2s linear infinite',
      },
    },
  },
  plugins: [],
}

export default config
