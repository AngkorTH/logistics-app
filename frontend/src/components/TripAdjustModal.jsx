// Modal แก้ไขข้อมูลทริป (Supervisor/Admin) — ระยะทาง / ความยาก / โบนัส / หักเงิน / เบี้ยเลี้ยงรายจุด
// 🚨 กฎเหล็ก: กด "บันทึก" แล้ว "ห้ามยิง API ทันที" — เด้ง Alert บังคับพิมพ์ "เหตุผลที่แก้ไข" ก่อน
//            ถ้าไม่พิมพ์เหตุผล ปุ่มยืนยันจะถูก disable · ส่ง edit_reason ไปกับ PATCH /trips/{id}/adjust
import { useState } from 'react'
import { useAdjustTrip } from '../api/hooks'
import { errMsg } from '../api/client'
import { Btn, Field, Modal, inputCls, money, DIFFICULTY } from './ui'

export default function TripAdjustModal({ trip, onClose, onDone }) {
  // ค่าตั้งต้น = ค่าปัจจุบันของทริป
  const [distance, setDistance] = useState(String(trip.distance_km ?? ''))
  const [difficulty, setDifficulty] = useState(trip.difficulty)
  const [bonus, setBonus] = useState(String(trip.bonus ?? ''))
  const [penalty, setPenalty] = useState(String(trip.penalty ?? ''))
  const [penaltyReason, setPenaltyReason] = useState(trip.penalty_reason || '')
  const [allowances, setAllowances] = useState(
    Object.fromEntries(trip.drops.map((d) => [d.id, String(d.allowance)])),
  )

  // stage 2: Alert บังคับเหตุผลการแก้ไข
  const [confirming, setConfirming] = useState(false)
  const [editReason, setEditReason] = useState('')
  const [err, setErr] = useState('')

  const adjust = useAdjustTrip()

  // รวมเฉพาะ field ที่ "เปลี่ยนไปจากเดิม" เพื่อส่งไป backend
  const buildChanges = () => {
    const body = {}
    if (Number(distance) !== trip.distance_km) body.distance_km = Number(distance)
    if (difficulty !== trip.difficulty) body.difficulty = difficulty
    if (Number(bonus) !== trip.bonus) body.bonus = Number(bonus)
    if (Number(penalty) !== trip.penalty) {
      body.penalty = Number(penalty)
      body.penalty_reason = penaltyReason
    }
    const changedAllow = {}
    trip.drops.forEach((d) => {
      const v = Number(allowances[d.id])
      if (v !== d.allowance) changedAllow[d.id] = v
    })
    if (Object.keys(changedAllow).length) body.allowances = changedAllow
    return body
  }

  const changes = buildChanges()
  const hasChanges = Object.keys(changes).length > 0

  const submit = async () => {
    setErr('')
    try {
      await adjust.mutateAsync({ tripId: trip.id, edit_reason: editReason.trim(), ...changes })
      onDone?.(`✏️ แก้ไขทริป ${trip.code} สำเร็จ (บันทึกเหตุผลลง Audit แล้ว)`)
      onClose()
    } catch (e) {
      setErr(errMsg(e))
    }
  }

  // ---------- Stage 2: Alert Modal บังคับเหตุผล ----------
  if (confirming) {
    return (
      <Modal title="⚠️ ยืนยันการแก้ไขข้อมูลทริป" onClose={() => setConfirming(false)}>
        <p className="text-sm text-slate-600 mb-3">
          กรุณาพิมพ์ <b>เหตุผลในการแก้ไขข้อมูลทริปในครั้งนี้</b> — ระบบจะบันทึกลง Audit Trail ถาวร
        </p>
        <Field label="เหตุผลที่แก้ไข (Edit Reason) — บังคับ">
          <textarea className={`${inputCls} h-24 resize-none`} value={editReason} autoFocus
            onChange={(e) => setEditReason(e.target.value)}
            placeholder="เช่น ลูกค้าแจ้งระยะทางคลาดเคลื่อน / ปรับยอดหักตามหลักฐานเพิ่มเติม" />
        </Field>
        {err && <div className="text-xs text-red-500 mb-3">{err}</div>}
        <div className="flex gap-2">
          <Btn color="outline" className="flex-1" onClick={() => setConfirming(false)}>ย้อนกลับ</Btn>
          <Btn color="red" className="flex-1" disabled={!editReason.trim() || adjust.isPending}
            onClick={submit}>
            ยืนยันบันทึกการแก้ไข
          </Btn>
        </div>
      </Modal>
    )
  }

  // ---------- Stage 1: ฟอร์มแก้ไข ----------
  return (
    <Modal title={`✏️ แก้ไขข้อมูลทริป ${trip.code}`} onClose={onClose} wide>
      <div className="grid grid-cols-2 gap-3">
        <Field label="ระยะทาง (กม.)">
          <input className={inputCls} type="number" min="0" value={distance} onChange={(e) => setDistance(e.target.value)} />
        </Field>
        <Field label="ความยากทริป">
          <select className={inputCls} value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
            {Object.values(DIFFICULTY).map((d) => <option key={d.key} value={d.key}>{d.th}</option>)}
          </select>
        </Field>
        <Field label="โบนัสทริป (บาท)">
          <input className={inputCls} type="number" min="0" value={bonus} onChange={(e) => setBonus(e.target.value)} />
        </Field>
        <Field label="ยอดหักเงิน (บาท)">
          <input className={inputCls} type="number" min="0" value={penalty} onChange={(e) => setPenalty(e.target.value)} />
        </Field>
      </div>
      {Number(penalty) !== trip.penalty && (
        <Field label="เหตุผลการหักเงิน (บังคับเมื่อแก้ยอดหัก)">
          <input className={inputCls} value={penaltyReason} onChange={(e) => setPenaltyReason(e.target.value)}
            placeholder="เช่น ส่งช้า / ไม่คลุมผ้าใบ" />
        </Field>
      )}

      <div className="mt-2 mb-3">
        <div className="text-xs font-medium text-slate-600 mb-1">เบี้ยเลี้ยงรายจุด</div>
        <div className="space-y-2">
          {trip.drops.map((d) => (
            <div key={d.id} className="flex items-center gap-2">
              <span className="text-xs text-slate-500 flex-1 truncate">จุด {d.seq}: {d.origin || '—'} ➜ {d.destination || d.name} <span className="text-slate-300">(เดิม {money(d.allowance)})</span></span>
              <input className={`${inputCls} w-28`} type="number" min="0" value={allowances[d.id]}
                onChange={(e) => setAllowances({ ...allowances, [d.id]: e.target.value })} />
            </div>
          ))}
        </div>
      </div>

      {err && <div className="text-xs text-red-500 mb-3">{err}</div>}

      <div className="flex gap-2">
        <Btn color="outline" className="flex-1" onClick={onClose}>ยกเลิก</Btn>
        {/* กด "บันทึก" → ไม่ยิง API ทันที แต่ไปหน้ายืนยัน (บังคับเหตุผล) */}
        <Btn color="orange" className="flex-1" disabled={!hasChanges}
          onClick={() => { setErr(''); setConfirming(true) }}>
          💾 บันทึก
        </Btn>
      </div>
      {!hasChanges && <p className="text-[10px] text-slate-400 text-center mt-2">— ยังไม่มีการเปลี่ยนแปลงข้อมูล —</p>}
    </Modal>
  )
}
