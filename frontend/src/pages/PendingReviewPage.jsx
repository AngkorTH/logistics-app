// แท็บ "รอตรวจ" (ข้อ 2.2) — Supervisor/Admin/Super Admin
// ทริปที่คนขับส่งงานจบแล้ว (มีหลักฐานครบ) รอตรวจ+ยืนยันความถูกต้อง เรียง "เก่า→ใหม่"
// คลิกดูทริป → TripDetailModal (เห็นภาพหลักฐาน/บิลทั้งหมด) · กดยืนยัน = ล็อกการเงิน
// → ทริปย้ายเข้า "ประวัติทริป" อัตโนมัติ
import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { usePendingReview, useDrivers, useCloseTrip } from '../api/hooks'
import { errMsg } from '../api/client'
import { Btn, money } from '../components/ui'
import TripDetailModal from '../components/TripDetailModal'
import { useAuth } from '../auth/AuthContext'

export default function PendingReviewPage() {
  const { user } = useAuth()
  const qc = useQueryClient()
  const { data: trips, isLoading } = usePendingReview()
  const { data: drivers } = useDrivers()
  const closeTrip = useCloseTrip()
  const [detailId, setDetailId] = useState(null)
  const [toast, setToast] = useState('')

  const driverName = (id) => {
    const d = (drivers || []).find((x) => x.id === id)
    return d ? `${d.emp_id} · ${d.name}` : `#${id}`
  }
  const notify = (msg) => { setToast(msg); setTimeout(() => setToast(''), 3500) }

  const confirm = async (trip, force = false) => {
    try {
      await closeTrip.mutateAsync({ tripId: trip.id, force })
      qc.invalidateQueries({ queryKey: ['pending-review'] })
      notify(`✅ ยืนยัน ${trip.code} แล้ว — ล็อกการเงินและย้ายเข้าประวัติทริป`)
    } catch (e) {
      // 409 = รูปหลักฐานยังไม่ครบ → popup ยืนยัน (warn-don't-block)
      if (e.response?.status === 409 && window.confirm(`${errMsg(e)}\n\nยืนยันปิดทริปนี้หรือไม่?`)) {
        return confirm(trip, true)
      }
      notify(`❌ ${errMsg(e)}`)
    }
  }

  if (isLoading) return <div className="text-center text-slate-400 py-16">กำลังโหลด…</div>

  return (
    <div className="space-y-3">
      <div className="text-sm text-slate-500">
        ทริปที่คนขับส่งงานเสร็จแล้ว รอตรวจหลักฐานและยืนยันความถูกต้อง — เรียงจาก <b>เก่าไปใหม่</b>
      </div>

      {(trips || []).length === 0 && (
        <div className="text-center text-slate-400 py-16">
          <div className="text-5xl mb-3">🗒️</div>ไม่มีทริปรอตรวจ — เคลียร์หมดแล้ว 🎉
        </div>
      )}

      {(trips || []).map((t) => {
        const photos = t.drops.filter((d) => d.photo).length
        const receipts = t.drops.reduce((n, d) => n + d.receipts.length, 0)
        const draft = t.drops.reduce((n, d) => n + d.receipts.filter((r) => !r.approved).length, 0)
        const allowance = t.drops.reduce((s, d) => s + d.allowance, 0)
        return (
          <div key={t.id} className="bg-white rounded-2xl ring-1 ring-slate-200 shadow-sm p-4 flex flex-wrap items-center gap-3">
            <div className="flex-1 min-w-[220px]">
              <div className="font-bold text-slate-800">{t.code} <span className="font-normal text-slate-400 text-sm">· {driverName(t.driver_id)}</span></div>
              <div className="text-xs text-slate-500 mt-0.5">
                🚛 {t.plate || '—'} · 📦 {t.drops.length} จุด · 📸 รูปส่งของ {photos}/{t.drops.length}
                · 🧾 บิล {receipts} ใบ{draft > 0 && <span className="text-amber-600 font-semibold"> (draft รออนุมัติ {draft})</span>}
                · เบี้ยเลี้ยง {money(allowance)}
              </div>
              <div className="text-[11px] text-slate-400 mt-0.5">
                จบงานเมื่อ {t.closed_at ? new Date(t.closed_at).toLocaleString('th-TH') : '—'}
              </div>
            </div>
            <div className="flex gap-2">
              <Btn color="outline" onClick={() => setDetailId(t.id)}>🔍 ดูหลักฐานทั้งหมด</Btn>
              <Btn color="green" disabled={closeTrip.isPending} onClick={() => confirm(t)}>
                ✅ ยืนยันถูกต้อง → เข้าประวัติ
              </Btn>
            </div>
          </div>
        )
      })}

      {detailId && (
        <TripDetailModal tripId={detailId} isSuperAdmin={user.role === 'SUPER_ADMIN'}
          onClose={() => { setDetailId(null); qc.invalidateQueries({ queryKey: ['pending-review'] }) }}
          onDone={notify} />
      )}
      {toast && (
        <div className="fixed bottom-6 inset-x-4 md:inset-x-auto md:right-6 md:w-96 z-50 bg-slate-800 text-white text-sm px-4 py-3 rounded-xl shadow-lg text-center fadein">
          {toast}
        </div>
      )}
    </div>
  )
}
