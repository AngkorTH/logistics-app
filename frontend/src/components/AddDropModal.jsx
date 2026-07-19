// เพิ่มงานย่อย (Sub-Trip) เข้าไปใน "ทริปเดิมที่ยัง Active" — Supervisor+
// Dynamic Multi-Drop: บังคับกรอก "เริ่มจากไหน (Origin)" + "ไปส่งที่ไหน (Destination)" เสมอ
// เที่ยวหลักจะยังไม่จบจนกว่า Supervisor จะกดปุ่ม "จบเที่ยว"
import { useState } from 'react'
import { useAddDrop } from '../api/hooks'
import { errMsg } from '../api/client'
import { Btn, Field, Modal, inputCls } from './ui'

export default function AddDropModal({ trip, onClose, onDone }) {
  const addDrop = useAddDrop()
  const [origin, setOrigin] = useState('')
  const [destination, setDestination] = useState('')
  const [allowance, setAllowance] = useState(300)
  const [err, setErr] = useState('')

  const submit = async () => {
    if (!origin.trim()) return setErr('กรอก "เริ่มจากไหน" ก่อน')
    if (!destination.trim()) return setErr('กรอก "ไปส่งที่ไหน" ก่อน')
    setErr('')
    try {
      await addDrop.mutateAsync({
        tripId: trip.id,
        origin: origin.trim(),
        destination: destination.trim(),
        allowance: Number(allowance) || 0,
      })
      onDone?.(`➕ เพิ่มงานย่อยเข้าทริป ${trip.code} แล้ว · ${origin.trim()} → ${destination.trim()}`)
      onClose()
    } catch (e) {
      setErr(errMsg(e, 'เพิ่มงานย่อยไม่สำเร็จ'))
    }
  }

  return (
    <Modal title={`➕ เพิ่มงานย่อยเข้า ${trip.code}`} onClose={onClose}>
      <div className="text-[11px] text-slate-400 mb-3">
        งานย่อยใบใหม่จะต่อท้ายเป็นจุดที่ {trip.drops.length + 1} ของเที่ยวนี้ ·
        เที่ยวหลักยัง Active จนกว่าจะกด “จบเที่ยว”
      </div>
      <Field label="เริ่มจากไหน (Origin) — บังคับ">
        <input className={inputCls} value={origin} onChange={(e) => setOrigin(e.target.value)}
          placeholder="เช่น ลำปาง" />
      </Field>
      <Field label="ไปส่งที่ไหน (Destination) — บังคับ">
        <input className={inputCls} value={destination} onChange={(e) => setDestination(e.target.value)}
          placeholder="เช่น กรุงเทพ" />
      </Field>
      <Field label="เบี้ยเลี้ยงงานย่อยนี้ (บาท)">
        <input className={inputCls} type="number" min="0" value={allowance}
          onChange={(e) => setAllowance(e.target.value)} />
      </Field>

      {err && <div className="text-xs text-red-500 mb-2">{err}</div>}
      <div className="flex gap-2 mt-2">
        <Btn color="outline" className="flex-1" onClick={onClose}>ยกเลิก</Btn>
        <Btn color="orange" className="flex-1" disabled={addDrop.isPending} onClick={submit}>
          {addDrop.isPending ? 'กำลังเพิ่ม…' : '➕ เพิ่มงานย่อย'}
        </Btn>
      </div>
    </Modal>
  )
}
