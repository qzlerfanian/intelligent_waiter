import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { StaffApp } from './StaffApp'
const ManagementApp = lazy(() => import('./ManagementApp').then(module => ({ default: module.ManagementApp })))

type MenuItem = { id: string; name: string; description: string; image_url: string; effective_price: number; calories: number | null; preparation_minutes: number; is_chef_recommended: boolean; tags: string[] }
type Category = { id: string; name: string; items: MenuItem[] }
type Menu = { id: string; name: string; currency: string; categories: Category[] }
type CartLine = { id: string; item_name: string; quantity: number; line_total: number }
type Cart = { lines: CartLine[]; subtotal: number; currency: string }
type CustomerOrder = { id: string; status: string; total: number; currency: string; created_at: string; lines: { item_name: string; quantity: number }[] }

const API = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'
const money = (value: number) => new Intl.NumberFormat('fa-IR').format(value)
const demoMenus: Menu[] = [{ id: 'demo', name: 'منوی اصلی', currency: 'IRR', categories: [{ id: 'popular', name: 'محبوب‌ها', items: [
  { id: 'kebab', name: 'چلوکباب مخصوص باران', description: 'کباب زغالی، برنج ایرانی زعفرانی و سبزی تازه', image_url: '/images/baran-hero.png', effective_price: 890000, calories: 760, preparation_minutes: 24, is_chef_recommended: true, tags: ['پرفروش'] },
  { id: 'chicken', name: 'مرغ گریل و سبزیجات', description: 'سینه مرغ آبدار با سبزیجات فصل و سس مخصوص', image_url: '', effective_price: 690000, calories: 430, preparation_minutes: 18, is_chef_recommended: false, tags: ['سبک'] },
  { id: 'salad', name: 'سالاد سبز باران', description: 'سبزی‌های تازه، آووکادو، گردو و سس انار', image_url: '', effective_price: 430000, calories: 280, preparation_minutes: 10, is_chef_recommended: false, tags: ['وگان'] },
  { id: 'dessert', name: 'چیزکیک زعفرانی', description: 'بافت لطیف پنیر، زعفران و کرامبل پسته', image_url: '', effective_price: 360000, calories: 390, preparation_minutes: 8, is_chef_recommended: true, tags: ['جدید'] }
] }, { id: 'drinks', name: 'نوشیدنی', items: [] }] }]

export function App() {
  return location.pathname.startsWith('/manage') ? <Suspense fallback={<div className="state">در حال بارگذاری مدیریت…</div>}><ManagementApp /></Suspense> : location.pathname.startsWith('/staff') ? <StaffApp /> : <CustomerApp />
}

function CustomerApp() {
  const qrToken = new URLSearchParams(location.search).get('qr') ?? ''
  const demo = new URLSearchParams(location.search).get('demo') === '1'
  const [sessionToken, setSessionToken] = useState(() => demo ? 'demo-session' : localStorage.getItem('baran_session') ?? '')
  const [branch, setBranch] = useState('کافه باران')
  const [table, setTable] = useState('—')
  const [menus, setMenus] = useState<Menu[]>([])
  const [cart, setCart] = useState<Cart>({ lines: [], subtotal: 0, currency: 'IRR' })
  const [activeCategory, setActiveCategory] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [orderId, setOrderId] = useState('')
  const [customerToken, setCustomerToken] = useState(() => localStorage.getItem('baran_customer_access') ?? '')
  const [accountOpen, setAccountOpen] = useState(false)
  const [favoriteIds, setFavoriteIds] = useState<string[]>([])
  const [query, setQuery] = useState('')
  const [checkoutOpen, setCheckoutOpen] = useState(false)
  const [promotionCode, setPromotionCode] = useState('')
  const [fulfillment, setFulfillment] = useState('dine_in')
  const [deliveryAddress, setDeliveryAddress] = useState('')
  const [checkoutBusy, setCheckoutBusy] = useState(false)

  const headers = useMemo(() => ({ 'Content-Type': 'application/json', 'X-Table-Session': sessionToken }), [sessionToken])
  const accountHeaders = useMemo(() => ({ ...headers, Authorization: `Bearer ${customerToken}` }), [headers, customerToken])

  useEffect(() => {
    async function boot() {
      try {
        if (demo) { setBranch('رستوران باران · شعبه نیاوران'); setTable('۱۲'); setMenus(demoMenus); setActiveCategory('popular'); setLoading(false); return }
        let token = sessionToken
        if (!token && qrToken) {
          const response = await fetch(`${API}/customer/sessions/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ qr_token: qrToken }) })
          if (!response.ok) throw new Error('کد QR معتبر نیست یا میز در دسترس نیست.')
          const payload = await response.json()
          token = payload.data.token
          localStorage.setItem('baran_session', token)
          setSessionToken(token)
          setBranch(payload.data.session.branch.name)
          setTable(payload.data.session.table.number)
        }
        if (!token) { setLoading(false); return }
        const auth = { 'X-Table-Session': token }
        const [sessionResponse, menuResponse, cartResponse] = await Promise.all([
          fetch(`${API}/customer/session/`, { headers: auth }),
          fetch(`${API}/customer/menu/`, { headers: auth }),
          fetch(`${API}/customer/cart/`, { headers: auth }),
        ])
        if (![sessionResponse, menuResponse, cartResponse].every(response => response.ok)) throw new Error('نشست میز منقضی شده است؛ QR را دوباره اسکن کنید.')
        const session = (await sessionResponse.json()).data
        const menuData = (await menuResponse.json()).data
        setBranch(session.branch.name); setTable(session.table.number); setMenus(menuData)
        setActiveCategory(menuData[0]?.categories[0]?.id ?? '')
        setCart((await cartResponse.json()).data)
      } catch (reason) { setError(reason instanceof Error ? reason.message : 'خطایی رخ داد.') }
      finally { setLoading(false) }
    }
    void boot()
  }, [])

  useEffect(() => {
    if (!customerToken || !sessionToken) { setFavoriteIds([]); return }
    async function connectAccount() {
      const claim = await fetch(`${API}/customer/session/claim/`, { method: 'POST', headers: accountHeaders })
      if (claim.status === 401) { localStorage.removeItem('baran_customer_access'); setCustomerToken(''); return }
      const response = await fetch(`${API}/customer/account/favorites/`, { headers: accountHeaders })
      if (response.ok) setFavoriteIds((await response.json()).data.map((favorite: { item_id: string }) => favorite.item_id))
    }
    void connectAccount()
  }, [customerToken, sessionToken])

  async function addItem(item: MenuItem) {
    setError('')
    if (demo) { setCart(current => ({ currency: 'IRR', subtotal: current.subtotal + item.effective_price, lines: [...current.lines, { id: crypto.randomUUID(), item_name: item.name, quantity: 1, line_total: item.effective_price }] })); return }
    const response = await fetch(`${API}/customer/cart/items/`, { method: 'POST', headers, body: JSON.stringify({ menu_item_id: item.id, quantity: 1 }) })
    if (!response.ok) { setError('این آیتم نیاز به انتخاب گزینه دارد یا اکنون موجود نیست.'); return }
    await refreshCart()
  }

  async function refreshCart() {
    const response = await fetch(`${API}/customer/cart/`, { headers })
    if (response.ok) setCart((await response.json()).data)
  }

  async function confirmOrder() {
    setCheckoutBusy(true); setError('')
    const response = await fetch(`${API}/customer/orders/confirm/`, { method: 'POST', headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, body: JSON.stringify({ promotion_code: promotionCode, fulfillment_type: fulfillment, delivery_address: deliveryAddress }) })
    const payload = await response.json()
    if (!response.ok) { setError(payload.error?.message ?? 'ثبت سفارش انجام نشد.'); setCheckoutBusy(false); return }
    setOrderId(payload.data.id); setCart({ lines: [], subtotal: 0, currency: payload.data.currency })
  }

  async function toggleFavorite(item: MenuItem) {
    if (!customerToken) { setAccountOpen(true); return }
    const selected = favoriteIds.includes(item.id)
    const response = await fetch(`${API}/customer/account/favorites/${selected ? `${item.id}/` : ''}`, { method: selected ? 'DELETE' : 'POST', headers: accountHeaders, body: selected ? undefined : JSON.stringify({ menu_item_id: item.id }) })
    if (response.ok) setFavoriteIds(current => selected ? current.filter(id => id !== item.id) : [...current, item.id])
  }

  if (loading) return <div className="state"><div className="loader"/><p>در حال آماده‌کردن میز شما…</p></div>
  if (!sessionToken) return <div className="state"><div className="brand-mark">ب</div><h1>باران</h1><p>برای دیدن منو، QR روی میز را اسکن کنید.</p></div>
  if (orderId) return <OrderProgress orderId={orderId} headers={headers} />

  const categories = menus.flatMap(menu => menu.categories)
  const categoryItems = categories.find(category => category.id === activeCategory)?.items ?? categories.flatMap(category => category.items)
  const visibleItems = categoryItems.filter(item => `${item.name} ${item.description} ${item.tags.join(' ')}`.toLocaleLowerCase('fa').includes(query.trim().toLocaleLowerCase('fa')))
  return <div className="app-shell" dir="rtl">
    <header className="topbar"><a className="wordmark"><i>ب</i><span>باران<small>تجربه‌ای برای چشیدن</small></span></a><div className="header-actions"><button className="account-button" onClick={() => setAccountOpen(true)}><span>♙</span>{customerToken ? 'حساب من' : 'ورود'}</button><div className="table-pill"><small>{branch}</small><b>میز {table}</b></div></div></header>
    <section className="hero"><div className="hero-copy"><span className="hero-badge">✦ انتخاب ویژه امروز</span><h1>یک تجربهٔ خوش‌طعم،<br/><em>در چند لمس.</em></h1><p>از منوی تازه انتخاب کن یا از دستیار هوشمند باران بخواه مطابق سلیقه‌ات پیشنهاد بدهد.</p><button onClick={() => document.querySelector('.menu-section')?.scrollIntoView({ behavior: 'smooth' })}>دیدن منو <span>↓</span></button></div><div className="hero-glow"/></section>
    <section className="menu-section"><div className="section-heading"><div><span>منوی امروز</span><h2>چه چیزی هوس کردی؟</h2></div><label className="search"><span>⌕</span><input value={query} onChange={event => setQuery(event.target.value)} placeholder="جست‌وجوی غذا، نوشیدنی یا طعم…"/><kbd>⌘ K</kbd></label></div>
    <nav className="category-nav">{categories.map(category => <button className={category.id === activeCategory ? 'active' : ''} onClick={() => setActiveCategory(category.id)} key={category.id}>{category.name}</button>)}</nav>
    {error && <div className="error">{error}</div>}
    <section className="menu-grid">{visibleItems.map((item, index) => <article className="food-card" key={item.id}>
      <div className={`food-art tone-${index % 4}`} style={item.image_url ? { backgroundImage: `url(${item.image_url})` } : undefined}><span>{item.is_chef_recommended ? 'پیشنهاد سرآشپز' : item.tags[0] ?? 'تازه'}</span><button aria-label="علاقه‌مندی" className={favoriteIds.includes(item.id) ? 'favorite active' : 'favorite'} onClick={() => void toggleFavorite(item)}>♥</button></div>
      <div className="card-copy"><h2>{item.name}</h2><p>{item.description || 'با مواد تازه و دستور ویژه‌ی آشپزخانه'}</p><div className="facts">{item.calories && <span>{item.calories} کالری</span>}<span>{item.preparation_minutes} دقیقه</span></div><footer><b>{money(item.effective_price)} <small>ریال</small></b><button onClick={() => void addItem(item)}>+</button></footer></div>
    </article>)}</section>{visibleItems.length === 0 && <div className="empty-menu">چیزی با این جست‌وجو پیدا نشد.</div>}</section>
    {cart.lines.length > 0 && <aside className="cart-bar"><div className="cart-count">{cart.lines.reduce((sum, line) => sum + line.quantity, 0)}</div><div><small>سبد سفارش شما</small><strong>{money(cart.subtotal)} <i>ریال</i></strong></div><button onClick={() => setCheckoutOpen(true)}>ادامه سفارش <span>←</span></button></aside>}
    {checkoutOpen && <div className="checkout-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) setCheckoutOpen(false) }}><section className="checkout-sheet"><header><div><span>مرور نهایی</span><h2>سفارش شما</h2></div><button onClick={() => setCheckoutOpen(false)}>×</button></header><div className="checkout-lines">{cart.lines.map(line => <div key={line.id}><span>{line.quantity}× {line.item_name}</span><b>{money(line.line_total)} ریال</b></div>)}</div><label>نحوه دریافت<select value={fulfillment} onChange={event => setFulfillment(event.target.value)}><option value="dine_in">سرو در همین میز</option><option value="takeaway">بیرون‌بر</option><option value="delivery">ارسال به آدرس</option></select></label>{fulfillment === 'delivery' && <label>آدرس تحویل<textarea value={deliveryAddress} onChange={event => setDeliveryAddress(event.target.value)} required /></label>}<label>کد تخفیف<div className="promo-input"><input value={promotionCode} onChange={event => setPromotionCode(event.target.value)} placeholder="مثلاً BARAN10"/><span>اعمال در ثبت نهایی</span></div></label>{error && <div className="error">{error}</div>}<footer><div><small>مبلغ سفارش</small><b>{money(cart.subtotal)} ریال</b></div><button disabled={checkoutBusy || (fulfillment === 'delivery' && !deliveryAddress.trim())} onClick={() => void confirmOrder()}>{checkoutBusy ? 'در حال ثبت…' : 'تأیید و ثبت سفارش'}</button></footer></section></div>}
    <ChatPanel headers={headers} onCartChanged={() => void refreshCart()} onOrderConfirmed={setOrderId} />
    {accountOpen && <AccountPanel sessionHeaders={headers} token={customerToken} setToken={setCustomerToken} onClose={() => setAccountOpen(false)} onCartChanged={() => void refreshCart()} />}
  </div>
}

function AccountPanel({ sessionHeaders, token, setToken, onClose, onCartChanged }: { sessionHeaders: Record<string, string>; token: string; setToken: (token: string) => void; onClose: () => void; onCartChanged: () => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [profile, setProfile] = useState<{ diet: string; allergen_codes: string[]; disliked_ingredients: string[]; spice_preference: number | null; ai_personalization_consent: boolean; retention_consent: boolean; marketing_consent: boolean } | null>(null)
  const [orders, setOrders] = useState<CustomerOrder[]>([])
  const [loyalty, setLoyalty] = useState<{ points_balance: number; tier: string } | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const authHeaders = useMemo(() => ({ ...sessionHeaders, Authorization: `Bearer ${token}` }), [sessionHeaders, token])
  async function load() {
    if (!token) return
    const responses = await Promise.all([fetch(`${API}/customer/account/profile/`, { headers: authHeaders }), fetch(`${API}/customer/account/orders/`, { headers: authHeaders }), fetch(`${API}/customer/account/loyalty/`, { headers: authHeaders })])
    if (responses.some(response => response.status === 401 || response.status === 403)) { localStorage.removeItem('baran_customer_access'); setToken(''); return }
    if (responses.every(response => response.ok)) { setProfile((await responses[0].json()).data); setOrders((await responses[1].json()).data); setLoyalty((await responses[2].json()).data) }
  }
  useEffect(() => { void load() }, [token])
  async function authenticate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('')
    const form = new FormData(event.currentTarget); const email = form.get('email'); const password = form.get('password')
    if (mode === 'register') {
      const registered = await fetch(`${API}/auth/register/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password, display_name: form.get('display_name') }) })
      if (!registered.ok) { setError('ثبت‌نام انجام نشد؛ ایمیل یا رمز را بررسی کن.'); setBusy(false); return }
    }
    const response = await fetch(`${API}/auth/token/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) })
    if (!response.ok) { setError('ایمیل یا رمز عبور صحیح نیست.'); setBusy(false); return }
    const access = (await response.json()).access
    const claim = await fetch(`${API}/customer/session/claim/`, { method: 'POST', headers: { ...sessionHeaders, Authorization: `Bearer ${access}` } })
    if (!claim.ok) { setError('اتصال حساب به این میز ممکن نشد.'); setBusy(false); return }
    localStorage.setItem('baran_customer_access', access); setToken(access); setBusy(false)
  }
  async function saveProfile() {
    if (!profile) return; setBusy(true)
    const response = await fetch(`${API}/customer/account/profile/`, { method: 'PATCH', headers: authHeaders, body: JSON.stringify(profile) })
    if (response.ok) setProfile((await response.json()).data); else setError('ذخیره ترجیحات ممکن نشد.')
    setBusy(false)
  }
  async function reorderOrder(orderId: string) {
    setBusy(true); const response = await fetch(`${API}/customer/account/orders/${orderId}/reorder/`, { method: 'POST', headers: { ...authHeaders, 'Idempotency-Key': crypto.randomUUID() } })
    if (response.ok) { onCartChanged(); onClose() } else setError('بعضی آیتم‌ها یا انتخاب‌های این سفارش دیگر موجود نیستند.')
    setBusy(false)
  }
  async function erase() {
    if (!window.confirm('ترجیحات، علاقه‌مندی‌ها و رضایت‌های ذخیره‌شده پاک شوند؟')) return
    const response = await fetch(`${API}/customer/account/privacy/erase/`, { method: 'POST', headers: authHeaders, body: JSON.stringify({ confirmation: 'DELETE MY PERSONALIZATION' }) })
    if (response.ok) await load()
  }
  function logout() { localStorage.removeItem('baran_customer_access'); setToken(''); onClose() }
  return <div className="account-backdrop" dir="rtl" onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}><aside className="account-panel"><header><div><p className="kicker">باشگاه مشتریان باران</p><h2>{token ? 'حساب من' : 'ورود به حساب'}</h2></div><button onClick={onClose}>×</button></header>{!token ? <form className="account-auth" onSubmit={event => void authenticate(event)}>{mode === 'register' && <label>نام<input name="display_name" required /></label>}<label>ایمیل<input name="email" type="email" required /></label><label>رمز عبور<input name="password" type="password" minLength={10} required /></label>{error && <div className="error">{error}</div>}<button disabled={busy}>{mode === 'login' ? 'ورود و اتصال به میز' : 'ساخت حساب'}</button><button type="button" className="link-button" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>{mode === 'login' ? 'حساب ندارم' : 'قبلاً ثبت‌نام کرده‌ام'}</button></form> : <div className="account-content">{loyalty && <section className="loyalty-card"><span>امتیاز قابل استفاده</span><b>{money(loyalty.points_balance)}</b><small>سطح {loyalty.tier === 'gold' ? 'طلایی' : loyalty.tier === 'silver' ? 'نقره‌ای' : 'برنزی'}</small></section>}{profile && <section className="preference-card"><h3>ترجیحات غذایی</h3><label>رژیم<select value={profile.diet} onChange={event => setProfile({ ...profile, diet: event.target.value })}><option value="none">بدون محدودیت</option><option value="vegetarian">گیاه‌خوار</option><option value="vegan">وگان</option></select></label><label>میزان علاقه به تندی<select value={profile.spice_preference ?? ''} onChange={event => setProfile({ ...profile, spice_preference: event.target.value === '' ? null : Number(event.target.value) })}><option value="">ثبت نشده</option>{[0, 1, 2, 3, 4, 5].map(level => <option value={level} key={level}>{level}</option>)}</select></label><label>آلرژن‌ها<input value={profile.allergen_codes.join('، ')} onChange={event => setProfile({ ...profile, allergen_codes: event.target.value.split(/[،,]/).map(value => value.trim()).filter(Boolean) })} placeholder="مثلاً dairy، nuts" /></label><label>مواد دوست‌ندارم<input value={profile.disliked_ingredients.join('، ')} onChange={event => setProfile({ ...profile, disliked_ingredients: event.target.value.split(/[،,]/).map(value => value.trim()).filter(Boolean) })} /></label><label className="consent"><input type="checkbox" checked={profile.ai_personalization_consent} onChange={event => setProfile({ ...profile, ai_personalization_consent: event.target.checked })} /> اجازه استفاده AI از این ترجیحات</label><label className="consent"><input type="checkbox" checked={profile.retention_consent} onChange={event => setProfile({ ...profile, retention_consent: event.target.checked })} /> نگهداری سابقه برای تجربه بهتر</label><label className="consent"><input type="checkbox" checked={profile.marketing_consent} onChange={event => setProfile({ ...profile, marketing_consent: event.target.checked })} /> دریافت پیشنهادهای بازاریابی</label><button disabled={busy} onClick={() => void saveProfile()}>ذخیره ترجیحات</button></section>}<section className="history-card"><h3>سفارش‌های قبلی</h3>{orders.length === 0 ? <p>هنوز سفارشی در حسابت نیست.</p> : orders.map(order => <div key={order.id}><span>{new Date(order.created_at).toLocaleDateString('fa-IR')} · {order.lines.map(line => `${line.quantity}× ${line.item_name}`).join('، ')}</span><button disabled={busy} onClick={() => void reorderOrder(order.id)}>سفارش مجدد</button></div>)}</section>{error && <div className="error">{error}</div>}<footer><button onClick={logout}>خروج</button><button className="danger-link" onClick={() => void erase()}>پاک‌کردن داده‌های شخصی‌سازی</button></footer></div>}</aside></div>
}

type ChatAction = { type: 'cart_changed' | 'confirm_order' | 'order_confirmed'; confirmation_id?: string; expires_at?: string; cart?: Cart; order_id?: string }
type ChatMessage = { id: string; role: 'user' | 'assistant'; content: string; actions?: ChatAction[] }
function ChatPanel({ headers, onCartChanged, onOrderConfirmed }: { headers: Record<string, string>; onCartChanged: () => void; onOrderConfirmed: (orderId: string) => void }) {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [value, setValue] = useState('')
  const [sending, setSending] = useState(false)
  useEffect(() => {
    if (!open || messages.length) return
    void fetch(`${API}/customer/chat/`, { headers }).then(response => response.json()).then(payload => setMessages(payload.data.messages ?? [])).catch(() => undefined)
  }, [open])
  async function send(text = value) {
    const content = text.trim(); if (!content || sending) return
    const optimistic = { id: crypto.randomUUID(), role: 'user' as const, content }
    setMessages(current => [...current, optimistic]); setValue(''); setSending(true)
    const response = await fetch(`${API}/customer/chat/messages/`, { method: 'POST', headers, body: JSON.stringify({ content }) })
    if (response.ok) {
      const payload = await response.json(); const message: ChatMessage = payload.data.message
      setMessages(current => [...current, message])
      if (message.actions?.some(action => action.type === 'cart_changed')) onCartChanged()
      const confirmed = message.actions?.find(action => action.type === 'order_confirmed')
      if (confirmed?.order_id) onOrderConfirmed(confirmed.order_id)
    }
    else setMessages(current => [...current, { id: crypto.randomUUID(), role: 'assistant', content: 'الان نتونستم پاسخ بدم؛ لطفاً دوباره امتحان کن.' }])
    setSending(false)
  }
  async function confirm(action: ChatAction) {
    if (!action.confirmation_id || sending) return
    setSending(true)
    const response = await fetch(`${API}/customer/chat/confirmations/${action.confirmation_id}/confirm/`, { method: 'POST', headers })
    const payload = await response.json()
    if (response.ok) onOrderConfirmed(payload.data.id)
    else setMessages(current => [...current, { id: crypto.randomUUID(), role: 'assistant', content: payload.error?.message ?? 'سبد تغییر کرده یا زمان تأیید گذشته؛ دوباره پیش‌نمایش سفارش را بخواه.' }])
    setSending(false)
  }
  return <><button className="chat-fab" onClick={() => setOpen(current => !current)}>{open ? '×' : '✦'}<span>{open ? 'بستن' : 'از باران بپرس'}</span></button>{open && <aside className="chat-panel"><header><div className="ai-orb">✦</div><div><b>دستیار سفارش باران</b><small><i/> متصل به منو و سبد همین میز</small></div></header><div className="chat-body">{messages.length === 0 && <div className="chat-welcome"><b>سلام! چی برات بیارم؟</b><p>پیشنهاد بگیر، دربارهٔ غذا بپرس یا آیتمی را به سبد اضافه کن.</p><div>{['غذای کم‌کالری چی دارید؟', 'برای دو نفر چی پیشنهاد میدی؟', 'سبدم رو نشون بده'].map(prompt => <button key={prompt} onClick={() => void send(prompt)}>{prompt}</button>)}</div></div>}{messages.map(message => <div className={`message ${message.role}`} key={message.id}><div className={`bubble ${message.role}`}>{message.content}</div>{message.actions?.filter(action => action.type === 'confirm_order').map(action => <div className="confirm-card" key={action.confirmation_id}><small>پیش‌نمایش سفارش</small><b>{money(action.cart?.subtotal ?? 0)} {action.cart?.currency === 'IRR' ? 'ریال' : action.cart?.currency}</b><span>{action.cart?.lines.length ?? 0} ردیف در سبد</span><button disabled={sending} onClick={() => void confirm(action)}>تأیید و ثبت سفارش</button><em>فقط با این دکمه یا تأیید صریح شما ثبت می‌شود.</em></div>)}</div>)}{sending && <div className="typing"><i/><i/><i/></div>}</div><form onSubmit={event => { event.preventDefault(); void send() }}><input value={value} onChange={event => setValue(event.target.value)} placeholder="مثلاً یک برگر به سبدم اضافه کن" maxLength={1000}/><button disabled={!value.trim() || sending}>↑</button></form><footer>قیمت و موجودی از دادهٔ زندهٔ همین شعبه محاسبه می‌شود.</footer></aside>}</>
}

function OrderProgress({ orderId, headers }: { orderId: string; headers: Record<string, string> }) {
  const [status, setStatus] = useState('pending')
  const [payment, setPayment] = useState<{ status: string; method: string | null }>({ status: 'unpaid', method: null })
  const [paymentBusy, setPaymentBusy] = useState('')
  const [paymentError, setPaymentError] = useState('')
  const states = ['pending', 'confirmed', 'preparing', 'ready', 'completed']
  const labels: Record<string, string> = { pending: 'ارسال‌شده', confirmed: 'تأیید رستوران', preparing: 'در حال آماده‌سازی', ready: 'آماده تحویل', completed: 'تحویل شد', cancelled: 'لغو شد' }
  useEffect(() => {
    async function refresh() {
      const response = await fetch(`${API}/customer/orders/${orderId}/`, { headers })
      if (response.ok) { const order = (await response.json()).data; setStatus(order.status); setPayment(order.payment) }
    }
    void refresh(); const timer = setInterval(() => void refresh(), 8000)
    return () => clearInterval(timer)
  }, [orderId])
  async function startPayment(method: 'cash' | 'pos' | 'online') {
    setPaymentBusy(method); setPaymentError('')
    const response = await fetch(`${API}/customer/payments/`, { method: 'POST', headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, body: JSON.stringify({ order_id: orderId, method }) })
    const payload = await response.json()
    if (!response.ok) { setPaymentError(payload.error?.message ?? 'شروع پرداخت ممکن نشد.'); setPaymentBusy(''); return }
    if (method === 'online' && payload.data.checkout) {
      const verify = await fetch(`${API}/customer/payments/${payload.data.id}/mock-confirm/`, { method: 'POST', headers, body: JSON.stringify({ token: payload.data.checkout.token }) })
      if (!verify.ok) { setPaymentError('تأیید پرداخت آزمایشی انجام نشد.'); setPaymentBusy(''); return }
      setPayment({ status: 'paid', method: 'online' })
    } else setPayment({ status: 'pending', method })
    setPaymentBusy('')
  }
  const current = states.indexOf(status)
  return <div className="state success" dir="rtl"><div className="check">✓</div><p className="kicker">سفارش ثبت شد</p><h1>{status === 'ready' ? 'سفارشت آماده‌ست!' : status === 'completed' ? 'نوش جان!' : 'در حال پیگیری سفارش'}</h1><div className="order-progress">{states.map((item, index) => <div className={index <= current ? 'done' : ''} key={item}><i>{index < current ? '✓' : index + 1}</i><span>{labels[item]}</span></div>)}</div><p>شماره پیگیری: <b>{orderId.slice(0, 8)}</b></p>{payment.status === 'paid' ? <div className="payment-success">✓ پرداخت با موفقیت ثبت شد</div> : <section className="payment-box"><b>روش پرداخت را انتخاب کن</b><p>{payment.status === 'pending' ? 'درخواست پرداخت ثبت شده؛ صندوق‌دار آن را نهایی می‌کند.' : 'پرداخت آنلاین فعلاً با درگاه امن آزمایشی انجام می‌شود.'}</p><div><button disabled={!!paymentBusy} onClick={() => void startPayment('online')}>{paymentBusy === 'online' ? 'در حال اتصال…' : 'پرداخت آنلاین'}</button><button disabled={!!paymentBusy} onClick={() => void startPayment('pos')}>کارت‌خوان</button><button disabled={!!paymentBusy} onClick={() => void startPayment('cash')}>نقدی</button></div>{paymentError && <span>{paymentError}</span>}</section>}{status === 'cancelled' && <div className="error">این سفارش لغو شده است.</div>}</div>
}
