// 🗂️ Hub "ประวัติรวม" (Master History Folder — ข้อ 3.1)
// เข้ามาเจอหน้าเลือก 3 เมนูย่อยก่อนเสมอ (ต้องกดเลือกถึงจะเห็นข้อมูล):
// (1) ประวัติทริป — ค้นหาชื่อคนขับ/เดือน/ปี (ไม่ใส่ชื่อ = ทุกคนในเดือนนั้น) + Safety Unlock
// (2) ประวัติการแก้ (Audit) — เฉพาะ Admin/Super Admin
// (3) ประวัติหักเงิน — ย้ายหน้าระบบเดิมเข้ามาอยู่ในหมวดนี้
import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { useTrips, useDrivers } from '../api/hooks'
import { money, inputCls, Btn } from '../components/ui'
import TripDetailModal from '../components/TripDetailModal'
import AuditLogPage from './AuditLogPage'
import PenaltyPage from './PenaltyPage'

const ADM = ['ADMIN', 'SUPER_ADMIN']
const MONTHS = [
  'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
  'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม',
]
const now = new Date()
const YEARS = Array.from({ length: 5 }, (_, i) => now.getFullYear() - i)

export default function MasterHistoryPage() {
  const { user } = useAuth()
  const isAdmin = ADM.includes(user.role)
  const [tab, setTab] = useState(null) // null = หน้าเลือกเมนู | 'trips' | 'edits' | 'deductions'

  /* ---------- หน้าเลือกเมนู (Hub) ---------- */
  if (!tab) {
    const cards = [
      { key: 'trips', icon: '📅', th: 'ประวัติทริป', sub: 'ค้นหาด้วยชื่อคนขับ เดือน ปี — ดูรายละเอียดเที่ยว หลักฐาน ยอดหัก + ปลดล็อกแก้ไข' },
      ...(isAdmin ? [{ key: 'edits', icon: '🛡️', th: 'ประวัติการแก้', sub: 'Audit Log การแก้ไขทั้งหมด: ใครแก้ แก้ของใคร แก้อะไร (Admin ขึ้นไป)' }] : []),
      { key: 'deductions', icon: '💸', th: 'ประวัติหักเงิน', sub: 'รายการหักเงินย้อนหลัง + สรุปอันดับ (ระบบเดิมย้ายเข้าหมวดนี้)' },
    ]
    return (
      <div className="grid gap-3 sm:grid-cols-3 max-w-4xl">
        {cards.map((c) => (
          <button key={c.key} onClick={() => setTab(c.key)}
            className="bg-white rounded-2xl ring-1 ring-slate-200 shadow-sm p-6 text-left hover:ring-orange-300 hover:shadow transition">
            <div className="text-4xl mb-3">{c.icon}</div>
            <div className="font-bold text-slate-800">{c.th}</div>
            <div className="text-xs text-slate-400 mt-1 leading-relaxed">{c.sub}</div>
          </button>
        ))}
      </div>
    )
  }

  /* ---------- แถบหัว + ปุ่มกลับ ---------- */
  const label = { trips: '📅 ประวัติทริป', edits: '🛡️ ประวัติการแก้', deductions: '💸 ประวัติหักเงิน' }[tab]
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Btn color="ghost" size="sm" onClick={() => setTab(null)}>← ประวัติรวม</Btn>
        <div className="font-bold text-slate-700">{label}</div>
      </div>
      {tab === 'trips' && <TripHistoryTab />}
      {tab === 'edits' && (isAdmin ? <AuditLogPage /> : null)}
      {tab === 'deductions' && <PenaltyPage />}
    </div>
  )
}

/* ================= (1) ประวัติทริป — ค้นหาทุกคนในเดือน/ปี ================= */
function TripHistoryTab() {
  const { user } = useAuth()
  const { data: trips, isLoading } = useTrips()
  const { data: drivers } = useDrivers()
  const [name, setName] = useState('')
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [year, setYear] = useState(now.getFullYear())
  const [detailId, setDetailId] = useState(null)
  const [toast, setToast] = useState('')

  const notify = (msg) => { setToast(msg); setTimeout(() => setToast(''), 3500) }
  const driverOf = (id) => (drivers || []).find((d) => d.id === id)

  // ประวัติ = ทริปที่ล็อกการเงินแล้ว (frozen) · กรองเดือน/ปีจากวันจบงาน · กรองชื่อ (ว่าง = ทุกคน)
  const rows = (trips || [])
    .filter((t) => t.frozen && t.closed_at)
    .filter((t) => {
      const d = new Date(t.closed_at)
      return d.getFullYear() === year && d.getMonth() + 1 === month
    })
    .filter((t) => {
      if (!name.trim()) return true
      const drv = driverOf(t.driver_id)
      return drv && `${drv.emp_id} ${drv.name}`.toLowerCase().includes(name.trim().toLowerCase())
    })
    .sort((a, b) => new Date(b.closed_at) - new Date(a.closed_at))

  return (
    <div className="space-y-3">
      {/* ---- ตัวกรอง: ชื่อคนขับ (ไม่บังคับ) + เดือน + ปี ---- */}
      <div className="bg-white rounded-xl ring-1 ring-slate-200 shadow-sm p-4 flex flex-col sm:flex-row gap-3 sm:items-end">
        <div className="flex-1">
          <label className="block text-xs font-medium text-slate-600 mb-1">ชื่อคนขับ (เว้นว่าง = แสดงทุกคน)</label>
          <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)}
            placeholder="เช่น สมชาย หรือ D01" />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">เดือน</label>
          <select className={inputCls} value={month} onChange={(e) => setMonth(Number(e.target.value))}>
            {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">ปี</label>
          <select className={inputCls} value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
      </div>

      {isLoading && <div className="text-center text-slate-400 py-10">กำลังโหลด…</div>}
      {!isLoading && rows.length === 0 && (
        <div className="text-center text-slate-400 py-14">
          <div className="text-4xl mb-2">🗂️</div>ไม่พบทริปในประวัติของ {MONTHS[month - 1]} {year}
        </div>
      )}

      {rows.map((t) => {
        const drv = driverOf(t.driver_id)
        const allowance = t.drops.reduce((s, d) => s + d.allowance, 0)
        return (
          <button key={t.id} onClick={() => setDetailId(t.id)}
            className="w-full bg-white rounded-2xl ring-1 ring-slate-200 shadow-sm p-4 text-left hover:ring-orange-300 transition flex flex-wrap items-center gap-3">
            <div className="flex-1 min-w-[220px]">
              <div className="font-bold text-slate-800">
                {t.code} <span className="font-normal text-slate-400 text-sm">· {drv ? `${drv.emp_id} · ${drv.name}` : `#${t.driver_id}`}</span>
                {t.override && <span className="ml-2 text-[10px] font-semibold text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded">มีการ override/แก้ไข</span>}
              </div>
              <div className="text-xs text-slate-500 mt-0.5">
                🚛 {t.plate || '—'} · 📦 {t.drops.length} จุด · เบี้ยเลี้ยง {money(allowance)}
                {t.penalty > 0 && <span className="text-red-500"> · หัก {money(t.penalty)} ({t.penalty_reason || '—'})</span>}
              </div>
              <div className="text-[11px] text-slate-400 mt-0.5">ปิดบัญชีเมื่อ {new Date(t.closed_at).toLocaleString('th-TH')} · 🔒 ล็อกการเงินแล้ว</div>
            </div>
            <span className="text-xs text-slate-400">ดูรายละเอียด →</span>
          </button>
        )
      })}

      {detailId && (
        <TripDetailModal tripId={detailId} isSuperAdmin={user.role === 'SUPER_ADMIN'}
          onClose={() => setDetailId(null)} onDone={notify} />
      )}
      {toast && (
        <div className="fixed bottom-6 inset-x-4 md:inset-x-auto md:right-6 md:w-96 z-50 bg-slate-800 text-white text-sm px-4 py-3 rounded-xl shadow-lg text-center fadein">
          {toast}
        </div>
      )}
    </div>
  )
}
