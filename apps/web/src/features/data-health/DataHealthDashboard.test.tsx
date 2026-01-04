import { render, screen, fireEvent } from '@testing-library/react'
import { DataHealthDashboard } from './DataHealthDashboard'
import { DataHealthScore } from './types'
import { describe, it, expect, vi } from 'vitest'

const mockData: DataHealthScore = {
  overall_score: 75,
  completeness_score: 80,
  consistency_score: 70,
  timeliness_score: 60,
  accuracy_score: 90,
  recommendations: [
    {
      type: 'completeness',
      priority: 'high',
      title: 'Test Recommendation',
      description: 'Fix this please',
      action: 'upload_csv'
    }
  ],
  calculated_at: '2023-01-01T00:00:00Z'
}

// Mock SubScoreCard and OverallScore to simplify testing (optional, but good for isolation)
// For now, let's test integration of the dashboard.

describe('DataHealthDashboard', () => {

  it('shows loading state when isLoading is true', () => {
    render(<DataHealthDashboard data={null} isLoading={true} onRefresh={vi.fn()} />)
    // Check for spinner or loading indicator structure
    // In our component code: <div className="animate-spin ...">
    // It doesn't have text, but we can search by class or just snapshot?
    // Let's assume we can find it by role or just generic container.
    const spinner = document.querySelector('.animate-spin')
    expect(spinner).toBeInTheDocument()
  })

  it('shows empty state when data is null', () => {
    render(<DataHealthDashboard data={null} isLoading={false} onRefresh={vi.fn()} />)
    expect(screen.getByText('No Health Score Available')).toBeInTheDocument()
  })

  it('renders dashboard with data', () => {
    render(<DataHealthDashboard data={mockData} isLoading={false} onRefresh={vi.fn()} />)

    // Header
    expect(screen.getByText('Data Health')).toBeInTheDocument()

    // Scores (formatted)
    // Overall score logic: 75%
    expect(screen.getByText('75%')).toBeInTheDocument()

    // Sub scores
    expect(screen.getByText('Completeness')).toBeInTheDocument()
    expect(screen.getByText('80%')).toBeInTheDocument()

    // Recommendations
    expect(screen.getByText('Test Recommendation')).toBeInTheDocument()
  })

  it('calls onRefresh when refresh button is clicked', () => {
    const onRefresh = vi.fn()
    render(<DataHealthDashboard data={mockData} isLoading={false} onRefresh={onRefresh} />)

    const refreshBtn = screen.getByTitle('Refresh')
    fireEvent.click(refreshBtn)

    expect(onRefresh).toHaveBeenCalledTimes(1)
  })
})
