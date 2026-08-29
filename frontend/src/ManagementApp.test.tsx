import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ManagementApp, managementRequest } from './ManagementApp'
import { formPayload, initialValues, sections } from './managementSchema'

const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const org = { id: 'org-1', name: 'رستوران تست', slug: 'test', role: 'owner' }
const user = { email: 'owner@example.test', display_name: 'مالک تست', organizations: [org] }
let requests: { url: string; options?: RequestInit }[]
function mockApi(overrides: Record<string, unknown> = {}, account = user) {
  vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => {
    requests.push({ url, options })
    const path = url.split('/api/v1/')[1]
    if (path === 'auth/me/') return response(account)
    if (path === 'organizations/') return response([org])
    if (options?.method === 'POST' || options?.method === 'PATCH') return response({ id: 'new-record', ...JSON.parse(String(options.body)) }, options.method === 'POST' ? 201 : 200)
    return response(overrides[path] ?? [])
  }))
}

describe('management console', () => {
  beforeEach(() => { sessionStorage.clear(); requests = []; vi.restoreAllMocks() })
  afterEach(() => { cleanup(); vi.unstubAllGlobals() })

  it('opens login and registration without making API calls', () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
    render(<ManagementApp />)
    expect(screen.getByRole('heading', { name: 'ورود به مدیریت' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'اولین بار است؟ ساخت حساب مالک' }))
    expect(screen.getByRole('heading', { name: 'ساخت حساب مالک' })).toBeTruthy()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('creates a branch with the selected organization and refreshes the list', async () => {
    sessionStorage.setItem('baran_manage_access', 'test-access'); mockApi()
    render(<ManagementApp />)
    await screen.findByText('چک‌لیست راه‌اندازی')
    fireEvent.click(screen.getByRole('button', { name: /ساخت شعبه/ }))
    fireEvent.click(await screen.findByRole('button', { name: '＋ افزودن شعبه' }))
    const dialog = screen.getByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText(/^نام/), { target: { value: 'شعبه مرکزی' } })
    fireEvent.change(within(dialog).getByLabelText(/کد انگلیسی شعبه/), { target: { value: 'central' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'ذخیره اطلاعات' }))
    await waitFor(() => expect(requests.some(entry => entry.options?.method === 'POST')).toBe(true))
    const submitted = requests.find(entry => entry.options?.method === 'POST')!
    expect(submitted.url).toContain('organizations/branches/')
    expect(submitted.options?.headers).toMatchObject({ 'X-Organization-ID': 'org-1', Authorization: 'Bearer test-access' })
    expect(JSON.parse(String(submitted.options?.body))).toMatchObject({ name: 'شعبه مرکزی', code: 'central', is_active: true })
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it('shows empty-organization onboarding', async () => {
    sessionStorage.setItem('baran_manage_access', 'test-access')
    vi.stubGlobal('fetch', vi.fn(async () => response({ ...user, organizations: [] })))
    render(<ManagementApp />)
    expect(await screen.findByRole('button', { name: '＋ ساخت اولین سازمان' })).toBeTruthy()
  })

  it('does not fetch or expose employee administration to branch managers', async () => {
    sessionStorage.setItem('baran_manage_access', 'test-access')
    mockApi({}, { ...user, organizations: [{ ...org, role: 'branch_manager' }] })
    render(<ManagementApp />)
    await screen.findByText('چک‌لیست راه‌اندازی')
    expect(screen.queryByRole('button', { name: /کارکنان/ })).toBeNull()
    expect(requests.some(entry => entry.url.includes('organizations/members/'))).toBe(false)
  })

  it('requires confirmation before sending a delete request', async () => {
    sessionStorage.setItem('baran_manage_access', 'test-access')
    mockApi({ 'organizations/branches/': [{ id: 'b-1', name: 'مرکزی', code: 'central', is_active: true }] })
    render(<ManagementApp />)
    fireEvent.click(await screen.findByRole('button', { name: /ساخت شعبه/ }))
    fireEvent.click(await screen.findByRole('button', { name: /^حذف$/ }))
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(requests.some(entry => entry.options?.method === 'DELETE')).toBe(false)
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'انصراف' }))
    expect(requests.some(entry => entry.options?.method === 'DELETE')).toBe(false)
  })

  it('serializes nullable prices, tags and ingredient selections', () => {
    const section = sections.find(item => item.key === 'items')!
    const values = initialValues(section, { ingredient_links: [{ ingredient: 'rice' }], base_price: 200000, tags: ['گرم'] })
    expect(values.ingredient_ids).toEqual(['rice'])
    values.tags = 'گرم، ایرانی, غذای اصلی'
    const payload = formPayload(section, values, true)
    expect(payload.discount_price).toBeNull()
    expect(payload.base_price).toBe(200000)
    expect(payload.tags).toEqual(['گرم', 'ایرانی', 'غذای اصلی'])
  })

  it('does not send identity fields when editing membership', () => {
    const section = sections.find(item => item.key === 'members')!
    const payload = formPayload(section, initialValues(section, { email: 'shared@example.test', user: 'u-1', role: 'chef', branches: ['b-1'], is_active: true }), true)
    expect(payload).toEqual({ role: 'chef', branches: ['b-1'], is_active: true })
  })

  it('refreshes an expired access token including initial profile loading', async () => {
    sessionStorage.setItem('baran_manage_access', 'expired'); sessionStorage.setItem('baran_manage_refresh', 'refresh')
    const fetch = vi.fn().mockResolvedValueOnce(response({}, 401)).mockResolvedValueOnce(response({ access: 'new-access', refresh: 'new-refresh' })).mockResolvedValueOnce(response(user))
    vi.stubGlobal('fetch', fetch)
    expect(await managementRequest('auth/me/')).toEqual(user)
    expect(sessionStorage.getItem('baran_manage_access')).toBe('new-access')
    expect(fetch).toHaveBeenCalledTimes(3)
  })
})
