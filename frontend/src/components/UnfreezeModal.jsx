// Modal ปลดล็อกการเงิน (Supervisor/Admin) — ทริปที่ freeze แล้วดูได้อย่างเดียว
// จนกว่าจะปลดล็อก · บังคับเหตุผล · ปลดสำเร็จระบบเด้งแจ้งเตือนให้ทีมรู้
import { useState } from 'react'
import { useUnfreeze } from '../api/hooks'
import { errMsg } from '../api/client'
import { Btn, Field, Modal, inputCls } from './ui'

export default function UnfreezeModal({ trip, onClose, onDone }) {
  const [reason, setReason] = useState('')
  const [err, setErr] = useState('')
  const unfreeze = useUnfreeze()

  const submit = async () => {
    setErr('')
    try {
      await unfreeze.mutateAsync({ tripId: trip.id, reason: reason.trim() })
      onDone?.(`🔓 ปลดล็อก ${trip.code} แล้ว — แก้ไขได้ · ระบบแจ้งเตือนทีมแล้ว`)
      onClose()
    } catch (e) {
      setErr(errMsg(e))
    }
  }

  return (
    <Modal title={`🔓 ปลดล็อกการเงิน ${trip.code}`} onClose={onClose}>
      <div className="rounded-lg bg-amber-50 text-amber-700 text-xs px-3 py-2 mb-3">
        ⚠️ ทริปนี้ถูกล็อกการเงินไว้ (ดูได้อย่างเดียว) — การปลดล็อกเพื่อแก้ไขจะถูกบันทึกและ<b>เด้งแจ้งเตือน</b>ให้ทีมทราบ
      </div>
      <Field label="เหตุผลในการปลดล็อก (บังคับ)">
        <input className={inputCls} value={reason} autoFocus onChange={(e) => setReason(e.target.value)}
          placeholder="เช่น ยอดบิลน้ำมันผิด ต้องแก้ไข" />
      </Field>
      {err && <div className="text-xs text-red-500 mb-3">{err}</div>}
      <div className="flex gap-2">
        <Btn color="outline" className="flex-1" onClick={onClose}>ยกเลิก</Btn>
        <Btn color="red" className="flex-1" disabled={!reason.trim() || unfreeze.isPending} onClick={submit}>
          ยืนยันปลดล็อก
        </Btn>
      </div>
    </Modal>
  )
}
