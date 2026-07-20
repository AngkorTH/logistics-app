// 📅 ประวัติงาน + เงินของฉัน (Driver เท่านั้น) — Mobile-First การ์ดใหญ่ อ่านง่าย
// ยิง GET /users/{ตัวเอง}/history/monthly — backend อนุญาตให้คนขับดู "ของตัวเองเท่านั้น"
// โหลดครั้งเดียวได้ 2 อย่าง: สรุปรายเดือน (months) + ตารางรายเที่ยวของเดือนที่เลือก (trips)
import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { useMonthlyHistory } from '../api/hooks'
import { ImageLightbox, PhotoThumb, money } from '../components/ui'

const MONTHS = [
  'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
  'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม',
]
const now = new Date()
const YEARS = Array.from({ length: 3 }, (_, i) => now.getFullYear() - i)
const selectCls = 'rounded-xl border border-slate-300 px-3 py-2.5 text-base font-semibold bg-white outline-none focus:ring-2 focus:ring-blue-200'

/* การ์ด 1 เที่ยว — แตะเพื่อกางดูขาย่อยที่วิ่งไปในเที่ยวนั้น */
function TripCard({ t }) {
  const [open, setOpen] = useState(false)
  const [zoom, setZoom] = useState(null)   // รูปหลักฐานที่กดขยายดูเต็มจอ
  const subs = t.sub_trips || []
  return (
    <div className="bg-white rounded-2xl ring-1 ring-slate-200 shadow-sm overflow-hidden">
      <button onClick={() => setOpen((v) => !v)} className="w-full text-left px-4 py-3.5">
        <div className="flex items-center justify-between">
          <span className="font-bold text-slate-800">🚛 {t.code}</span>
          <span className="text-xs text-slate-400">
            {t.closed_at ? new Date(t.closed_at).toLocaleDateString('th-TH') : '—'}
          </span>
        </div>
        <div className="text-[11px] text-slate-400 mt-0.5">
          {t.plate || 'ไม่ระบุทะเบียน'} · {t.drops} ขา · {t.distance_km.toLocaleString('th-TH')} กม.
        </div>
        <div className="flex items-center gap-2 mt-2">
          <span className="rounded-lg bg-emerald-50 ring-1 ring-emerald-200 px-2.5 py-1 text-sm font-bold text-emerald-700">
            ได้รับ {money(t.allowance_net)}
          </span>
          {t.penalty > 0 && (
            <span className="rounded-lg bg-red-50 ring-1 ring-red-200 px-2.5 py-1 text-sm font-bold text-red-600">
              ถูกหัก {money(t.penalty)}
            </span>
          )}
          <span className="ml-auto text-slate-400 text-sm">{open ? '▾' : '▸'}</span>
        </div>
      </button>
      {open && (
        <div className="border-t border-slate-100 bg-slate-50/70 px-4 py-3 space-y-1.5">
          {!subs.length && <div className="text-xs text-slate-400">— ไม่มีข้อมูลขาย่อย —</div>}
          {subs.map((d) => (
            <div key={d.seq} className="flex items-center gap-2 text-sm bg-white rounded-xl ring-1 ring-slate-200 px-3 py-2">
              <span className="text-[11px] text-slate-400">#{d.seq}</span>
              <span className="font-medium text-slate-600 truncate">{d.origin}</span>
              <span className="text-orange-500">➜</span>
              <span className="font-semibold text-slate-800 truncate">{d.destination}</span>
              {/* รูปหลักฐานที่ตัวเองส่งไป — กดดูย้อนหลังได้ */}
              <PhotoThumb src={d.loaded_photo} label={`ของที่ขน ขา ${d.seq}`} onZoom={setZoom} size="w-8 h-8" />
              <PhotoThumb src={d.photo} label={`ส่งของ ขา ${d.seq}`} onZoom={setZoom} size="w-8 h-8" />
              <span className="ml-auto text-xs font-bold text-emerald-700 shrink-0">{money(d.allowance)}</span>
            </div>
          ))}
        </div>
      )}
      <ImageLightbox image={zoom} onClose={() => setZoom(null)} />
    </div>
  )
}

export default function MyHistoryPage() {
  const { user } = useAuth()
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [year, setYear] = useState(now.getFullYear())

  const { data, isLoading, error } = useMonthlyHistory(user.id, { year, month })

  const trips = data?.trips || []
  // ยอดรวมของเดือนที่เลือก — คิดจากรายเที่ยวที่ backend ส่งมา (ตรงกับที่โชว์ในตาราง)
  const sumAllowance = trips.reduce((s, t) => s + t.allowance_net, 0)
  const sumPenalty = trips.reduce((s, t) => s + t.penalty, 0)
  const sumKm = trips.reduce((s, t) => s + t.distance_km, 0)

  return (
    <div className="max-w-md mx-auto space-y-4 fadein">
      <div className="bg-white rounded-2xl ring-1 ring-slate-200 shadow-sm p-4">
        <div className="text-base font-bold text-slate-700 mb-2">📅 เลือกเดือนที่ต้องการดู</div>
        <div className="flex gap-2">
          <select className={`${selectCls} flex-1`} value={month} onChange={(e) => setMonth(Number(e.target.value))}>
            {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
          </select>
          <select className={selectCls} value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
      </div>

      {isLoading && <div className="text-center text-slate-400 py-10">กำลังโหลดประวัติ…</div>}
      {error && <div className="text-center text-red-500 py-10 text-sm">โหลดประวัติไม่สำเร็จ — ตรวจสอบสัญญาณ</div>}

      {data && (
        <>
          {/* สรุปเงินของเดือนนี้ — ตัวใหญ่ อ่านกลางแดดได้ */}
          <div className="rounded-2xl bg-slate-800 text-white p-5 shadow-lg">
            <div className="text-sm text-slate-300">รวมเดือน {MONTHS[month - 1]} {year}</div>
            <div className="text-3xl font-extrabold mt-1">{money(sumAllowance)}</div>
            <div className="text-xs text-slate-400 mt-0.5">เบี้ยเลี้ยงสุทธิที่ได้รับ (หลังหักแล้ว)</div>
            <div className="grid grid-cols-3 gap-2 mt-4">
              {[
                { th: 'เที่ยว', v: `${trips.length}` },
                { th: 'ระยะทาง', v: `${sumKm.toLocaleString('th-TH')} กม.` },
                { th: 'ถูกหัก', v: money(sumPenalty) },
              ].map((x) => (
                <div key={x.th} className="rounded-xl bg-white/10 px-2 py-2 text-center">
                  <div className="text-[10px] text-slate-300">{x.th}</div>
                  <div className="text-sm font-bold">{x.v}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="text-sm font-bold text-slate-600">🚛 เที่ยวที่ปิดงานแล้ว ({trips.length})</div>
          {!trips.length ? (
            <div className="text-center text-slate-400 text-sm py-8 border border-dashed border-slate-200 rounded-2xl">
              — เดือนนี้ยังไม่มีเที่ยวที่ปิดงาน —
            </div>
          ) : (
            <div className="space-y-2.5">{trips.map((t) => <TripCard key={t.trip_id} t={t} />)}</div>
          )}

          <div className="text-[11px] text-slate-400 text-center pt-2">
            ตัวเลขนี้นับเฉพาะเที่ยวที่คนคุมงาน “ล็อกการเงิน” แล้วเท่านั้น
          </div>
        </>
      )}
    </div>
  )
}
