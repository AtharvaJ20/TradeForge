import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DisciplineScoreInput } from '../DisciplineScoreInput'

describe('DisciplineScoreInput', () => {
  it('renders 10 radio buttons', () => {
    render(<DisciplineScoreInput value={null} onChange={() => {}} />)
    const radios = screen.getAllByRole('radio')
    expect(radios).toHaveLength(10)
  })

  it('marks selected score as checked', () => {
    render(<DisciplineScoreInput value={7} onChange={() => {}} />)
    expect(screen.getByRole('radio', { name: 'Score 7' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('radio', { name: 'Score 6' })).toHaveAttribute('aria-checked', 'false')
  })

  it('calls onChange with the clicked score', async () => {
    const onChange = vi.fn()
    render(<DisciplineScoreInput value={null} onChange={onChange} />)
    await userEvent.click(screen.getByRole('radio', { name: 'Score 5' }))
    expect(onChange).toHaveBeenCalledWith(5)
  })

  it('deselects when the selected score is clicked again', async () => {
    const onChange = vi.fn()
    render(<DisciplineScoreInput value={5} onChange={onChange} />)
    await userEvent.click(screen.getByRole('radio', { name: 'Score 5' }))
    expect(onChange).toHaveBeenCalledWith(null)
  })

  it('does not call onChange when disabled', async () => {
    const onChange = vi.fn()
    render(<DisciplineScoreInput value={null} onChange={onChange} disabled />)
    await userEvent.click(screen.getByRole('radio', { name: 'Score 3' }))
    expect(onChange).not.toHaveBeenCalled()
  })
})
