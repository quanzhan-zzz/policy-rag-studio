import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { MetricCard } from './MetricCard'

describe('MetricCard', () => {
  it('renders the lab metric with supporting context', () => {
    render(<MetricCard detail="Three chunk profiles" label="Indexed chunks" value={42} />)
    expect(screen.getByText('Indexed chunks')).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.getByText('Three chunk profiles')).toBeInTheDocument()
  })
})
