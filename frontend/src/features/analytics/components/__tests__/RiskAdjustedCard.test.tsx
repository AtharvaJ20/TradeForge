import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { RiskAdjustedCard } from '../RiskAdjustedCard'
import type { SharpeResult, SortinoResult } from '../../types'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const SHARPE_SUFFICIENT: SharpeResult = {
  sharpe_ratio: '2.34',
  mean_r: '0.45',
  std_r: '0.61',
  n_per_year: 252,
  r_coverage_count: 30,
  insufficient_sample: false,
}

const SORTINO_SUFFICIENT: SortinoResult = {
  sortino_ratio: '1.89',
  mean_r: '0.45',
  downside_dev: '0.75',
  n_per_year: 252,
  r_coverage_count: 30,
  insufficient_sample: false,
  no_downside_trades: false,
}

const SHARPE_INSUFFICIENT: SharpeResult = {
  sharpe_ratio: null,
  mean_r: null,
  std_r: null,
  n_per_year: 252,
  r_coverage_count: 5,
  insufficient_sample: true,
}

const SORTINO_INSUFFICIENT: SortinoResult = {
  sortino_ratio: null,
  mean_r: null,
  downside_dev: null,
  n_per_year: 252,
  r_coverage_count: 5,
  insufficient_sample: true,
  no_downside_trades: false,
}

const SORTINO_NO_DOWNSIDE: SortinoResult = {
  sortino_ratio: null,
  mean_r: '0.45',
  downside_dev: null,
  n_per_year: 252,
  r_coverage_count: 30,
  insufficient_sample: false,
  no_downside_trades: true,
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('RiskAdjustedCard', () => {
  it('renders the section heading', () => {
    render(<RiskAdjustedCard sharpe={SHARPE_SUFFICIENT} sortino={SORTINO_SUFFICIENT} />)
    expect(screen.getByRole('region', { name: /risk-adjusted returns/i })).toBeInTheDocument()
  })

  describe('TC-RA-001 — sufficient sample (30 trades)', () => {
    it('displays signed Sharpe ratio', () => {
      render(<RiskAdjustedCard sharpe={SHARPE_SUFFICIENT} sortino={SORTINO_SUFFICIENT} />)
      // +2.34 (positive → prefixed with +)
      expect(screen.getByText('+2.34')).toBeInTheDocument()
    })

    it('displays signed Sortino ratio', () => {
      render(<RiskAdjustedCard sharpe={SHARPE_SUFFICIENT} sortino={SORTINO_SUFFICIENT} />)
      expect(screen.getByText('+1.89')).toBeInTheDocument()
    })

    it('shows trade coverage count for each tile', () => {
      render(<RiskAdjustedCard sharpe={SHARPE_SUFFICIENT} sortino={SORTINO_SUFFICIENT} />)
      // Both tiles show "30 trades with R"
      const coverageLabels = screen.getAllByText('30 trades with R')
      expect(coverageLabels).toHaveLength(2)
    })

    it('shows n_per_year in footer', () => {
      render(<RiskAdjustedCard sharpe={SHARPE_SUFFICIENT} sortino={SORTINO_SUFFICIENT} />)
      expect(screen.getByText(/252 trading sessions/i)).toBeInTheDocument()
    })

    it('does not show insufficient-data notice', () => {
      render(<RiskAdjustedCard sharpe={SHARPE_SUFFICIENT} sortino={SORTINO_SUFFICIENT} />)
      expect(screen.queryByText(/insufficient data/i)).not.toBeInTheDocument()
    })
  })

  describe('TC-RA-002 — insufficient sample (5 trades)', () => {
    it('displays em-dash for both ratios', () => {
      render(<RiskAdjustedCard sharpe={SHARPE_INSUFFICIENT} sortino={SORTINO_INSUFFICIENT} />)
      const dashes = screen.getAllByText('—')
      expect(dashes.length).toBeGreaterThanOrEqual(2)
    })

    it('shows insufficient-data notice with coverage count for Sharpe', () => {
      render(<RiskAdjustedCard sharpe={SHARPE_INSUFFICIENT} sortino={SORTINO_INSUFFICIENT} />)
      expect(screen.getAllByText(/insufficient data \(n = 5\)/i).length).toBeGreaterThanOrEqual(1)
    })

    it('does not show "trades with R" count when sample is insufficient', () => {
      render(<RiskAdjustedCard sharpe={SHARPE_INSUFFICIENT} sortino={SORTINO_INSUFFICIENT} />)
      expect(screen.queryByText(/trades with R/i)).not.toBeInTheDocument()
    })
  })

  describe('no_downside_trades flag', () => {
    it('shows specific no-downside message for Sortino tile', () => {
      render(<RiskAdjustedCard sharpe={SHARPE_SUFFICIENT} sortino={SORTINO_NO_DOWNSIDE} />)
      expect(screen.getByText(/no negative-R trades in sample/i)).toBeInTheDocument()
    })

    it('still shows Sharpe ratio when Sortino has no_downside_trades', () => {
      render(<RiskAdjustedCard sharpe={SHARPE_SUFFICIENT} sortino={SORTINO_NO_DOWNSIDE} />)
      expect(screen.getByText('+2.34')).toBeInTheDocument()
    })

    it('does not show insufficient-data notice for no-downside case', () => {
      render(<RiskAdjustedCard sharpe={SHARPE_SUFFICIENT} sortino={SORTINO_NO_DOWNSIDE} />)
      expect(screen.queryByText(/insufficient data/i)).not.toBeInTheDocument()
    })
  })

  describe('negative ratios', () => {
    it('displays negative Sharpe without a + prefix', () => {
      const negSharpe: SharpeResult = { ...SHARPE_SUFFICIENT, sharpe_ratio: '-0.55' }
      render(<RiskAdjustedCard sharpe={negSharpe} sortino={SORTINO_SUFFICIENT} />)
      expect(screen.getByText('-0.55')).toBeInTheDocument()
    })
  })

  describe('accessibility', () => {
    it('each ratio value element has an aria-label', () => {
      render(<RiskAdjustedCard sharpe={SHARPE_SUFFICIENT} sortino={SORTINO_SUFFICIENT} />)
      // <dd> carries aria-label="Sharpe ratio: +2.34" / "Sortino ratio: +1.89"
      expect(screen.getByRole('definition', { name: /sharpe ratio/i })).toBeInTheDocument()
      expect(screen.getByRole('definition', { name: /sortino ratio/i })).toBeInTheDocument()
    })

    it('card is a labelled landmark region', () => {
      render(<RiskAdjustedCard sharpe={SHARPE_SUFFICIENT} sortino={SORTINO_SUFFICIENT} />)
      expect(screen.getByRole('region', { name: /risk-adjusted returns/i })).toBeInTheDocument()
    })
  })
})
