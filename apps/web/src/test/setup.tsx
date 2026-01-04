import '@testing-library/jest-dom'
import { vi } from 'vitest'
import React from 'react'

// Mock ResizeObserver
global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}))

// Mock recharts ResponsiveContainer
vi.mock('recharts', async () => {
  const OriginalModule = await vi.importActual('recharts');
  return {
    ...OriginalModule,
    ResponsiveContainer: ({ children }: any) => <div style={{ width: '500px', height: '500px' }}>{children}</div>
  };
});
