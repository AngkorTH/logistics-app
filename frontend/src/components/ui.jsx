// Shared UI components — หั่นมาจาก prototype-ui.tsx.html (Btn / Field / Modal / StatusPill / Stat)
export const STATUS = {
  WHITE:  { key: 'WHITE',  th: 'รองาน',           color: 'bg-white',      ring: 'ring-slate-300',   dot: 'bg-slate-400',   text: 'text-slate-600' },
  ORANGE: { key: 'ORANGE', th: 'กำลังไปขึ้นของ',  color: 'bg-orange-50',  ring: 'ring-orange-400',  dot: 'bg-orange-500',  text: 'text-orange-700' },
  GREEN:  { key: 'GREEN',  th: 'กำลังไปส่ง',       color: 'bg-emerald-50', ring: 'ring-emerald-400', dot: 'bg-emerald-500', text: 'text-emerald-700' },
}

export const ROLES = {
  DRIVER:      { key: 'DRIVER',      th: 'พนักงานขับรถ',  icon: '🚚' },
  SUPERVISOR:  { key: 'SUPERVISOR',  th: 'คนคุมงาน',       icon: '📋' },
  ADMIN:       { key: 'ADMIN',       th: 'แอดมิน',         icon: '🛡️' },
  SUPER_ADMIN: { key: 'SUPER_ADMIN', th: 'ซุปเปอร์แอดมิน', icon: '👑' },
}

export const money = (n) => '฿' + (n || 0).toLocaleString('th-TH')

// ความยากทริป (Trip Difficulty) — ใช้ทั้งฟอร์มจ่ายงานและคิว dispatch
// rate = เปอร์เซ็นต์เบี้ยเลี้ยง (ต้องตรงกับ ALLOWANCE_RATE ฝั่ง backend)
export const DIFFICULTY = {
  EASY:   { key: 'EASY',   th: 'ง่าย',      rate: 0.05, cls: 'bg-emerald-100 text-emerald-700' },
  MEDIUM: { key: 'MEDIUM', th: 'ปานกลาง',  rate: 0.07, cls: 'bg-amber-100 text-amber-700' },
  HARD:   { key: 'HARD',   th: 'ยาก',       rate: 0.10, cls: 'bg-red-100 text-red-700' },
}

// เบี้ยเลี้ยงต่อขา = รายได้ต่อขา × เปอร์เซ็นต์ความยาก (พรีวิวสดในฟอร์มจ่ายงาน)
export const calcAllowance = (revenue, difficulty) =>
  Math.round((Number(revenue) || 0) * (DIFFICULTY[difficulty]?.rate || 0) * 100) / 100

// ⭐ Star rating — เรนเดอร์คะแนนคนขับเป็น "รูปดาว" เท่านั้น (ไม่มีตัวเลข/คำอธิบาย)
// value = 0-5 · เต็มดาว = สีเหลือง, ที่เหลือ = เทาจาง
export function Stars({ value = 0, size = 16 }) {
  const n = Math.max(0, Math.min(5, Math.round(value)))
  return (
    <span className="inline-flex items-center gap-0.5" aria-label={`rating ${n}`} role="img">
      {[1, 2, 3, 4, 5].map((i) => (
        <svg key={i} width={size} height={size} viewBox="0 0 20 20"
          fill={i <= n ? '#f59e0b' : '#e2e8f0'} aria-hidden="true">
          <path d="M10 1.5l2.6 5.3 5.8.85-4.2 4.1 1 5.75L10 14.9l-5.2 2.7 1-5.75-4.2-4.1 5.8-.85L10 1.5z" />
        </svg>
      ))}
    </span>
  )
}

export const inputCls =
  'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-400 outline-none'

export function Btn({ children, onClick, color = 'slate', size = 'md', disabled, className = '', type = 'button' }) {
  const colors = {
    slate: 'bg-slate-700 hover:bg-slate-800 text-white',
    orange: 'bg-orange-500 hover:bg-orange-600 text-white',
    green: 'bg-emerald-500 hover:bg-emerald-600 text-white',
    blue: 'bg-blue-500 hover:bg-blue-600 text-white',
    red: 'bg-red-500 hover:bg-red-600 text-white',
    ghost: 'bg-slate-100 hover:bg-slate-200 text-slate-700',
    outline: 'border border-slate-300 text-slate-600 hover:bg-slate-50',
  }
  const sizes = { sm: 'text-xs px-2.5 py-1.5', md: 'text-sm px-3.5 py-2', lg: 'text-sm px-4 py-2.5' }
  return (
    <button type={type} onClick={onClick} disabled={disabled}
      className={`rounded-lg font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${colors[color]} ${sizes[size]} ${className}`}>
      {children}
    </button>
  )
}

export function Field({ label, children, hint }) {
  return (
    <div className="mb-3">
      <label className="block text-xs font-medium text-slate-600 mb-1">{label}</label>
      {children}
      {hint && <p className="text-[10px] text-slate-400 mt-1">{hint}</p>}
    </div>
  )
}

export function Modal({ title, children, onClose, wide }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onClick={onClose}>
      <div className={`bg-white rounded-2xl shadow-2xl w-full ${wide ? 'max-w-lg' : 'max-w-md'} max-h-[90vh] overflow-y-auto fadein`}
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 sticky top-0 bg-white z-10">
          <h3 className="font-bold text-slate-800">{title}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-xl leading-none">×</button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  )
}

export function StatusPill({ status }) {
  const s = STATUS[status] || STATUS.WHITE
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ring-1 ${s.ring} ${s.text} bg-white`}>
      <span className={`w-2 h-2 rounded-full ${s.dot}`}></span>{s.th}
    </span>
  )
}

// Phase 4: รูปหลักฐานจริง — thumbnail คลิกขยายดูเต็มจอ
// src เป็น "attached" (ข้อมูลเก่าก่อนมีระบบไฟล์) จะโชว์ badge ✔ แทนรูป
export function PhotoThumb({ src, label, onZoom, size = 'w-14 h-14' }) {
  const viewable = !!src && (src.startsWith('/uploads/') || src.startsWith('data:image/'))
  if (!src) return null
  if (!viewable) {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] text-slate-400 bg-slate-100 rounded px-1.5 py-1"
        title={`${label} (ข้อมูลเก่า — ไม่มีไฟล์รูป)`}>✔ {label}</span>
    )
  }
  return (
    <button type="button" onClick={() => onZoom?.({ src, label })} title={`คลิกเพื่อขยาย: ${label}`}
      className={`relative ${size} rounded-lg overflow-hidden ring-1 ring-slate-300 hover:ring-blue-400 transition shrink-0`}>
      <img src={src} alt={label} className="w-full h-full object-cover" loading="lazy" />
      <span className="absolute bottom-0 inset-x-0 bg-black/50 text-white text-[8px] leading-tight px-0.5 truncate">{label}</span>
    </button>
  )
}

// Full-size Image Modal — ซูมดูใบเสร็จ/จุดชำรุดชัดๆ (คลิกพื้นหลังเพื่อปิด)
export function ImageLightbox({ image, onClose }) {
  if (!image) return null
  return (
    <div className="fixed inset-0 z-[70] bg-black/85 flex flex-col items-center justify-center p-4" onClick={onClose}>
      <img src={image.src} alt={image.label} className="max-w-full max-h-[85vh] rounded-lg shadow-2xl object-contain"
        onClick={(e) => e.stopPropagation()} />
      <div className="mt-3 text-white text-sm font-medium">{image.label}</div>
      <button onClick={onClose} className="mt-1 text-slate-300 text-xs underline">ปิด (หรือแตะพื้นหลัง)</button>
    </div>
  )
}

export function Stat({ label, value, dot, accent, sub }) {
  return (
    <div className="bg-white rounded-xl p-4 ring-1 ring-slate-200 shadow-sm">
      <div className="flex items-center gap-2 text-slate-500 text-xs font-medium">
        {dot && <span className={`w-2.5 h-2.5 rounded-full ${dot}`}></span>}{label}
      </div>
      <div className={`text-2xl font-bold mt-1 ${accent || 'text-slate-800'}`}>{value}</div>
      {sub && <div className="text-[10px] text-slate-400 mt-0.5">{sub}</div>}
    </div>
  )
}
