import { FormEvent, useEffect, useMemo, useState } from 'react'

const API = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'
const money = (value: number) => new Intl.NumberFormat('fa-IR').format(value)

type StaffContext = { user: { display_name: string; email: string }; organization: { id: string; name: string }; role: string; branches: { id: string; name: string }[] }
type OrderLine = { id: string; item_name: string; quantity: number; note: string; options: { name: string }[]; add_ons: { name: string; quantity: number }[] }
type StaffOrder = { id: string; branch: string; branch_name: string; table_number: string; status: string; total: number; currency: string; payment: { status: string; method: string | null }; version: number; created_at: string; lines: OrderLine[] }

const labels: Record<string, string> = { pending: 'جدید', confirmed: 'تأییدشده', preparing: 'در حال آماده‌سازی', ready: 'آماده تحویل', completed: 'تکمیل‌شده', cancelled: 'لغوشده' }
const columnsByRole: Record<string, string[]> = {
  chef: ['confirmed', 'preparing', 'ready'], kitchen_staff: ['confirmed', 'preparing', 'ready'],
  cashier: ['pending', 'confirmed', 'ready', 'completed'], waiter: ['confirmed', 'ready', 'completed'],
}

export function StaffApp() {
  const [token, setToken] = useState(() => localStorage.getItem('baran_staff_access') ?? '')
  const [organizationId, setOrganizationId] = useState(() => localStorage.getItem('baran_staff_org') ?? '')
  const [context, setContext] = useState<StaffContext | null>(null)
  const [orders, setOrders] = useState<StaffOrder[]>([])
  const [branchId, setBranchId] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const [analytics, setAnalytics] = useState<{ revenue: number; orders: number; average_order: number; reservations: number; low_stock: { ingredient: string }[] } | null>(null)

  const headers = useMemo(() => ({ 'Content-Type': 'application/json', Authorization: `Bearer ${token}`, 'X-Organization-ID': organizationId }), [token, organizationId])

  async function load(activeToken = token, activeOrg = organizationId, activeBranch = branchId) {
    if (!activeToken || !activeOrg) return
    const requestHeaders = { Authorization: `Bearer ${activeToken}`, 'X-Organization-ID': activeOrg }
    const branchQuery = activeBranch ? `?branch=${activeBranch}` : ''
    const [contextResponse, ordersResponse, analyticsResponse] = await Promise.all([fetch(`${API}/staff/context/${branchQuery}`, { headers: requestHeaders }), fetch(`${API}/staff/orders/${branchQuery}`, { headers: requestHeaders }), fetch(`${API}/staff/analytics/${branchQuery}`, { headers: requestHeaders })])
    if (contextResponse.status === 401) { logout(); return }
    if (!contextResponse.ok || !ordersResponse.ok) { setError('دریافت سفارش‌ها ممکن نشد.'); return }
    setContext((await contextResponse.json()).data)
    setOrders((await ordersResponse.json()).data)
    if (analyticsResponse.ok) setAnalytics((await analyticsResponse.json()).data)
    setError('')
  }

  useEffect(() => {
    void load()
    const timer = setInterval(() => void load(), 8000)
    return () => clearInterval(timer)
  }, [token, organizationId, branchId])

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError('')
    const form = new FormData(event.currentTarget)
    const response = await fetch(`${API}/auth/token/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: form.get('email'), password: form.get('password') }) })
    if (!response.ok) { setError('ایمیل یا رمز عبور صحیح نیست.'); return }
    const access = (await response.json()).access
    const meResponse = await fetch(`${API}/auth/me/`, { headers: { Authorization: `Bearer ${access}` } })
    const me = await meResponse.json()
    const organization = me.organizations?.[0]
    if (!organization) { setError('برای این کاربر عضویت فعالی ثبت نشده است.'); return }
    localStorage.setItem('baran_staff_access', access); localStorage.setItem('baran_staff_org', organization.id)
    setToken(access); setOrganizationId(organization.id)
  }

  function logout() {
    localStorage.removeItem('baran_staff_access'); localStorage.removeItem('baran_staff_org')
    setToken(''); setOrganizationId(''); setContext(null); setOrders([])
  }

  async function transition(order: StaffOrder, status: string) {
    setBusy(order.id); setError('')
    const response = await fetch(`${API}/staff/orders/${order.id}/`, { method: 'PATCH', headers, body: JSON.stringify({ status, version: order.version }) })
    if (!response.ok) { setError(response.status === 400 ? 'سفارش تغییر کرده است؛ لیست تازه شد.' : 'این تغییر برای نقش شما مجاز نیست.'); await load(); setBusy(''); return }
    const updated = (await response.json()).data
    setOrders(current => current.map(item => item.id === updated.id ? updated : item)); setBusy('')
  }

  async function collect(order: StaffOrder, method: 'cash' | 'pos') {
    setBusy(`pay-${order.id}`); setError('')
    const response = await fetch(`${API}/staff/orders/${order.id}/collect-payment/`, { method: 'POST', headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, body: JSON.stringify({ method }) })
    if (!response.ok) { setError('ثبت پرداخت ممکن نشد یا برای این نقش مجاز نیست.'); setBusy(''); return }
    const updated = (await response.json()).data
    setOrders(current => current.map(item => item.id === updated.id ? updated : item)); setBusy('')
  }

  if (!token) return <div className="staff-login" dir="rtl"><form onSubmit={event => void login(event)}><div className="brand-mark">ب</div><p className="kicker">پنل عملیات باران</p><h1>خوش آمدید</h1><label>ایمیل<input name="email" type="email" required /></label><label>رمز عبور<input name="password" type="password" required /></label>{error && <div className="error">{error}</div>}<button type="submit">ورود به شیفت</button></form></div>
  if (!context) return <div className="state"><div className="loader"/><p>در حال دریافت سفارش‌ها…</p></div>

  const columns = columnsByRole[context.role] ?? ['pending', 'confirmed', 'preparing', 'ready', 'completed']
  const transitionsByRole: Record<string, Record<string, string>> = {
    chef: { confirmed: 'preparing', preparing: 'ready' }, kitchen_staff: { confirmed: 'preparing', preparing: 'ready' },
    cashier: { pending: 'confirmed', ready: 'completed' }, waiter: { ready: 'completed' },
    owner: { pending: 'confirmed', confirmed: 'preparing', preparing: 'ready', ready: 'completed' },
    admin: { pending: 'confirmed', confirmed: 'preparing', preparing: 'ready', ready: 'completed' },
    branch_manager: { pending: 'confirmed', confirmed: 'preparing', preparing: 'ready', ready: 'completed' },
  }
  const next = transitionsByRole[context.role] ?? {}
  return <div className="staff-shell" dir="rtl">
    <aside className="staff-side"><div className="staff-brand"><div className="brand-mark">ب</div><div><b>باران</b><small>مرکز عملیات</small></div></div><div className="shift"><span className="live-dot"/> شیفت آنلاین</div><div className="staff-user"><b>{context.user.display_name || context.user.email}</b><small>{labels[context.role] ?? context.role}</small></div><button className="logout" onClick={logout}>خروج از حساب</button></aside>
    <main className="staff-main"><header className="staff-head"><div><p className="kicker">{context.organization.name}</p><h1>سفارش‌های امروز</h1></div><select value={branchId} onChange={event => setBranchId(event.target.value)}><option value="">همه شعب مجاز</option>{context.branches.map(branch => <option key={branch.id} value={branch.id}>{branch.name}</option>)}</select></header>
      {error && <div className="error">{error}</div>}
      {analytics && <div className="insight-strip"><div><small>فروش امروز</small><b>{money(analytics.revenue)} ریال</b></div><div><small>میانگین سفارش</small><b>{money(analytics.average_order)} ریال</b></div><div><small>رزرو امروز</small><b>{analytics.reservations}</b></div><div className={analytics.low_stock.length ? 'warning' : ''}><small>هشدار موجودی</small><b>{analytics.low_stock.length}</b></div></div>}
      <div className="status-summary">{columns.map(status => <div key={status}><b>{orders.filter(order => order.status === status).length}</b><span>{labels[status]}</span></div>)}</div>
      <div className="order-board">{columns.map(status => <section className="order-column" key={status}><div className="column-title"><h2>{labels[status]}</h2><span>{orders.filter(order => order.status === status).length}</span></div>{orders.filter(order => order.status === status).map(order => <article className="order-card" key={order.id}><header><div><b>میز {order.table_number}</b><small>#{order.id.slice(0, 6)}</small></div><time>{new Date(order.created_at).toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit' })}</time></header><ul>{order.lines.map(line => <li key={line.id}><b>{line.quantity}×</b><div>{line.item_name}{line.options.length > 0 && <small>{line.options.map(value => value.name).join('، ')}</small>}{line.note && <em>{line.note}</em>}</div></li>)}</ul><div className={`payment-chip ${order.payment.status}`}>{order.payment.status === 'paid' ? `پرداخت‌شده · ${order.payment.method === 'cash' ? 'نقدی' : order.payment.method === 'pos' ? 'کارت‌خوان' : 'آنلاین'}` : 'پرداخت‌نشده'}</div>{order.payment.status !== 'paid' && ['owner', 'admin', 'branch_manager', 'cashier'].includes(context.role) && <div className="collect-actions"><button disabled={busy === `pay-${order.id}`} onClick={() => void collect(order, 'pos')}>ثبت کارت‌خوان</button><button disabled={busy === `pay-${order.id}`} onClick={() => void collect(order, 'cash')}>ثبت نقدی</button></div>}<footer><strong>{money(order.total)} ریال</strong>{next[status] && <button disabled={busy === order.id} onClick={() => void transition(order, next[status])}>{labels[next[status]]} ←</button>}</footer></article>)}</section>)}</div>
    </main>
  </div>
}
