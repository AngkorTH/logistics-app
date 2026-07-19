// เพิ่มงานย่อย (Sub-Trip) เข้าไปใน "ทริปเดิมที่ยัง Active" — Supervisor+
// Dynamic Multi-Drop: บังคับกรอก "เริ่มจากไหน (Origin)" + "ไปส่งที่ไหน (Destination)" เสมอ
// เที่ยวหลักจะยังไม่จบจนกว่า Supervisor จะกดปุ่ม "จบเที่ยว"
import { useState } from 'react'
import { useAddDrop, useAssign } from '../api/hooks'
import { errMsg } from '../api/client'
import { Btn, Field, Modal, inputCls, money, DIFFICULTY, calcAllowance } from './ui'

export default function AddDropModal({ trip, onClose, onDone }) {
  const addDrop = useAddDrop()
  const assign = useAssign()
  const [origin, setOrigin] = useState('')
  const [destination, setDestination] = useState('')
  const [revenue, setRevenue] = useState('')
  const [difficulty, setDifficulty] = useState(trip.difficulty || 'MEDIUM')
  const [err, setErr] = useState('')
  const busy = addDrop.isPending || assign.isPending

  const submit = async () => {
    if (!origin.trim()) return setErr('กรอก "เริ่มจากไหน" ก่อน')
    if (!destination.trim()) return setErr('กรอก "ไปส่งที่ไหน" ก่อน')
    if (!(Number(revenue) > 0)) return setErr('กรอก "รายได้ต่อขา" (ต้องมากกว่า 0)')
    setErr('')
    try {
      await addDrop.mutateAsync({
        tripId: trip.id,
        origin: origin.trim(),
        destination: destination.trim(),
        revenue: Number(revenue),
        difficulty,
      })
      // คนขับพักเป็น "รองาน" อยู่ → ต้องจ่ายงานซ้ำเพื่อดันกลับเป็น 🟠 ไม่งั้นคนขับไม่เห็นขาใหม่
      if (trip.status === 'WHITE') {
        await assign.mutateAsync({ tripId: trip.id, difficulty: trip.difficulty, force: true })
      }
      onDone?.(`🚦 จ่ายงานย่อยถัดไปให้ ${trip.code} แล้ว · ${origin.trim()} → ${destination.trim()}`)
      onClose()
    } catch (e) {
      setErr(errMsg(e, 'จ่ายงานย่อยไม่สำเร็จ'))
    }
  }

  return (
    <Modal title={`🚦 จ่ายงานย่อยถัดไป · ${trip.code}`} onClose={onClose}>
      <div className="text-[11px] text-slate-400 mb-3">
        งานย่อยใบใหม่ = ขาที่ {trip.drops.length + 1} ของเที่ยวนี้ · จ่ายแล้วคนขับจะเห็นเป็น
        “งานล่าสุด” ทันที (สถานะ 🟠) · เที่ยวหลักยัง Active จนกว่าจะกด “จบเที่ยว”
      </div>
      <Field label="เริ่มจากไหน (Origin) — บังคับ">
        <input className={inputCls} value={origin} onChange={(e) => setOrigin(e.target.value)}
          placeholder="เช่น ลำปาง" />
      </Field>
      <Field label="ไปส่งที่ไหน (Destination) — บังคับ">
        <input className={inputCls} value={destination} onChange={(e) => setDestination(e.target.value)}
          placeholder="เช่น กรุงเทพ" />
      </Field>
      <Field label="รายได้ต่อขา (Revenue) — บังคับ" hint="ฐานคิดเบี้ยเลี้ยงของขานี้">
        <input className={inputCls} type="number" min="0" value={revenue}
          onChange={(e) => setRevenue(e.target.value)} placeholder="เช่น 12000" />
      </Field>
      <Field label="ความยากของขานี้" hint="ง่าย 5% · ปานกลาง 7% · ยาก 10% ของรายได้ต่อขา">
        <div className="grid grid-cols-3 gap-2">
          {Object.values(DIFFICULTY).map((x) => (
            <button key={x.key} type="button" onClick={() => setDifficulty(x.key)}
              className={`rounded-lg py-2 text-sm font-medium ring-1 transition-colors ${
                difficulty === x.key ? `${x.cls} ring-transparent` : 'bg-white text-slate-500 ring-slate-300 hover:bg-slate-50'}`}>
              {x.th} <span className="opacity-70">{(x.rate * 100).toFixed(0)}%</span>
            </button>
          ))}
        </div>
      </Field>
      {/* เบี้ยเลี้ยงคิดสดทันทีจากรายได้ × เปอร์เซ็นต์ความยาก */}
      <div className="mb-3 rounded-md bg-emerald-50 ring-1 ring-emerald-200 px-3 py-2 text-sm">
        <span className="text-emerald-700 font-semibold">
          💰 เบี้ยเลี้ยงขานี้ {Number(revenue) > 0 ? money(calcAllowance(revenue, difficulty)) : '—'}
        </span>
        <span className="text-[11px] text-slate-500 ml-2">
          {Number(revenue) > 0
            ? `${money(Number(revenue))} × ${(DIFFICULTY[difficulty].rate * 100).toFixed(0)}% (${DIFFICULTY[difficulty].th})`
            : 'กรอกรายได้ต่อขาเพื่อดูยอด'}
        </span>
      </div>

      {err && <div className="text-xs text-red-500 mb-2">{err}</div>}
      <div className="flex gap-2 mt-2">
        <Btn color="outline" className="flex-1" onClick={onClose}>ยกเลิก</Btn>
        <Btn color="orange" className="flex-1" disabled={busy} onClick={submit}>
          {busy ? 'กำลังจ่ายงาน…' : '🚦 จ่ายงานย่อยนี้'}
        </Btn>
      </div>
    </Modal>
  )
}
