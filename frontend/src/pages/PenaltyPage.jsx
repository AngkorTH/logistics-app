// หน้า "ระบบประวัติและสรุปการหักเงิน" (Dedicated Penalty Page) — Supervisor+ เท่านั้น
// - Month/Year Picker + ช่องค้นหาชื่อคนขับ → ยิง GET /penalties?driver_name=&month=&year=
// - คลิกชื่อคนขับในตาราง → เปิด TripDetailModal ของทริปที่โดนหักเงินนั้น
import { useState } from 'react'
import { usePenaltyList, useLeaderboard } from '../api/hooks'
import { useAuth } from '../auth/AuthContext'
import { money, inputCls } from '../components/ui'
import TripDetailModal from '../components/TripDetailModal'

const MONTHS = [
  'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
  'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม',
]
const now = new Date()
const YEARS = Array.from({ length: 5 }, (_, i) => now.getFullYear() - i)

export default function PenaltyPage() {
  const { user } = useAuth()
  const [tab, setTab] = useState('list')                  // list | leaderboard
  const [month, setMonth] = useState(now.getMonth() + 1)  // 1-12
  const [year, setYear] = useState(now.getFullYear())
  const [driverName, setDriverName] = useState('')
  const [detailId, setDetailId] = useState(null)

  const { data: rows, isLoading, error } = usePenaltyList({ driver_name: driverName, month, year })
  const { data: board, isLoading: boardLoading } = useLeaderboard({ month, year })
  const total = (rows || []).reduce((s, p) => s + p.amount, 0)
  const isSuperAdmin = user.role === 'SUPER_ADMIN'

  return (
    <div className="space-y-4">
      {/* ---- แท็บ: รายการ / จัดอันดับ ---- */}
      <div className="flex gap-1 bg-slate-200/60 rounded-lg p-1 w-fit">
        {[['list', '📋 รายการหักเงิน'], ['leaderboard', '🏆 จัดอันดับคนโดนหัก']].map(([k, th]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`text-xs px-3 py-1.5 rounded-md font-medium ${tab === k ? 'bg-white shadow-sm text-slate-800' : 'text-slate-500'}`}>
            {th}
          </button>
        ))}
      </div>

      {/* ---- ตัวกรอง: เดือn/ปี + ค้นหาชื่อคนขับ (เฉพาะแท็บรายการ) ---- */}
      <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
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
        {tab === 'list' && (
          <div className="flex-1">
            <label className="block text-xs font-medium text-slate-600 mb-1">ค้นหาชื่อคนขับ</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">🔍</span>
              <input className={`${inputCls} pl-9`} value={driverName} onChange={(e) => setDriverName(e.target.value)}
                placeholder="พิมพ์ชื่อคนขับเพื่อกรอง…" />
            </div>
          </div>
        )}
      </div>

      {/* ---- แท็บจัดอันดับ (Leaderboard) ---- */}
      {tab === 'leaderboard' && (
        <div className="bg-white rounded-xl ring-1 ring-slate-200 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 font-bold text-slate-700 text-sm">
            🏆 อันดับคนโดนหักเงินมากที่สุด — {MONTHS[month - 1]} {year}
          </div>
          {boardLoading ? (
            <div className="text-sm text-slate-400 text-center py-6">กำลังโหลด…</div>
          ) : !board?.length ? (
            <div className="text-sm text-slate-300 text-center py-6">— ไม่มีการหักเงินในเดือน/ปีที่เลือก —</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[420px]">
                <thead className="bg-slate-50 text-slate-500 text-xs">
                  <tr>
                    <th className="text-left px-4 py-2.5">อันดับ</th>
                    <th className="text-left px-4 py-2.5">คนขับ</th>
                    <th className="text-right px-4 py-2.5">ยอดหักรวม</th>
                    <th className="text-right px-4 py-2.5">จำนวนครั้ง</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {board.map((row, i) => (
                    <tr key={row.driver_id} className="hover:bg-slate-50">
                      <td className="px-4 py-2.5 font-bold text-slate-400">
                        {i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `#${i + 1}`}
                      </td>
                      <td className="px-4 py-2.5 font-medium text-slate-700">{row.driver_name}</td>
                      <td className="px-4 py-2.5 text-right text-red-500 font-semibold">{money(row.total_amount)}</td>
                      <td className="px-4 py-2.5 text-right text-slate-500">{row.count} ครั้ง</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ---- ตารางประวัติการหักเงิน (แท็บรายการ) ---- */}
      {tab === 'list' && (
      <div className="bg-white rounded-xl ring-1 ring-slate-200 shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-100 font-bold text-slate-700 text-sm flex items-center justify-between">
          <span>💸 การหักเงิน — {MONTHS[month - 1]} {year}</span>
          <span className="text-xs font-normal text-slate-500">
            {rows?.length || 0} รายการ · รวม <span className="text-red-500 font-medium">{money(total)}</span>
          </span>
        </div>
        {isLoading ? (
          <div className="text-sm text-slate-400 text-center py-6">กำลังโหลด…</div>
        ) : error ? (
          <div className="text-sm text-red-500 text-center py-6">โหลดข้อมูลไม่สำเร็จ</div>
        ) : !rows.length ? (
          <div className="text-sm text-slate-300 text-center py-6">— ไม่มีรายการหักเงินในเดือน/ปีที่เลือก —</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[560px]">
              <thead className="bg-slate-50 text-slate-500 text-xs">
                <tr>
                  <th className="text-left px-4 py-2.5">คนขับ</th>
                  <th className="text-left px-4 py-2.5">ทริป</th>
                  <th className="text-right px-4 py-2.5">ยอดหัก</th>
                  <th className="text-left px-4 py-2.5">เหตุผล</th>
                  <th className="text-left px-4 py-2.5">บันทึกโดย</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50">
                    <td className="px-4 py-2.5">
                      {/* คลิกชื่อ → เปิดรายละเอียดทริปที่โดนหักเงิน */}
                      <button onClick={() => setDetailId(p.trip_id)}
                        className="text-blue-600 hover:text-blue-700 hover:underline font-medium">
                        {p.driver_name}
                      </button>
                    </td>
                    <td className="px-4 py-2.5 text-slate-400">{p.trip_code}</td>
                    <td className="px-4 py-2.5 text-right text-red-500 font-medium">{money(p.amount)}</td>
                    <td className="px-4 py-2.5 text-slate-500">{p.reason}</td>
                    <td className="px-4 py-2.5 text-slate-400 text-xs">{p.creator_name}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      )}

      {detailId && (
        <TripDetailModal tripId={detailId} isSuperAdmin={isSuperAdmin} onClose={() => setDetailId(null)} onDone={() => {}} />
      )}
    </div>
  )
}
