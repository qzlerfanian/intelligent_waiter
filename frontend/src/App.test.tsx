import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'

describe('customer app', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    history.replaceState({}, '', '/')
    vi.restoreAllMocks()
  })

  it('asks a customer without a session to scan the table QR', async () => {
    render(<App />)
    expect(await screen.findByText('برای دیدن منو، QR روی میز را اسکن کنید.')).toBeTruthy()
  })

  it('shows staff login on the operations route', async () => {
    history.replaceState({}, '', '/staff')
    render(<App />)
    expect(await screen.findByText('ورود به شیفت')).toBeTruthy()
  })

  it('loads the separate management route', async () => {
    history.replaceState({}, '', '/manage')
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'ورود به مدیریت' })).toBeTruthy()
  })

  it('renders the complete premium storefront in demo mode', async () => {
    history.replaceState({}, '', '/?demo=1')
    render(<App />)
    expect(await screen.findByText('یک تجربهٔ خوش‌طعم،')).toBeTruthy()
    expect(await screen.findByPlaceholderText('جست‌وجوی غذا، نوشیدنی یا طعم…')).toBeTruthy()
    expect(await screen.findByText('چلوکباب مخصوص باران')).toBeTruthy()
  })
})
