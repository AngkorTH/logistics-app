// คิวอนุมัติ (Phase 3C) — Supervisor/Admin/Super Admin
// 3 หมวดในหน้าเดียว: 🚨 เหตุฉุกเฉิน SOS (ปิดเหตุ) · 🔧 ตรวจสภาพรถรอประเมิน (อนุมัติ/ไม่อนุมัติ)
// · 💵 คำขอเบิกเงินล่วงหน้า (อนุมัติ/ปฏิเสธ — ยอดจะถูกหักอัตโนมัติตอนปิดทริป)
import { useState } from 'react'
import {
  useIncidents, useResolveIncident,
  usePendingInspections, useReviewInspection,
  useAdvances, useDecideAdvance,
  useDrivers,
} from '../api/hooks'
import { errMsg } from '../api/client'
import { Btn, ImageLightbox, PhotoThumb, money } from '../components/ui'
import { CHECK_ITEMS } from '../components/DriverSheets'

const KIND_TH = { BREAKDOWN: '🔧 รถเสีย/ขัดข้อง', ACCIDENT: '💥 อุบัติเหตุ', OTHER: '❓ อื่นๆ' }
const CHECK_TH = Object.fromEntries(CHECK_ITEMS.map((c) => [c.key, c.label]))

export default function ApprovalsPage() {
  const { data: incidents } = useIncidents('OPEN')
  const { data: inspections } = usePendingInspections()
  const { data: advances } = useAdvances()
  const { data: drivers } = useDrivers()
  const resolveIncident = useResolveIncident()
  const reviewInspection = useReviewInspection()
  const decideAdvance = useDecideAdvance()
  const [toast, setToast] = useState('')
  const [zoom, setZoom] = useState(null)  // Phase 4: ขยายดูรูปเต็มจอ

  const notify = (msg) => { setToast(msg); setTimeout(() => setToast(''), 3500) }
  const driverName = (id) => {
    const d = (drivers || []).find((x) => x.id === id)
    return d ? `${d.emp_id} · ${d.name}` : `#${id}`
  }
  const run = async (fn, okMsg) => {
    try { await fn(); notify(okMsg) } catch (e) { notify(`❌ ${errMsg(e)}`) }
  }

  const pendingAdvances = (advances || []).filter((a) => a.status === 'PENDING')

  return (
    <div className="space-y-6">
      {/* ---------- 🚨 เหตุฉุกเฉิน (SOS) ---------- */}
      <section>
        <h2 className="font-bold text-slate-800 mb-2">🚨 เหตุฉุกเฉิน (SOS) ที่ยังเปิดอยู่</h2>
        {(incidents || []).length === 0 && <Empty text="ไม่มีเหตุฉุกเฉินค้าง" />}
        {(incidents || []).map((inc) => (
          <div key={inc.id} className="bg-red-50 ring-2 ring-red-300 rounded-2xl p-4 mb-2 flex flex-wrap items-center gap-3">
            <div className="flex-1 min-w-[220px]">
              <div className="font-bold text-red-700">{KIND_TH[inc.kind] || inc.kind} <span className="text-slate-400 font-normal text-sm">· {inc.code} · ทริป #{inc.trip_id}</span></div>
              <div className="text-sm text-slate-700 mt-0.5">{driverName(inc.driver_id)} — {inc.message || 'ไม่มีรายละเอียด'}</div>
              <div className="text-[11px] text-slate-500 mt-0.5">
                {inc.gps && <>🛰 พิกัด {inc.gps} · </>}
                แจ้งเมื่อ {new Date(inc.created_at).toLocaleString('th-TH')} · ทริปถูกพักอยู่
              </div>
              <div className="mt-1.5"><PhotoThumb src={inc.photo} label={`รูปหน้างาน ${inc.code}`} onZoom={setZoom} size="w-16 h-16" /></div>
            </div>
            <Btn color="red" disabled={resolveIncident.isPending}
              onClick={() => {
                const note = window.prompt('บันทึกการปิดเหตุ (เช่น เปลี่ยนยางแล้ว วิ่งต่อได้):', '')
                if (note === null) return
                run(() => resolveIncident.mutateAsync({ id: inc.id, note }),
                  `✅ ปิดเหตุ ${inc.code} แล้ว — ทริปกลับมาวิ่งต่อได้`)
              }}>
              ✅ ปิดเหตุ / ปลดล็อกทริป
            </Btn>
          </div>
        ))}
      </section>

      {/* ---------- 🔧 ตรวจสภาพรถรอประเมิน ---------- */}
      <section>
        <h2 className="font-bold text-slate-800 mb-2">🔧 ตรวจสภาพรถ — จุดชำรุดรอประเมิน</h2>
        {(inspections || []).length === 0 && <Empty text="ไม่มีรายการรอประเมิน" />}
        {(inspections || []).map((ins) => {
          let failed = []
          try { failed = Object.entries(JSON.parse(ins.items)).filter(([, v]) => !v).map(([k]) => CHECK_TH[k] || k) } catch { /* items เพี้ยน — โชว์ดิบ */ }
          return (
            <div key={ins.id} className="bg-white ring-1 ring-amber-300 rounded-2xl p-4 mb-2 flex flex-wrap items-center gap-3">
              <div className="flex-1 min-w-[220px]">
                <div className="font-bold text-slate-800">{driverName(ins.driver_id)} <span className="text-slate-400 font-normal text-sm">· ทริป #{ins.trip_id}</span></div>
                <div className="text-sm text-red-600 mt-0.5">❌ ชำรุด: {failed.join(', ') || ins.items}</div>
                {ins.defect_note && <div className="text-xs text-slate-500 mt-0.5">📝 {ins.defect_note}</div>}
                <div className="text-[11px] text-slate-400 mt-0.5">ส่งเมื่อ {new Date(ins.created_at).toLocaleString('th-TH')}</div>
                <div className="mt-1.5"><PhotoThumb src={ins.defect_photo} label="รูปจุดชำรุด" onZoom={setZoom} size="w-16 h-16" /></div>
              </div>
              <div className="flex gap-2">
                <Btn color="outline" disabled={reviewInspection.isPending}
                  onClick={() => run(() => reviewInspection.mutateAsync({ id: ins.id, approve: false, note: 'รถต้องซ่อมก่อน' }),
                    '🚫 ไม่อนุมัติ — คนขับต้องแก้ไขแล้วตรวจใหม่')}>
                  🚫 ไม่อนุมัติ
                </Btn>
                <Btn color="green" disabled={reviewInspection.isPending}
                  onClick={() => run(() => reviewInspection.mutateAsync({ id: ins.id, approve: true, note: '' }),
                    '✅ อนุมัติแล้ว — ปุ่มเริ่มงานของคนขับปลดล็อกทันที')}>
                  ✅ อนุมัติให้วิ่งได้
                </Btn>
              </div>
            </div>
          )
        })}
      </section>

      {/* ---------- 💵 คำขอเบิกเงินล่วงหน้า ---------- */}
      <section>
        <h2 className="font-bold text-slate-800 mb-2">💵 คำขอเบิกเงินล่วงหน้า — รออนุมัติ</h2>
        {pendingAdvances.length === 0 && <Empty text="ไม่มีคำขอค้าง" />}
        {pendingAdvances.map((a) => (
          <div key={a.id} className="bg-white ring-1 ring-blue-200 rounded-2xl p-4 mb-2 flex flex-wrap items-center gap-3">
            <div className="flex-1 min-w-[220px]">
              <div className="font-bold text-slate-800">{money(a.amount)} <span className="text-slate-400 font-normal text-sm">· {a.code} · {driverName(a.driver_id)}</span></div>
              <div className="text-sm text-slate-600 mt-0.5">📝 {a.reason}</div>
              <div className="text-[11px] text-slate-400 mt-0.5">
                ขอเมื่อ {new Date(a.requested_at).toLocaleString('th-TH')}
                {a.trip_id && <> · ระหว่างทริป #{a.trip_id}</>} · อนุมัติแล้วจะถูกหักจากยอดจ่ายสุทธิตอนปิดทริปอัตโนมัติ
              </div>
            </div>
            <div className="flex gap-2">
              <Btn color="outline" disabled={decideAdvance.isPending}
                onClick={() => run(() => decideAdvance.mutateAsync({ id: a.id, approve: false }),
                  `🚫 ปฏิเสธคำขอ ${a.code} แล้ว`)}>
                🚫 ปฏิเสธ
              </Btn>
              <Btn color="blue" disabled={decideAdvance.isPending}
                onClick={() => run(() => decideAdvance.mutateAsync({ id: a.id, approve: true }),
                  `✅ อนุมัติ ${money(a.amount)} — จะถูกหักตอนปิดทริปอัตโนมัติ`)}>
                ✅ อนุมัติ
              </Btn>
            </div>
          </div>
        ))}
      </section>

      <ImageLightbox image={zoom} onClose={() => setZoom(null)} />
      {toast && (
        <div className="fixed bottom-6 inset-x-4 md:inset-x-auto md:right-6 md:w-96 z-50 bg-slate-800 text-white text-sm px-4 py-3 rounded-xl shadow-lg text-center fadein">
          {toast}
        </div>
      )}
    </div>
  )
}

function Empty({ text }) {
  return <div className="text-sm text-slate-400 bg-white rounded-xl ring-1 ring-slate-200 px-4 py-3">{text}</div>
}
