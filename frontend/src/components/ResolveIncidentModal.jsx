// Modal ปิดเหตุ / ปลดล็อกทริป (Supervisor+) — แทน window.prompt เดิมที่ถูกบล็อกใน
// embedded/sandboxed browser หลายตัว (คืน null ทันที ทำให้ปุ่ม "กดไม่ติด")
// ทำหน้าที่เป็น Confirmation Modal ก่อนปลดล็อกทริป + ช่องบันทึกหมายเหตุ (ไม่บังคับ)
import { useState } from 'react'
import { useResolveIncident } from '../api/hooks'
import { errMsg } from '../api/client'
import { Btn, Field, Modal, inputCls } from './ui'

const KIND_TH = { BREAKDOWN: '🔧 รถเสีย/ขัดข้อง', ACCIDENT: '💥 อุบัติเหตุ', OTHER: '❓ อื่นๆ' }

export default function ResolveIncidentModal({ incident, driverLabel, onClose, onDone, onErr }) {
  const [note, setNote] = useState('')
  const [err, setErr] = useState('')
  const resolve = useResolveIncident()

  const submit = async () => {
    setErr('')
    try {
      await resolve.mutateAsync({ id: incident.id, note: note.trim() })
      onDone?.(`✅ ปิดเหตุ ${incident.code} แล้ว — ทริปกลับมาวิ่งต่อได้`)
      onClose()
    } catch (e) {
      const m = errMsg(e)
      setErr(m)
      onErr?.(m)
    }
  }

  return (
    <Modal title={`✅ ปิดเหตุ / ปลดล็อกทริป ${incident.code}`} onClose={onClose}>
      <div className="rounded-lg bg-amber-50 text-amber-700 text-xs px-3 py-2 mb-3">
        ⚠️ ยืนยันปิดเหตุ <b>{KIND_TH[incident.kind] || incident.kind}</b> ของ {driverLabel} (ทริป #{incident.trip_id})?
        <br />เมื่อไม่มีเหตุอื่นค้าง <b>ทริปจะถูกปลดล็อก</b> ให้คนขับทำรายการต่อได้ทันที
      </div>
      <Field label="บันทึกการปิดเหตุ (ไม่บังคับ)">
        <input className={inputCls} value={note} autoFocus onChange={(e) => setNote(e.target.value)}
          placeholder="เช่น เปลี่ยนยางแล้ว วิ่งต่อได้" />
      </Field>
      {err && <div className="text-xs text-red-500 mb-3">{err}</div>}
      <div className="flex gap-2">
        <Btn color="outline" className="flex-1" onClick={onClose}>ยกเลิก</Btn>
        <Btn color="red" className="flex-1" disabled={resolve.isPending} onClick={submit}>
          ยืนยันปิดเหตุ / ปลดล็อก
        </Btn>
      </div>
    </Modal>
  )
}
