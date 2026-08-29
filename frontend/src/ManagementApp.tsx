import { FormEvent, useEffect, useRef, useState } from 'react'
import { Field, Row, Section, formPayload, initialValues, roles, sections } from './managementSchema'
import { TableQR } from './TableQR'
import './management.css'

const API = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1').replace(/\/$/, '')
let refreshing: Promise<void> | null = null
function errorText(value: any): string {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) return value.map(errorText).join(' · ')
  return Object.entries(value ?? {}).map(([key, detail]) => `${key}: ${errorText(detail)}`).join('\n')
}
export async function managementRequest(path: string, organization = '', options: RequestInit = {}, retry = true): Promise<any> {
  const token = sessionStorage.getItem('baran_manage_access')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token && !path.startsWith('auth/token') && path !== 'auth/register/') headers.Authorization = `Bearer ${token}`
  if (organization) headers['X-Organization-ID'] = organization
  const response = await fetch(`${API}/${path}`, { ...options, headers: { ...headers, ...options.headers } })
  if (response.status === 401 && token && retry && !path.startsWith('auth/token') && path !== 'auth/register/') {
    if (!refreshing) refreshing = (async () => {
      const renewed = await fetch(`${API}/auth/token/refresh/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh: sessionStorage.getItem('baran_manage_refresh') }) })
      if (!renewed.ok) { sessionStorage.removeItem('baran_manage_access'); sessionStorage.removeItem('baran_manage_refresh'); throw new Error('نشست شما منقضی شده؛ دوباره وارد شوید.') }
      const tokens = await renewed.json()
      sessionStorage.setItem('baran_manage_access', tokens.access)
      if (tokens.refresh) sessionStorage.setItem('baran_manage_refresh', tokens.refresh)
    })().finally(() => { refreshing = null })
    await refreshing
    return managementRequest(path, organization, options, false)
  }
  if (response.status === 204) return null
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(errorText(body.error?.details ?? body.detail ?? body.error?.message ?? `خطای درخواست (${response.status})`))
  return body.data ?? body.results ?? body
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    ref.current?.focus()
    const oldOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = oldOverflow; previous?.focus() }
  }, [])
  return <div className="manage-overlay"><div ref={ref} tabIndex={-1} className="manage-modal" role="dialog" aria-modal="true" aria-label={title} onKeyDown={event => {
    if (event.key === 'Escape') onClose()
    if (event.key === 'Tab') {
      const elements = ref.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href]')
      if (!elements?.length) return
      const first = elements[0], last = elements[elements.length - 1]
      if (event.shiftKey && (document.activeElement === first || document.activeElement === ref.current)) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
  }}><header><h2>{title}</h2><button type="button" className="manage-quiet" onClick={onClose} aria-label="بستن">✕</button></header>{children}</div></div>
}

export function ManagementApp() {
  const [authenticated, setAuthenticated] = useState(() => Boolean(sessionStorage.getItem('baran_manage_access')))
  const [register, setRegister] = useState(false)
  const [me, setMe] = useState<Row | null>(null)
  const [organization, setOrganization] = useState(sessionStorage.getItem('baran_manage_org') ?? '')
  const [data, setData] = useState<Record<string, Row[]>>({})
  const [sectionKey, setSectionKey] = useState('overview')
  const [search, setSearch] = useState('')
  const [branchFilter, setBranchFilter] = useState('')
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [revision, setRevision] = useState(0)
  const [editor, setEditor] = useState<{ section: Section; row?: Row } | null>(null)
  const [values, setValues] = useState<Row>({})
  const [formError, setFormError] = useState('')
  const [action, setAction] = useState<{ type: 'delete' | 'qr' | 'stock'; section: Section; row: Row } | null>(null)
  const [qr, setQr] = useState('')
  const [delta, setDelta] = useState('')
  const [reason, setReason] = useState('')
  const role = me?.organizations?.find((item: Row) => item.id === organization)?.role
  const isAdmin = role === 'owner' || role === 'admin'
  const canManage = isAdmin || role === 'branch_manager'
  const allowedSections = sections.filter(section => !section.adminOnly || isAdmin)
  const section = sections.find(item => item.key === sectionKey)

  function fail(exc: unknown) {
    setError(exc instanceof Error ? exc.message : 'ارتباط با سرور برقرار نشد.')
    if (!sessionStorage.getItem('baran_manage_access')) setAuthenticated(false)
  }
  function logout() {
    for (const key of ['access', 'refresh', 'org']) sessionStorage.removeItem(`baran_manage_${key}`)
    setAuthenticated(false); setMe(null); setData({}); setOrganization(''); setError('')
  }
  useEffect(() => {
    if (!authenticated) return
    let cancelled = false
    setLoading(true); setError('')
    managementRequest('auth/me/').then(user => {
      if (cancelled) return
      setMe(user)
      const saved = sessionStorage.getItem('baran_manage_org')
      const selected = user.organizations?.find((item: Row) => item.id === saved)?.id ?? user.organizations?.[0]?.id ?? ''
      setOrganization(selected); sessionStorage.setItem('baran_manage_org', selected)
      if (!selected) setLoading(false)
    }).catch(exc => { if (!cancelled) { fail(exc); setLoading(false) } })
    return () => { cancelled = true }
  }, [authenticated, revision])

  useEffect(() => {
    if (!authenticated || !organization || !me) return
    const controller = new AbortController()
    let cancelled = false
    setLoading(true); setData({}); setError('')
    const permitted = sections.filter(item => item.key === 'organizations' || (canManage && (!item.adminOnly || isAdmin)))
    Promise.all(permitted.map(async item => [item.key, await managementRequest(item.path, item.key === 'organizations' ? '' : organization, { signal: controller.signal })] as const)).then(entries => {
      if (!cancelled) { setData(Object.fromEntries(entries)); setLoading(false) }
    }).catch(exc => { if (!cancelled) { fail(exc); setLoading(false) } })
    return () => { cancelled = true; controller.abort() }
  }, [authenticated, organization, me, canManage, isAdmin])

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('')
    const fields = new FormData(event.currentTarget)
    const credentials = { email: fields.get('email'), password: fields.get('password') }
    try {
      if (register) await managementRequest('auth/register/', '', { method: 'POST', body: JSON.stringify({ ...credentials, display_name: fields.get('display_name') }) })
      const tokens = await managementRequest('auth/token/', '', { method: 'POST', body: JSON.stringify(credentials) })
      sessionStorage.setItem('baran_manage_access', tokens.access); sessionStorage.setItem('baran_manage_refresh', tokens.refresh)
      setAuthenticated(true)
    } catch (exc) { fail(exc) } finally { setBusy(false) }
  }
  function navigate(key: string) { setSectionKey(key); setSearch(''); setNotice(''); setBranchFilter('') }
  function openEditor(target: Section, row?: Row) {
    setEditor({ section: target, row }); setValues(initialValues(target, row)); setFormError('')
  }
  function labelFor(key: string, id: any): string {
    const row = data[key]?.find(item => String(item.id) === String(id))
    if (!row) return String(id ?? '—')
    if (key === 'stock') return `${labelFor('ingredients', row.ingredient)} · ${labelFor('branches', row.branch)} (${row.unit})`
    return String(row.name ?? row.display_name ?? row.number ?? row.id)
  }
  function display(target: Section, row: Row, key: string): string {
    const field = target.fields.find(item => item.key === key)
    const value = row[key]
    if (value === null || value === undefined || value === '') return '—'
    if (field?.relation) return Array.isArray(value) ? value.map(id => labelFor(field.relation!, id)).join('، ') || 'بدون شعبه' : labelFor(field.relation, value)
    if (field?.options) return field.options.find(([id]) => id === String(value))?.[1] ?? String(value)
    if (typeof value === 'boolean') return value ? 'فعال' : 'غیرفعال'
    if (field?.type === 'datetime-local') return new Date(value).toLocaleString('fa-IR')
    if (typeof value === 'number') return value.toLocaleString('fa-IR')
    return String(value)
  }
  function choices(field: Field): [string, string][] {
    if (!field.relation) return field.options ?? []
    return (data[field.relation] ?? []).filter(row => {
      if (!values.branch || !['table', 'stock_item', 'menu', 'menu_item'].includes(field.key)) return true
      const branch = field.key === 'menu_item' ? data.catalogs?.find(menu => menu.id === data.categories?.find(category => category.id === row.category)?.menu)?.branch : row.branch
      return !branch || String(branch) === String(values.branch)
    }).map(row => [String(row.id), labelFor(field.relation!, row.id)])
  }
  async function save(event: FormEvent) {
    event.preventDefault(); if (!editor) return
    setBusy(true); setFormError('')
    try {
      const result = await managementRequest(`${editor.section.path}${editor.row ? `${editor.row.id}/` : ''}`, editor.section.key === 'organizations' ? '' : organization, { method: editor.row ? 'PATCH' : 'POST', body: JSON.stringify(formPayload(editor.section, values, Boolean(editor.row))) })
      if (editor.section.key === 'organizations' && !editor.row) { sessionStorage.setItem('baran_manage_org', result.id); setOrganization(result.id); setSectionKey('overview') }
      if (result.qr_token) setQr(`${window.location.origin}/?qr=${encodeURIComponent(result.qr_token)}`)
      setEditor(null); setNotice('اطلاعات با موفقیت ذخیره شد.'); setRevision(value => value + 1)
    } catch (exc) { setFormError(exc instanceof Error ? exc.message : 'ذخیره انجام نشد؛ دوباره تلاش کنید.') } finally { setBusy(false) }
  }
  async function performAction(event: FormEvent) {
    event.preventDefault(); if (!action) return
    setBusy(true); setFormError('')
    try {
      const endpoint = `${action.section.path}${action.row.id}/`
      if (action.type === 'delete') await managementRequest(endpoint, organization, { method: 'DELETE' })
      if (action.type === 'qr') {
        const result = await managementRequest(`${endpoint}rotate_qr/`, organization, { method: 'POST', body: '{}' })
        setQr(`${window.location.origin}/?qr=${encodeURIComponent(result.qr_token)}`)
      }
      if (action.type === 'stock') await managementRequest(`${endpoint}adjust/`, organization, { method: 'POST', body: JSON.stringify({ delta, reason }) })
      setAction(null); setNotice('عملیات با موفقیت انجام شد.'); setRevision(value => value + 1)
    } catch (exc) { setFormError(exc instanceof Error ? exc.message : 'عملیات انجام نشد.') } finally { setBusy(false) }
  }
  function fieldInput(field: Field) {
    const value = values[field.key]
    if (field.type === 'multi') return <fieldset className="manage-multi"><legend>{field.label}</legend>{choices(field).map(([id, label]) => <label key={id}><input type="checkbox" checked={(value ?? []).map(String).includes(id)} onChange={event => setValues(current => ({ ...current, [field.key]: event.target.checked ? [...current[field.key], id] : current[field.key].filter((entry: any) => String(entry) !== id) }))} />{label}</label>)}{choices(field).length === 0 && <small>ابتدا رکوردهای این بخش را بسازید.</small>}</fieldset>
    if (field.type === 'checkbox') return <label className="manage-check"><input type="checkbox" checked={Boolean(value)} onChange={event => setValues(current => ({ ...current, [field.key]: event.target.checked }))} />{field.label}</label>
    const properties = { id: `manage-${field.key}`, required: field.required, value: value ?? '', onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setValues(current => ({ ...current, [field.key]: event.target.value })) }
    return <label htmlFor={properties.id}>{field.label}{field.required && <span className="manage-required"> *</span>}{field.relation || field.options ? <select {...properties}><option value="">انتخاب کنید</option>{choices(field).filter(([id]) => field.key !== 'role' || role === 'owner' || id !== 'owner').map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select> : field.type === 'textarea' ? <textarea {...properties} rows={3} /> : <input {...properties} type={field.type === 'tags' ? 'text' : field.type === 'decimal' ? 'number' : field.type ?? 'text'} min={field.min} max={field.max} step={field.type === 'decimal' ? '0.001' : undefined} minLength={field.type === 'password' ? 10 : undefined} autoComplete={field.type === 'password' ? 'new-password' : undefined} />}</label>
  }

  if (!authenticated) return <div className="manage manage-auth" dir="rtl"><section className="manage-auth-story"><a className="manage-brand" href="/">بــاران <span>مرکز مدیریت</span></a><p className="manage-eyebrow">همه‌چیز، در یک نگاه</p><h1>میزبان تجربه‌های<br />به‌یادماندنی باشید.</h1><p>از اولین منو تا آخرین سفارش؛ شعب، تیم و رستوران شما، در یک فضای منظم.</p><div className="manage-auth-tags"><span>منوی هوشمند</span><span>تیم هماهنگ</span><span>مدیریت چندشعبه‌ای</span></div></section><form className="manage-auth-form" onSubmit={login}><small>BARAN / MANAGEMENT</small><h2>{register ? 'ساخت حساب مالک' : 'ورود به مدیریت'}</h2><p>{register ? 'پس از ثبت‌نام، سازمان و اولین شعبه‌تان را بسازید.' : 'با حساب مالک یا مدیر رستوران وارد شوید.'}</p>{register && <label>نام و نام خانوادگی<input name="display_name" required autoComplete="name" /></label>}<label>ایمیل<input type="email" name="email" required autoComplete="email" dir="ltr" /></label><label>رمز عبور<input type="password" name="password" required minLength={register ? 10 : undefined} autoComplete={register ? 'new-password' : 'current-password'} dir="ltr" /></label>{error && <div className="manage-error" role="alert">{error}</div>}<button disabled={busy} type="submit">{busy ? 'در حال پردازش…' : register ? 'ثبت‌نام و شروع' : 'ورود به پنل'}</button><button className="manage-quiet" type="button" disabled={busy} onClick={() => { setRegister(!register); setError('') }}>{register ? 'حساب دارم؛ ورود' : 'اولین بار است؟ ساخت حساب مالک'}</button><a href="/staff">ورود کارکنان به پنل سفارش‌ها ←</a></form></div>

  const rows = (data[sectionKey] ?? []).filter(row => (!branchFilter || String(row.branch) === branchFilter) && (!search || (section?.columns ?? []).some(key => display(section!, row, key).toLocaleLowerCase().includes(search.toLocaleLowerCase()))))
  return <div className="manage manage-shell" dir="rtl"><aside className="manage-sidebar"><a className="manage-brand" href="/manage">بــاران <span>مرکز مدیریت</span></a><label className="manage-org-label">سازمان فعال<select aria-label="سازمان فعال" value={organization} onChange={event => { sessionStorage.setItem('baran_manage_org', event.target.value); setOrganization(event.target.value); setEditor(null); setAction(null); setQr(''); navigate('overview') }}><option value="" disabled>انتخاب سازمان</option>{me?.organizations?.map((item: Row) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><nav aria-label="منوی مدیریت"><button className={sectionKey === 'overview' ? 'selected' : ''} onClick={() => navigate('overview')}>نمای کلی <span>⌂</span></button>{canManage && ['راه‌اندازی', 'منو و فروش', 'عملیات'].map(group => <div key={group}><small>{group}</small>{allowedSections.filter(item => item.group === group).map(item => <button key={item.key} className={sectionKey === item.key ? 'selected' : ''} onClick={() => navigate(item.key)}>{item.title}<span>{data[item.key]?.length ?? '—'}</span></button>)}</div>)}</nav><footer><b>{me?.display_name || me?.email}</b><small>{roles.find(([id]) => id === role)?.[1] ?? 'حساب جدید'}</small><a href="/staff">پنل سفارش‌ها ↗</a><button className="manage-quiet" onClick={logout}>خروج از حساب</button></footer></aside>
    <main className="manage-main"><header className="manage-heading"><div><p className="manage-eyebrow">مدیریت رستوران / {me?.organizations?.find((item: Row) => item.id === organization)?.name ?? 'خوش آمدید'}</p><h1>{section?.title ?? 'امروز، همه‌چیز در کنترل شماست.'}</h1></div><button className="manage-quiet" disabled={loading || busy} onClick={() => setRevision(value => value + 1)}>↻ به‌روزرسانی</button></header>
      {error && <div className="manage-error" role="alert">{error}</div>}{notice && <div className="manage-notice" role="status">{notice}</div>}
      {loading ? <div className="manage-empty" role="status">در حال دریافت اطلاعات…</div> : !organization ? <section className="manage-welcome"><p className="manage-eyebrow">قدم اول</p><h2>رستوران شما از اینجا شروع می‌شود.</h2><p>ابتدا سازمان را بسازید؛ بعد شعبه، منو و همکارانتان را اضافه کنید.</p><button onClick={() => openEditor(sections[0])}>＋ ساخت اولین سازمان</button></section> : !canManage ? <section className="manage-empty"><h2>این حساب دسترسی مدیریت ندارد.</h2><p>برای تغییر تنظیمات، مالک باید نقش مدیریتی به شما بدهد.</p><a href="/staff">رفتن به پنل سفارش‌ها</a><button onClick={() => openEditor(sections[0])}>ساخت سازمان مستقل</button></section> : sectionKey === 'overview' ? <>
        <section className="manage-welcome"><div><p className="manage-eyebrow">فضای کار شما</p><h2>یک رستوران منظم.<br />یک تجربه بهتر.</h2><p>اطلاعات واقعی را ثبت کنید و اولین سفارش را از لینک میز امتحان کنید.</p><button onClick={() => navigate('items')}>مدیریت محصولات ←</button></div><div className="manage-orbit" aria-hidden="true"><span>ب</span><small>BARAN</small></div></section>
        <div className="manage-stats">{[['branches', 'شعبه'], ['items', 'محصول'], ['tables', 'میز'], ['members', 'همکار']].filter(([key]) => key !== 'members' || isAdmin).map(([key, title]) => <button key={key} onClick={() => navigate(key)}><small>{title}</small><strong>{(data[key]?.length ?? 0).toLocaleString('fa-IR')}</strong><span>مشاهده و مدیریت ←</span></button>)}</div>
        <section className="manage-card"><h2>چک‌لیست راه‌اندازی</h2><p>به همین ترتیب پیش بروید تا منوی مشتری آماده شود.</p><div className="manage-checklist">{[['branches', 'ساخت شعبه', 'مکان و کد شعبه'], ['catalogs', 'ساخت منو', 'منوی مشترک یا اختصاصی'], ['categories', 'دسته‌بندی', 'نظم بخشیدن به محصولات'], ['items', 'افزودن غذا', 'قیمت، تصویر و توضیحات'], ['tables', 'ساخت میز', 'دریافت لینک منوی مشتری'], ['members', 'افزودن همکار', 'نقش و شعبه مجاز']].filter(([key]) => key !== 'members' || isAdmin).map(([key, title, subtitle], index) => <button key={key} className="manage-step" onClick={() => navigate(key)}><span>{data[key]?.length ? '✓' : index + 1}</span><div><b>{title}</b><small>{subtitle}</small></div><span>←</span></button>)}</div></section>
      </> : section && <section className="manage-card"><div className="manage-toolbar"><div><h2>{section.title}<small> {rows.length.toLocaleString('fa-IR')} مورد</small></h2><p>{section.description}</p></div>{(section.key !== 'branches' || isAdmin) && <button onClick={() => openEditor(section)}>＋ افزودن {section.singular}</button>}</div><div className="manage-filters"><input aria-label="جست‌وجو" placeholder="جست‌وجو در این بخش…" value={search} onChange={event => setSearch(event.target.value)} />{section.fields.some(field => field.key === 'branch') && <select aria-label="فیلتر شعبه" value={branchFilter} onChange={event => setBranchFilter(event.target.value)}><option value="">همه شعب</option>{data.branches?.map(branch => <option value={branch.id} key={branch.id}>{branch.name}</option>)}</select>}</div>
        {rows.length === 0 ? <div className="manage-empty"><span>＋</span><h3>{search || branchFilter ? 'نتیجه‌ای پیدا نشد.' : 'هنوز چیزی ثبت نشده است.'}</h3><p>{search || branchFilter ? 'جست‌وجو یا فیلتر را تغییر دهید.' : `با افزودن اولین ${section.singular} شروع کنید.`}</p></div> : <div className="manage-table-wrap"><table><thead><tr>{section.columns.map(key => <th key={key}>{section.fields.find(field => field.key === key)?.label ?? key}</th>)}<th>عملیات</th></tr></thead><tbody>{rows.map(row => <tr key={row.id}>{section.columns.map(key => <td key={key} data-label={section.fields.find(field => field.key === key)?.label ?? key}>{key === 'name' && row.image_url && <img src={row.image_url} alt="" loading="lazy" />}<span className={typeof row[key] === 'boolean' ? `manage-badge ${row[key] ? 'on' : 'off'}` : ''}>{display(section, row, key)}</span></td>)}<td className="manage-row-actions" data-label="عملیات">{(section.key !== 'branches' || isAdmin) && <><button className="manage-quiet" onClick={() => openEditor(section, row)}>ویرایش</button>{!section.noDelete && <button className="manage-danger" onClick={() => { setAction({ type: 'delete', section, row }); setFormError('') }}>حذف</button>}</>}{section.key === 'tables' && <button className="manage-quiet" onClick={() => { setAction({ type: 'qr', section, row }); setFormError('') }}>تعویض QR</button>}{section.key === 'stock' && <button className="manage-quiet" onClick={() => { setAction({ type: 'stock', section, row }); setDelta(''); setReason(''); setFormError('') }}>اصلاح موجودی</button>}</td></tr>)}</tbody></table></div>}
      </section>}
      <footer className="manage-bottom">باران · مرکز مدیریت رستوران <a href="/staff">مشاهده سفارش‌ها ↗</a></footer>
    </main>
    {editor && <Modal title={`${editor.row ? 'ویرایش' : 'افزودن'} ${editor.section.singular}`} onClose={() => { if (!busy) setEditor(null) }}><form onSubmit={save}><p>{editor.section.description}</p><div className="manage-form-grid">{editor.section.fields.filter(field => !(editor.row && field.createOnly)).map(field => <div key={field.key} className={['textarea', 'multi'].includes(field.type ?? '') ? 'manage-wide' : ''}>{fieldInput(field)}</div>)}</div>{values.image_url && editor.section.key === 'items' && <img className="manage-preview" src={values.image_url} alt="پیش‌نمایش تصویر محصول" />}{formError && <div className="manage-error" role="alert">{formError}</div>}<footer><button type="submit" disabled={busy}>{busy ? 'در حال ذخیره…' : 'ذخیره اطلاعات'}</button><button type="button" className="manage-quiet" disabled={busy} onClick={() => setEditor(null)}>انصراف</button></footer></form></Modal>}
    {action && <Modal title={action.type === 'delete' ? `حذف ${action.section.singular}` : action.type === 'qr' ? 'تعویض لینک و QR میز' : 'اصلاح موجودی انبار'} onClose={() => { if (!busy) setAction(null) }}><form onSubmit={performAction}>{action.type === 'stock' ? <><p>موجودی فعلی: {action.row.quantity} {action.row.unit}</p><label>مقدار تغییر (منفی برای کاهش)<input type="number" step="0.001" value={delta} required onChange={event => setDelta(event.target.value)} /></label><label>دلیل تغییر<input maxLength={60} value={reason} required onChange={event => setReason(event.target.value)} /></label></> : <p>{action.type === 'delete' ? `آیا از حذف «${action.row.name ?? action.row.email ?? action.row.number ?? action.section.singular}» مطمئنید؟ رکوردهای وابسته ممکن است حذف شوند. این عملیات قابل بازگشت نیست؛ برای حفظ سابقه، در صورت امکان غیرفعال‌سازی را انتخاب کنید.` : 'لینک و QR قبلی این میز باطل می‌شود. پس از تأیید، لینک جدید را ذخیره و جایگزین نسخه قبلی کنید.'}</p>}{formError && <div className="manage-error" role="alert">{formError}</div>}<footer><button disabled={busy} type="submit">{busy ? 'در حال انجام…' : 'تأیید و انجام'}</button><button className="manage-quiet" disabled={busy} type="button" onClick={() => setAction(null)}>انصراف</button></footer></form></Modal>}
    {qr && <Modal title="لینک منوی این میز آماده است" onClose={() => setQr('')}><p>این لینک فقط همین‌بار نمایش داده می‌شود؛ آن را برای چاپ QR یا استفاده مشتری ذخیره کنید. لینک localhost فقط روی همین کامپیوتر کار می‌کند.</p><TableQR url={qr} /><label>لینک مشتری<input readOnly dir="ltr" value={qr} onFocus={event => event.target.select()} /></label><div className="manage-qr-actions"><a href={qr} target="_blank" rel="noreferrer">بازکردن منوی مشتری ↗</a><button onClick={() => void navigator.clipboard.writeText(qr).then(() => setNotice('لینک کپی شد.')).catch(() => setNotice('کپی خودکار ممکن نشد؛ متن لینک را انتخاب و کپی کنید.'))}>کپی لینک</button></div></Modal>}
  </div>
}
