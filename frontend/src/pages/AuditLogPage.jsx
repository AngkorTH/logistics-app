// หน้าประวัติเหตุการณ์ (Audit Log) — Admin+ เท่านั้น (task 5)
// แสดงว่า ใคร/ทำอะไร/ที่ข้อมูลไหน/เมื่อไหร่/รายละเอียด(เหตุผล)
// รวมเหตุการณ์จาก task 1 (เปลี่ยนสถานะ) และ task 2 (แก้ยอดเงิน OCR) โดยอัตโนมัติ
import { useState } from 'react'
import { useAuditLogs, useTrips } from '../api/hooks'
import { useAuth } from '../auth/AuthContext'
import { Btn } from '../components/ui'
import TripDetailModal from '../components/TripDetailModal'

// ปุ่มกรองด่วนตาม action ที่สำคัญ
const QUICK = [
  { key: '', th: 'ทั้งหมด' },
  { key: 'เปลี่ยนสถานะ', th: '🔧 เปลี่ยนสถานะ' },
  { key: 'แก้ยอดเงิน', th: '✏️ แก้ยอดเงิน OCR' },
  { key: 'หักเงิน', th: '💸 หักเงิน' },
  { key: 'แก้ไขข้อมูลทริป', th: '📝 แก้ไขทริป' },
  { key: 'จ่ายงาน', th: '🚦 จ่ายงาน' },
]

export default function AuditLogPage() {
  const [action, setAction] = useState('')
  const [target, setTarget] = useState('')
  // ข้อ 3.1: ค้นหาด้วย "ใครเป็นคนแก้" + เดือน/ปี ได้
  const [who, setWho] = useState('')
  const [month, setMonth] = useState('')  // '' = ทุกเดือน
  const [year, setYear] = useState('')    // '' = ทุกปี
  const { data: logs, isLoading, error } = useAuditLogs({
    action, target, who,
    month: month ? Number(month) : undefined,
    year: year ? Number(year) : undefined,
  })
  // map รหัสทริป (เช่น "T-001") → tripId เพื่อกดข้ามไปหน้ารายละเอียดทริปได้จากแต่ละแถว
  const { user } = useAuth()
  const { data: trips } = useTrips()
  const tripIdByCode = Object.fromEntries((trips || []).map((t) => [t.code, t.id]))
  const [detailId, setDetailId] = useState(null)  // ทริปที่กำลังเปิดดูรายละเอียด/แก้ไข
  const [toast, setToast] = useState('')
  const notify = (msg) => { setToast(msg); setTimeout(() => setToast(''), 3500) }
  const now = new Date()
  const YEARS = Array.from({ length: 5 }, (_, i) => now.getFullYear() - i)
  const MONTHS = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']

  return (
    <div className="space-y-4">
      {/* ---- ตัวกรอง ---- */}
      <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
        <div className="flex flex-wrap gap-1">
          {QUICK.map((q) => (
            <button key={q.key} onClick={() => setAction(q.key)}
              className={`text-xs px-2.5 py-1.5 rounded-lg font-medium ${action === q.key ? 'bg-slate-800 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}>
              {q.th}
            </button>
          ))}
        </div>
        <div className="flex-1">
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">🔍</span>
            <input className="w-full border border-slate-300 rounded-lg pl-9 pr-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-200"
              value={target} onChange={(e) => setTarget(e.target.value)}
              placeholder="ค้นหาตามข้อมูล/รหัสทริป เช่น T-001…" />
          </div>
        </div>
      </div>

      {/* ---- ตัวกรองชั้นสอง: ใครเป็นคนแก้ + เดือน/ปี (ข้อ 3.1) ---- */}
      <div className="flex flex-col sm:flex-row gap-3">
        <input className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-200"
          value={who} onChange={(e) => setWho(e.target.value)}
          placeholder="👤 ค้นหาตามชื่อผู้แก้ เช่น ธนพล หรือ SV01…" />
        <select className="border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none"
          value={month} onChange={(e) => setMonth(e.target.value)} disabled={!year}
          title={!year ? 'เลือกปีก่อนจึงจะกรองเดือนได้' : ''}>
          <option value="">ทุกเดือน</option>
          {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
        </select>
        <select className="border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none"
          value={year} onChange={(e) => { setYear(e.target.value); if (!e.target.value) setMonth('') }}>
          <option value="">ทุกปี</option>
          {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
      </div>

      {/* ---- ตาราง Audit ---- */}
      <div className="bg-white rounded-xl ring-1 ring-slate-200 shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-100 font-bold text-slate-700 text-sm flex items-center justify-between">
          <span>🛡️ ประวัติเหตุการณ์ระบบ (Audit Trail)</span>
          <span className="text-xs font-normal text-slate-400">{logs?.length || 0} รายการล่าสุด</span>
        </div>
        {isLoading ? (
          <div className="text-sm text-slate-400 text-center py-6">กำลังโหลด…</div>
        ) : error ? (
          <div className="text-sm text-red-500 text-center py-6">โหลดข้อมูลไม่สำเร็จ</div>
        ) : !logs.length ? (
          <div className="text-sm text-slate-300 text-center py-6">— ไม่พบเหตุการณ์ —</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[720px]">
              <thead className="bg-slate-50 text-slate-500 text-xs">
                <tr>
                  <th className="text-left px-4 py-2.5">เวลา</th>
                  <th className="text-left px-4 py-2.5">ผู้กระทำ</th>
                  <th className="text-left px-4 py-2.5">การกระทำ</th>
                  <th className="text-left px-4 py-2.5">ข้อมูล</th>
                  <th className="text-left px-4 py-2.5">รายละเอียด / เหตุผล</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {logs.map((l) => (
                  <tr key={l.id} className="hover:bg-slate-50 align-top">
                    <td className="px-4 py-2.5 text-slate-400 text-xs whitespace-nowrap">{new Date(l.at).toLocaleString('th-TH')}</td>
                    <td className="px-4 py-2.5 text-slate-700 whitespace-nowrap">{l.who}</td>
                    <td className="px-4 py-2.5"><span className="text-xs bg-slate-100 rounded px-2 py-0.5 text-slate-600 whitespace-nowrap">{l.action}</span></td>
                    <td className="px-4 py-2.5 text-slate-500 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <span>{l.target}</span>
                        {/* ปุ่มข้ามไปหน้ารายละเอียดทริป — โผล่เฉพาะแถวที่ target เป็นรหัสทริปจริง */}
                        {tripIdByCode[l.target] && (
                          <Btn size="sm" color="ghost" onClick={() => setDetailId(tripIdByCode[l.target])}>
                            🔎 ดูรายละเอียดทริป
                          </Btn>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-slate-500 text-xs">{l.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* รายละเอียดทริป + แก้ไข (frozen → ปลดล็อกก่อนแก้) — reuse ตัวเดียวกับหน้าประวัติทริป */}
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
