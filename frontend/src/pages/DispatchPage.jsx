// หน้าจัดการคิวงาน (Smart Dispatch) — Supervisor+ เท่านั้น
// - GET /dispatch/queue: คนขับจัดกลุ่ม 3 สี · กลุ่ม White เรียงลำดับมาจาก Backend แล้ว
// - Search bar (?q=) ค้นด้วยชื่อคนขับ/ทะเบียนรถ แบบเรียลไทม์
// - คลิกชื่อคนขับที่ติดงาน → เปิด TripDetailModal ของ active_trip_id
// - ศูนย์อนุมัติ (OCR Draft + คำขอปลดล็อก) ย้ายมาไว้ที่นี่ (ออกจาก Dashboard)
// คะแนนคนขับ = แสดงเป็น "ดาว" เท่านั้น (Stars) ห้ามโชว์ตัวเลข
import { useState } from 'react'
import { useDispatchQueue, useTrips } from '../api/hooks'
import { useAuth } from '../auth/AuthContext'
import { Btn, Stars, STATUS, DIFFICULTY, inputCls } from '../components/ui'
import AssignModal from '../components/AssignModal'
import TripDetailModal from '../components/TripDetailModal'
import ApprovalCenter, { pendingReceipts } from '../components/ApprovalCenter'
import MaintenanceReportsPanel from '../components/MaintenanceReportsPanel'

// 3 กลุ่มสถานะ — โชว์ "คนขับทุกคน" ครบทุกกลุ่มเสมอ (เห็นภาพรวมทั้งกองรถในจอเดียว)
// แต่แยกคอลัมน์ + แถบสีหัวกลุ่มชัดๆ เพื่อให้กวาดตาอ่านง่าย ไม่ปนกัน
const GROUPS = [
  { key: 'white',  st: 'WHITE',  hint: 'ว่าง พร้อมรับงาน (เรียงคิวให้แล้ว)',
    head: 'bg-slate-100 ring-slate-300 text-slate-600', body: 'bg-slate-50/60 ring-slate-200' },
  { key: 'orange', st: 'ORANGE', hint: 'จ่ายงานแล้ว กำลังไปขึ้นของ',
    head: 'bg-orange-100 ring-orange-300 text-orange-700', body: 'bg-orange-50/50 ring-orange-200' },
  { key: 'green',  st: 'GREEN',  hint: 'ขึ้นของแล้ว กำลังวิ่งไปส่ง',
    head: 'bg-emerald-100 ring-emerald-300 text-emerald-700', body: 'bg-emerald-50/50 ring-emerald-200' },
]

function DriverCard({ d, showRank, rank, onOpen }) {
  // เที่ยวหลักที่ยังไม่จบ — มีค่าแม้คนขับพักเป็น "รองาน" ระหว่างขา (คนคุมงานต้องเห็น)
  const tripId = d.active_trip_id || d.main_trip_id
  const tripCode = d.active_trip_code || d.main_trip_code
  const hasTrip = !!tripId
  const waitingNextLeg = !d.active_trip_id && !!d.main_trip_id
  return (
    <div className="rounded-xl bg-white ring-1 ring-slate-200 p-3.5 shadow-sm fadein">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            {showRank && <span className="text-[10px] font-bold text-slate-400 bg-slate-100 rounded px-1.5 py-0.5">#{rank}</span>}
            {/* คลิกชื่อ → เปิดรายละเอียดทริปปัจจุบัน (เฉพาะคนที่ติดงานอยู่) */}
            {hasTrip ? (
              <button onClick={() => onOpen(tripId)}
                className="font-bold text-blue-600 hover:text-blue-700 hover:underline text-sm truncate text-left">
                {d.name}
              </button>
            ) : (
              <span className="font-bold text-slate-800 text-sm truncate">{d.name}</span>
            )}
          </div>
          <div className="text-[11px] text-slate-400">
            {d.emp_id}{hasTrip && <span className="text-slate-500"> · 🚛 {tripCode} · {d.plate || 'ยังไม่ผูกทะเบียน'}</span>}
          </div>
          {/* ความคืบหน้ารายขาในเที่ยวนี้ + เตือนว่าคนขับรอคนคุมงานจ่ายขาถัดไป */}
          {hasTrip && (
            <div className="mt-1 flex items-center gap-1.5 flex-wrap">
              <span className="text-[10px] font-semibold text-slate-600 bg-slate-100 rounded px-1.5 py-0.5">
                วิ่งแล้ว {d.legs_done}/{d.legs_total} ขา
              </span>
              {waitingNextLeg && (
                <span className="text-[10px] font-semibold text-amber-700 bg-amber-100 rounded px-1.5 py-0.5">
                  รอจ่ายขาถัดไป
                </span>
              )}
            </div>
          )}
        </div>
        {/* คะแนน = ดาวเท่านั้น */}
        <Stars value={d.rating} />
      </div>
      {/* metric ที่ใช้เรียงลำดับ (เฉพาะกลุ่มรองาน) */}
      {showRank && (d.prev_difficulty || d.prev_load_seconds != null) && (
        <div className="flex items-center gap-2 mt-2 flex-wrap">
          {d.prev_difficulty && (
            <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${DIFFICULTY[d.prev_difficulty].cls}`}>
              ทริปก่อน: {DIFFICULTY[d.prev_difficulty].th}
            </span>
          )}
          {d.prev_load_seconds != null && (
            <span className="text-[10px] text-slate-400">⏱ ขึ้นของ {Math.round(d.prev_load_seconds / 60)} นาที</span>
          )}
        </div>
      )}
    </div>
  )
}

export default function DispatchPage() {
  const { user } = useAuth()
  const [q, setQ] = useState('')
  const { data, isLoading, error } = useDispatchQueue(q)
  const { data: trips } = useTrips()
  const [showAssign, setShowAssign] = useState(false)
  const [detailId, setDetailId] = useState(null)
  const [showApproval, setShowApproval] = useState(false)
  const [toast, setToast] = useState(null)
  const notify = (msg, kind = 'green') => { setToast({ msg, kind }); setTimeout(() => setToast(null), 3500) }

  const drafts = pendingReceipts(trips || [])
  const isSuperAdmin = user.role === 'SUPER_ADMIN'

  return (
    <div className="space-y-5">
      {/* ---- Search + ปุ่มจ่ายงาน ---- */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="relative flex-1">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">🔍</span>
          <input className={`${inputCls} pl-9`} value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="ค้นหาชื่อคนขับ หรือ เลขทะเบียนรถ…" />
          {q && (
            <button onClick={() => setQ('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">×</button>
          )}
        </div>
        <div className="flex gap-2">
          <Btn color="ghost" onClick={() => setShowApproval((v) => !v)}>
            ✅ ศูนย์อนุมัติ{drafts.length ? ` (${drafts.length})` : ''}
          </Btn>
          <Btn color="orange" onClick={() => setShowAssign(true)}>＋ จ่ายงานใหม่</Btn>
        </div>
      </div>

      <p className="text-xs text-slate-400">
        กลุ่ม “รองาน” เรียงลำดับให้แล้ว: วิ่งงานหนักมาก่อน → กดขึ้นของไวก่อน → ดาวมากก่อน · คลิกชื่อคนขับที่ติดงานเพื่อดูรายละเอียดทริป
      </p>

      {/* รถที่คนขับแจ้งเหตุ/กำลังซ่อม — ล็อกจ่ายงาน จนกว่าจะปิดเหตุ */}
      <MaintenanceReportsPanel />

      {showApproval && (
        <div className="bg-white rounded-xl ring-1 ring-slate-200 shadow-sm p-4">
          <ApprovalCenter trips={trips || []} isSuperAdmin={isSuperAdmin} onDone={notify} onErr={(m) => notify(m, 'red')} />
        </div>
      )}

      {isLoading ? (
        <div className="text-sm text-slate-400">กำลังโหลดคิวจ่ายงาน…</div>
      ) : error ? (
        <div className="text-sm text-red-500">โหลดข้อมูลไม่สำเร็จ — ตรวจสอบว่า Backend รันอยู่</div>
      ) : (
        <>
          {/* แถบสรุปหัวหน้า: คนขับทั้งกองรถกี่คน แยกตามสถานะกี่คน */}
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="font-bold text-slate-600">
              👥 คนขับทั้งหมด {GROUPS.reduce((n, g) => n + (data[g.key] || []).length, 0)} คน
            </span>
            {GROUPS.map(({ key, st }) => (
              <span key={key} className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-semibold ring-1 ${STATUS[st].ring} ${STATUS[st].text} bg-white`}>
                <span className={`w-2 h-2 rounded-full ${STATUS[st].dot}`}></span>
                {STATUS[st].th} {(data[key] || []).length}
              </span>
            ))}
          </div>

          <div className="grid md:grid-cols-3 gap-4">
            {GROUPS.map(({ key, st, hint, head, body }) => {
              const s = STATUS[st]
              const list = data[key] || []
              return (
                <section key={key} className={`rounded-2xl ring-1 ${body} p-2.5 space-y-2`}>
                  {/* หัวกลุ่มแถบสี — แยกสายตาชัดว่าคนขับก้อนนี้อยู่สถานะไหน */}
                  <header className={`rounded-xl ring-1 ${head} px-3 py-2`}>
                    <div className="flex items-center gap-2 text-sm font-bold">
                      <span className={`w-2.5 h-2.5 rounded-full ${s.dot}`}></span>
                      {s.th}
                      <span className="ml-auto rounded-full bg-white/70 px-2 py-0.5 text-xs">{list.length} คน</span>
                    </div>
                    <div className="text-[10px] font-medium opacity-70 mt-0.5">{hint}</div>
                  </header>
                  {!list.length && (
                    <div className="text-xs text-slate-300 text-center py-4 border border-dashed border-slate-200 rounded-xl bg-white/50">
                      {q ? '— ไม่พบผลลัพธ์ —' : '— ไม่มีคนขับในกลุ่มนี้ —'}
                    </div>
                  )}
                  {list.map((d, i) => (
                    <DriverCard key={d.id} d={d} showRank={key === 'white'} rank={i + 1} onOpen={setDetailId} />
                  ))}
                </section>
              )
            })}
          </div>
        </>
      )}

      {showAssign && <AssignModal onClose={() => setShowAssign(false)} onDone={notify} />}
      {detailId && (
        <TripDetailModal tripId={detailId} isSuperAdmin={isSuperAdmin}
          onClose={() => setDetailId(null)} onDone={notify} />
      )}
      {toast && (
        <div className={`fixed bottom-5 right-5 z-50 text-sm text-white px-4 py-2.5 rounded-xl shadow-lg fadein ${toast.kind === 'red' ? 'bg-red-500' : 'bg-slate-800'}`}>
          {toast.msg}
        </div>
      )}
    </div>
  )
}
