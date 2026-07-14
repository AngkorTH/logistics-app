// Dashboard (Supervisor/Admin/Super Admin) — สรุปภาพรวมอย่างเดียว (Overview Stats)
// ตาม claude.md ข้อ 6.1: เหลือเฉพาะ Stat Cards 4 ใบ — ไม่มีตารางคุมรถ ไม่มีตารางหักเงิน
// (การจัดคิว/จ่ายงาน/อนุมัติบิล ย้ายไปหน้า "จัดการคิวงาน" · หักเงินไปหน้า "ประวัติการหักเงิน")
import { useTrips, useDispatchQueue } from '../api/hooks'
import { Stat } from '../components/ui'
import { pendingReceipts } from '../components/ApprovalCenter'

export default function Dashboard() {
  const { data: trips, isLoading, error } = useTrips()
  const { data: queue } = useDispatchQueue()

  if (isLoading) return <div className="text-sm text-slate-400">กำลังโหลดข้อมูล…</div>
  if (error) return <div className="text-sm text-red-500">โหลดข้อมูลไม่สำเร็จ — ตรวจสอบว่า Backend รันอยู่</div>

  const drafts = pendingReceipts(trips || [])

  return (
    <div className="space-y-5">
      <p className="text-xs text-slate-400">ภาพรวมสถานะทีมคนขับแบบเรียลไทม์</p>

      {/* ---- Stat Cards 4 ใบ: รองาน / ขึ้นของ / ส่งของ / รอเช็กสลิป ---- */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="รองาน (White)" value={queue?.white?.length ?? '—'} dot="bg-slate-400" sub="สถานะขาว · พร้อมรับงาน" />
        <Stat label="กำลังขึ้นของ (Orange)" value={queue?.orange?.length ?? '—'} dot="bg-orange-500" accent="text-orange-600" sub="สถานะส้ม · ไปขึ้นของ" />
        <Stat label="กำลังส่งของ (Green)" value={queue?.green?.length ?? '—'} dot="bg-emerald-500" accent="text-emerald-600" sub="สถานะเขียว · กำลังส่ง" />
        <Stat label="รอเช็กสลิป" value={drafts.length} dot="bg-amber-400" accent={drafts.length ? 'text-amber-600' : undefined} sub="บิล OCR รออนุมัติ" />
      </div>
    </div>
  )
}
