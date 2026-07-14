// Modal เปลี่ยนสถานะทริปแบบ Manual (Supervisor/Admin) — task 1
// ยืนยันก่อนเปลี่ยน + บังคับกรอกเหตุผล · สำเร็จแล้ว backend แจ้งเตือนคนขับ (stub push)
import { useState } from 'react'
import { useOverrideStatus } from '../api/hooks'
import { errMsg } from '../api/client'
import { Btn, Field, Modal, inputCls, STATUS } from './ui'

const OPTIONS = ['WHITE', 'ORANGE', 'GREEN']

export default function StatusOverrideModal({ trip, onClose, onDone, onErr }) {
  const [status, setStatus] = useState(trip.status)
  const [reason, setReason] = useState('')
  const [err, setErr] = useState('')
  const override = useOverrideStatus()

  const changed = status !== trip.status
  const canSubmit = changed && reason.trim()

  const submit = async () => {
    setErr('')
    try {
      await override.mutateAsync({ tripId: trip.id, status, reason: reason.trim() })
      onDone?.(`🔧 เปลี่ยนสถานะ ${trip.code} → ${STATUS[status].th} · แจ้งเตือนคนขับแล้ว`)
      onClose()
    } catch (e) {
      const m = errMsg(e); setErr(m); onErr?.(m)
    }
  }

  return (
    <Modal title={`🔧 เปลี่ยนสถานะงาน ${trip.code}`} onClose={onClose}>
      <div className="rounded-lg bg-amber-50 text-amber-700 text-xs px-3 py-2 mb-3">
        ⚠️ ยืนยันเปลี่ยนสถานะงานของคนขับแบบ Manual — ระบบจะแจ้งเตือนคนขับและบันทึกลง Audit Log
      </div>

      <Field label="สถานะใหม่">
        <div className="grid grid-cols-3 gap-2">
          {OPTIONS.map((st) => (
            <button key={st} onClick={() => setStatus(st)}
              className={`rounded-lg py-2 text-xs font-semibold ring-1 ${status === st ? `${STATUS[st].ring} ${STATUS[st].text} bg-white` : 'ring-slate-200 text-slate-400'}`}>
              <span className={`inline-block w-2 h-2 rounded-full mr-1 ${STATUS[st].dot}`}></span>{STATUS[st].th}
            </button>
          ))}
        </div>
      </Field>

      <Field label="เหตุผลในการเปลี่ยนสถานะ (บังคับ)">
        <input className={inputCls} value={reason} onChange={(e) => setReason(e.target.value)}
          placeholder="เช่น คนขับลืมกดขนของขึ้นเสร็จ" />
      </Field>

      {err && <div className="text-xs text-red-500 mb-3">{err}</div>}

      <div className="flex gap-2">
        <Btn color="outline" className="flex-1" onClick={onClose}>ยกเลิก</Btn>
        <Btn color="orange" className="flex-1" disabled={!canSubmit || override.isPending} onClick={submit}>
          ยืนยันเปลี่ยนสถานะ
        </Btn>
      </div>
    </Modal>
  )
}
