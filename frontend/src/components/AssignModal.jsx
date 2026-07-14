// ฟอร์มจ่ายงาน (Supervisor) — เลือกคนขับ + จุดส่ง Multi-Drop 1-5 จุด
// ข้อ 2.1: ไม่มีช่องเลือกทะเบียนรถแล้ว — ระบบดึงจากคลังรถยนต์ที่ผูกกับคนขับอัตโนมัติ
// ขั้นตอน: POST /trips (สร้างทริป+จุดส่ง) → POST /trips/{id}/assign (→ ORANGE)
import { useState } from 'react'
import { useDrivers, useVehicles, useCreateTrip, useAssign } from '../api/hooks'
import { errMsg } from '../api/client'
import { Btn, Field, Modal, inputCls, DIFFICULTY } from './ui'

const emptyDrop = () => ({ name: '', allowance: 300 })

export default function AssignModal({ onClose, onDone }) {
  const { data: drivers } = useDrivers()
  const { data: vehicles } = useVehicles()
  const createTrip = useCreateTrip()
  const assign = useAssign()

  const [driverId, setDriverId] = useState('')
  const [difficulty, setDifficulty] = useState('')  // บังคับ Supervisor เลือกก่อนจ่ายงาน
  const [distance, setDistance] = useState(100)
  const [drops, setDrops] = useState([emptyDrop()])
  const [err, setErr] = useState('')
  const busy = createTrip.isPending || assign.isPending

  const setDrop = (i, patch) => setDrops((ds) => ds.map((d, j) => (j === i ? { ...d, ...patch } : d)))

  const submit = async () => {
    if (!driverId) return setErr('เลือกพนักงานขับรถ')
    if (!difficulty) return setErr('เลือกความยากของทริป')
    if (drops.some((d) => !d.name.trim())) return setErr('กรอกชื่อจุดส่งให้ครบทุกจุด')
    setErr('')
    try {
      const { data: trip } = await createTrip.mutateAsync({
        driver_id: Number(driverId), distance_km: Number(distance) || 0,
        drops: drops.map((d) => ({ name: d.name, allowance: Number(d.allowance) || 0 })),
      })
      const { data: assigned } = await assign.mutateAsync({ tripId: trip.id, difficulty })
      onDone?.(`🔔 จ่ายงาน ${trip.code} แล้ว → สีส้ม · ทะเบียน ${assigned.plate} (ดึงจากคลังรถอัตโนมัติ)`)
      onClose()
    } catch (e) {
      setErr(errMsg(e, 'จ่ายงานไม่สำเร็จ'))
    }
  }

  return (
    <Modal title="🚦 จ่ายงานใหม่" onClose={onClose} wide>
      <Field label="พนักงานขับรถ">
        <select className={inputCls} value={driverId} onChange={(e) => setDriverId(e.target.value)}>
          <option value="">— เลือกคนขับ —</option>
          {(drivers || []).map((d) => <option key={d.id} value={d.id}>{d.emp_id} · {d.name}</option>)}
        </select>
      </Field>
      {/* ข้อ 2.1: ไม่มีช่องเลือกทะเบียน — โชว์ทะเบียนที่ระบบจะดึงให้ดูเฉยๆ (read-only) */}
      <div className="mb-3 -mt-1 text-[11px] text-slate-400">
        🚛 ระบบจะดึงทะเบียนรถที่ผูกกับคนขับอัตโนมัติ
        {driverId && (() => {
          const v = (vehicles || []).find((x) => x.driver_id === Number(driverId))
          return v
            ? <span className="text-slate-600 font-semibold"> — {v.plate} ({v.model})</span>
            : <span className="text-red-500 font-semibold"> — คนขับคนนี้ยังไม่ถูกผูกรถ! ไปผูกที่หน้า "คลังรถยนต์" ก่อน</span>
        })()}
      </div>
      <Field label="ความยากของทริป (Difficulty)" hint="ใช้จัดลำดับคิวจ่ายงานครั้งถัดไปของคนขับ">
        <div className="grid grid-cols-3 gap-2">
          {Object.values(DIFFICULTY).map((d) => (
            <button key={d.key} type="button" onClick={() => setDifficulty(d.key)}
              className={`rounded-lg py-2 text-sm font-medium ring-1 transition-colors ${
                difficulty === d.key ? `${d.cls} ring-transparent` : 'bg-white text-slate-500 ring-slate-300 hover:bg-slate-50'}`}>
              {d.th}
            </button>
          ))}
        </div>
      </Field>
      <Field label="ระยะทางประมาณ (กม.)">
        <input className={inputCls} type="number" min="0" value={distance} onChange={(e) => setDistance(e.target.value)} />
      </Field>

      <div className="text-xs font-medium text-slate-600 mb-1">จุดส่งย่อย (Multi-Drop 1-5 จุด)</div>
      <div className="space-y-2 mb-3">
        {drops.map((d, i) => (
          <div key={i} className="flex gap-2 items-center">
            <span className="text-xs text-slate-400 w-4">{i + 1}.</span>
            <input className={inputCls} placeholder="ชื่อจุดส่ง เช่น โลตัส (ลาดพร้าว)" value={d.name}
              onChange={(e) => setDrop(i, { name: e.target.value })} />
            <input className={`${inputCls} !w-24`} type="number" min="0" title="เบี้ยเลี้ยง (บาท)"
              value={d.allowance} onChange={(e) => setDrop(i, { allowance: e.target.value })} />
            {drops.length > 1 && (
              <button className="text-slate-400 hover:text-red-500" onClick={() => setDrops((ds) => ds.filter((_, j) => j !== i))}>✕</button>
            )}
          </div>
        ))}
      </div>
      {drops.length < 5 && (
        <Btn color="ghost" size="sm" onClick={() => setDrops((ds) => [...ds, emptyDrop()])}>＋ เพิ่มจุดส่ง</Btn>
      )}

      {err && <div className="text-xs text-red-500 mt-3">{err}</div>}
      <div className="flex gap-2 mt-4">
        <Btn color="outline" className="flex-1" onClick={onClose}>ยกเลิก</Btn>
        <Btn color="orange" className="flex-1" onClick={submit} disabled={busy}>
          {busy ? 'กำลังจ่ายงาน…' : '🚦 จ่ายงาน → สีส้ม'}
        </Btn>
      </div>
    </Modal>
  )
}
