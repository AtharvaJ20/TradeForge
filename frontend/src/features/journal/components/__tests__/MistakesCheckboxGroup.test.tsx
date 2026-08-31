import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MistakesCheckboxGroup } from '../MistakesCheckboxGroup'

describe('MistakesCheckboxGroup', () => {
  it('renders all 13 mistakes without visibleCount', () => {
    render(<MistakesCheckboxGroup value={[]} onChange={() => {}} />)
    expect(screen.getAllByRole('checkbox')).toHaveLength(13)
  })

  it('respects visibleCount', () => {
    render(<MistakesCheckboxGroup value={[]} onChange={() => {}} visibleCount={6} />)
    expect(screen.getAllByRole('checkbox')).toHaveLength(6)
  })

  it('marks checked mistakes', () => {
    render(<MistakesCheckboxGroup value={['FOMO_ENTRY', 'REVENGE_TRADE']} onChange={() => {}} />)
    expect(screen.getByRole('checkbox', { name: 'FOMO entry' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('checkbox', { name: 'Revenge trade' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('checkbox', { name: 'Distracted' })).toHaveAttribute('aria-checked', 'false')
  })

  it('adds a mistake when unchecked chip is clicked', async () => {
    const onChange = vi.fn()
    render(<MistakesCheckboxGroup value={[]} onChange={onChange} />)
    await userEvent.click(screen.getByRole('checkbox', { name: 'Oversized position' }))
    expect(onChange).toHaveBeenCalledWith(['OVERSIZED_POSITION'])
  })

  it('removes a mistake when checked chip is clicked', async () => {
    const onChange = vi.fn()
    render(<MistakesCheckboxGroup value={['FOMO_ENTRY', 'OVERSIZED_POSITION']} onChange={onChange} />)
    await userEvent.click(screen.getByRole('checkbox', { name: 'FOMO entry' }))
    expect(onChange).toHaveBeenCalledWith(['OVERSIZED_POSITION'])
  })
})
