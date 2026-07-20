// หน้าประวัติทริป (Trip History Flow) — Supervisor+ เท่านั้น
// Flow บังคับ 3 ขั้น: (1) เลือกคนขับ → (2) เลือกเดือน/ปี → (3) กด "ดูประวัติ" ค่อยยิง API
// GET /users/{id}/history/monthly?year=&month= คืนตารางทริปรายเที่ยวของเดือนนั้น
import { useState } from 'react'
import { useDrivers, useMonthlyHistory } from '../api/hooks'
import { money, inputCls, Btn, DIFFICULTY, ImageLightbox, PhotoThumb } from '../components/ui'

const MONTHS = [
  'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
  'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม',
]
const now = new Date()
const YEARS = Array.from({ length: 5 }, (_, i) => now.getFullYear() - i)

/* แถวเที่ยวหลัก 1 เที่ยว — กดเพื่อกางดูงานย่อย (Sub-Trips) เรียงตามลำดับ Origin → Destination */
function TripRow({ t }) {
  const [open, setOpen] = useState(false)
  const [zoom, setZoom] = useState(null)   // รูปหลักฐานที่กดขยายดูเต็มจอ
  const subs = t.sub_trips || []
  return (
    <>
      <tr className="hover:bg-slate-50 cursor-pointer" onClick={() => setOpen((v) => !v)}>
        <td className="px-4 py-3 font-medium text-slate-700">
          <span className="text-slate-400 mr-1.5">{open ? '▾' : '▸'}</span>{t.code}
        </td>
        <td className="px-4 py-3 text-slate-500 text-xs">{new Date(t.closed_at).toLocaleString('th-TH')}</td>
        <td className="px-4 py-3 text-slate-500">{t.plate || '—'}</td>
        <td className="px-4 py-3 text-center">
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${DIFFICULTY[t.difficulty].cls}`}>
            {DIFFICULTY[t.difficulty].th}
          </span>
        </td>
        <td className="px-4 py-3 text-right text-slate-500">{t.distance_km.toLocaleString('th-TH')}</td>
        <td className="px-4 py-3 text-center text-slate-500">{t.drops}</td>
        <td className="px-4 py-3 text-right text-emerald-600 font-medium">{money(t.allowance_net)}</td>
        <td className="px-4 py-3 text-right text-red-500">{t.penalty ? money(t.penalty) : '—'}</td>
      </tr>
      {open && (
        <tr className="bg-slate-50/70">
          <td colSpan={8} className="px-6 py-3">
            <div className="text-xs font-semibold text-slate-500 mb-2">
              📦 งานย่อย (Sub-Trips) ของ {t.code} — {subs.length} ใบ
            </div>
            {!subs.length ? (
              <div className="text-xs text-slate-300">— ไม่มีข้อมูลงานย่อย —</div>
            ) : (
              <div className="space-y-1.5">
                {subs.map((d) => (
                  <div key={d.seq} className="flex items-center gap-2 text-sm bg-white rounded-lg ring-1 ring-slate-200 px-3 py-2">
                    <span className="text-[11px] text-slate-400 w-10">#{d.seq}</span>
                    <span className="font-medium text-slate-600">{d.origin}</span>
                    <span className="text-orange-500">➜</span>
                    <span className="font-semibold text-slate-800">{d.destination}</span>
                    {/* หลักฐานรายขา — คลิกขยายดูย้อนหลัง (ของที่ขน / ผ้าใบ / ส่งของ) */}
                    <span className="flex items-center gap-1 ml-2">
                      <PhotoThumb src={d.loaded_photo} label={`ของที่ขน ขา ${d.seq}`} onZoom={setZoom} size="w-8 h-8" />
                      <PhotoThumb src={d.tarp} label={`ผ้าใบ ขา ${d.seq}`} onZoom={setZoom} size="w-8 h-8" />
                      <PhotoThumb src={d.photo} label={`ส่งของ ขา ${d.seq}`} onZoom={setZoom} size="w-8 h-8" />
                    </span>
                    <span className="ml-auto text-xs text-slate-400">เบี้ยเลี้ยง {money(d.allowance)}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${d.delivered ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-400'}`}>
                      {d.delivered ? 'ส่งแล้ว' : 'ยังไม่ส่ง'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </td>
        </tr>
      )}
      {zoom && (
        <tr>
          <td colSpan={8} className="p-0">
            <ImageLightbox image={zoom} onClose={() => setZoom(null)} />
          </td>
        </tr>
      )}
    </>
  )
}

export default function HistoryPage() {
  const { data: drivers } = useDrivers()
  const [driverId, setDriverId] = useState('')
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [year, setYear] = useState(now.getFullYear())
  // query ที่ "ยืนยันแล้ว" — ตั้งค่าเมื่อกดปุ่มดูประวัติเท่านั้น (บังคับตาม flow)
  const [applied, setApplied] = useState(null)

  const { data, isLoading, isFetching } = useMonthlyHistory(applied?.driverId, {
    year: applied?.year,
    month: applied?.month,
    enabled: !!applied,
  })

  const canSubmit = !!driverId

  return (
    <div className="space-y-4">
      {/* ---- ตัวเลือก 3 ขั้น ---- */}
      <div className="bg-white rounded-xl ring-1 ring-slate-200 shadow-sm p-4">
        <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
          <div className="flex-1">
            <label className="block text-xs font-medium text-slate-600 mb-1">1) เลือกพนักงานขับรถ</label>
            <select className={inputCls} value={driverId} onChange={(e) => setDriverId(e.target.value)}>
              <option value="">— เลือกคนขับ —</option>
              {(drivers || []).map((d) => <option key={d.id} value={d.id}>{d.emp_id} · {d.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">2) เดือน</label>
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
          <Btn color="orange" disabled={!canSubmit}
            onClick={() => setApplied({ driverId, month, year, name: drivers?.find((d) => String(d.id) === String(driverId))?.name })}>
            3) ดูประวัติ
          </Btn>
        </div>
      </div>

      {!applied && <div className="text-sm text-slate-300">เลือกคนขับและเดือน/ปี แล้วกด “ดูประวัติ” เพื่อแสดงข้อมูล</div>}

      {applied && (isLoading || isFetching) && <div className="text-sm text-slate-400">กำลังโหลด…</div>}

      {applied && data && !isFetching && (
        <div className="bg-white rounded-xl ring-1 ring-slate-200 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 font-bold text-slate-700 text-sm">
            📅 ประวัติทริปของ {data.driver_name} — {MONTHS[applied.month - 1]} {applied.year}
            <span className="text-xs font-normal text-slate-400"> ({data.trips.length} เที่ยว)</span>
          </div>
          {!data.trips.length ? (
            <div className="text-sm text-slate-300 text-center py-6">— ไม่มีทริปที่ปิดงานในเดือน/ปีที่เลือก —</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[640px]">
                <thead className="bg-slate-50 text-slate-500 text-xs">
                  <tr>
                    <th className="text-left px-4 py-3">เที่ยวหลัก (กดเพื่อดูงานย่อย)</th>
                    <th className="text-left px-4 py-3">ปิดงานเมื่อ</th>
                    <th className="text-left px-4 py-3">ทะเบียน</th>
                    <th className="text-center px-4 py-3">ความยาก</th>
                    <th className="text-right px-4 py-3">ระยะทาง (กม.)</th>
                    <th className="text-center px-4 py-3">งานย่อย</th>
                    <th className="text-right px-4 py-3">เบี้ยเลี้ยงสุทธิ</th>
                    <th className="text-right px-4 py-3">ยอดหัก</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.trips.map((t) => <TripRow key={t.trip_id} t={t} />)}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
