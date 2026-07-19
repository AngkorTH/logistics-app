// ฟอร์มจ่ายงาน (Supervisor) — เลือกคนขับ + งานย่อย (Sub-Trip) 1-5 ใบ
// Dynamic Multi-Drop: ทุกงานย่อยบังคับกรอก "เริ่มจากไหน (Origin)" + "ไปส่งที่ไหน (Destination)"
// ข้อ 2.1: ไม่มีช่องเลือกทะเบียนรถแล้ว — ระบบดึงจากคลังรถยนต์ที่ผูกกับคนขับอัตโนมัติ
// ขั้นตอน: POST /trips (สร้างทริป+จุดส่ง) → POST /trips/{id}/assign (→ ORANGE)
import { useState } from 'react'
import { useAvailableDrivers, useVehicles, useCreateTrip, useAssign, useAddDrop } from '../api/hooks'
import { errMsg } from '../api/client'
import { Btn, Field, Modal, inputCls, DIFFICULTY } from './ui'

// Dynamic Multi-Drop: ทุกงานย่อยบังคับกรอก "เริ่มจากไหน" + "ไปส่งที่ไหน"
const emptyDrop = () => ({ origin: '', destination: '', allowance: 300 })

// ป้ายกำกับคนขับที่ "รองาน" 2 ประเภท (waiting_type จาก backend)
const WAITING = {
  SUB_TRIP: { th: 'ยังไม่จบเที่ยว รองานย่อย', cls: 'bg-amber-100 text-amber-700' },
  NEW_TRIP: { th: 'จบเที่ยวแล้ว รองานใหม่', cls: 'bg-emerald-100 text-emerald-700' },
}

export default function AssignModal({ onClose, onDone }) {
  const { data: drivers, isLoading: loadingDrivers } = useAvailableDrivers()
  const { data: vehicles } = useVehicles()
  const createTrip = useCreateTrip()
  const assign = useAssign()
  const addDrop = useAddDrop()

  const [driverId, setDriverId] = useState('')
  const [difficulty, setDifficulty] = useState('')  // บังคับ Supervisor เลือกก่อนจ่ายงาน
  const [distance, setDistance] = useState(100)
  const [drops, setDrops] = useState([emptyDrop()])
  const [err, setErr] = useState('')
  const busy = createTrip.isPending || assign.isPending || addDrop.isPending

  const setDrop = (i, patch) => setDrops((ds) => ds.map((d, j) => (j === i ? { ...d, ...patch } : d)))

  const list = drivers || []
  const picked = list.find((d) => String(d.id) === String(driverId))
  // แบ่ง 2 กลุ่มตาม waiting_type ที่ backend ส่งมา
  const groups = [
    { key: 'SUB_TRIP', items: list.filter((d) => d.waiting_type === 'SUB_TRIP') },
    { key: 'NEW_TRIP', items: list.filter((d) => d.waiting_type === 'NEW_TRIP') },
  ]

  const submit = async () => {
    if (!driverId) return setErr('เลือกพนักงานขับรถ')
    if (!difficulty) return setErr('เลือกความยากของทริป')
    if (drops.some((d) => !d.origin.trim() || !d.destination.trim()))
      return setErr('กรอก "เริ่มจากไหน" และ "ไปส่งที่ไหน" ให้ครบทุกงานย่อย')
    setErr('')
    const payload = drops.map((d) => ({
      origin: d.origin.trim(), destination: d.destination.trim(),
      allowance: Number(d.allowance) || 0,
    }))
    try {
      // คนขับที่เที่ยวหลักยังไม่จบ → เพิ่มงานย่อยเข้าเที่ยวเดิม (ไม่สร้างเที่ยวใหม่ซ้อน)
      if (picked?.waiting_type === 'SUB_TRIP' && picked.active_trip_id) {
        for (const d of payload) await addDrop.mutateAsync({ tripId: picked.active_trip_id, ...d })
        const { data: assigned } = await assign.mutateAsync({ tripId: picked.active_trip_id, difficulty })
        onDone?.(`➕ เพิ่ม ${payload.length} งานย่อยเข้าเที่ยวเดิม ${picked.active_trip_code} → สีส้ม · ทะเบียน ${assigned.plate}`)
        return onClose()
      }
      const { data: trip } = await createTrip.mutateAsync({
        driver_id: Number(driverId), distance_km: Number(distance) || 0, drops: payload,
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
      <Field label="พนักงานขับรถ" hint="แสดงเฉพาะคนที่ “รองาน” เท่านั้น — คนที่กำลังวิ่งงานอยู่ไม่ถูกส่งมา">
        <select className={inputCls} value={driverId} onChange={(e) => setDriverId(e.target.value)}>
          <option value="">— เลือกคนขับ —</option>
          {groups.map(({ key, items }) => items.length > 0 && (
            <optgroup key={key} label={`${WAITING[key].th} (${items.length})`}>
              {items.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.emp_id} · {d.name}
                  {d.waiting_type === 'SUB_TRIP' ? ` — ${d.active_trip_code} (${d.active_trip_drops} งานย่อย)` : ''}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </Field>
      {!loadingDrivers && list.length === 0 && (
        <div className="-mt-2 mb-3 text-[11px] text-red-500">ไม่มีคนขับที่รองานอยู่ตอนนี้ — ทุกคนกำลังวิ่งงาน</div>
      )}
      {/* ป้ายกำกับประเภทการรองานของคนที่เลือก */}
      {picked && (
        <div className="-mt-2 mb-3 flex items-center gap-2 flex-wrap">
          <span className={`text-[11px] font-semibold px-2 py-0.5 rounded ${WAITING[picked.waiting_type].cls}`}>
            {WAITING[picked.waiting_type].th}
          </span>
          {picked.waiting_type === 'SUB_TRIP' && (
            <span className="text-[11px] text-slate-500">
              งานย่อยที่กรอกด้านล่างจะถูก <b>เพิ่มเข้าเที่ยวเดิม {picked.active_trip_code}</b> (ตอนนี้มี {picked.active_trip_drops} ใบ) ไม่ใช่เที่ยวใหม่
            </span>
          )}
        </div>
      )}
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

      <div className="text-xs font-medium text-slate-600 mb-1">
        งานย่อย (Sub-Trip / Multi-Drop 1-5 ใบ) — บังคับกรอกต้นทางและปลายทางทุกใบ
      </div>
      <div className="space-y-2 mb-3">
        {drops.map((d, i) => (
          <div key={i} className="rounded-lg ring-1 ring-slate-200 p-2.5">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold text-slate-500">งานย่อยที่ {i + 1}</span>
              {drops.length > 1 && (
                <button className="text-slate-400 hover:text-red-500 text-sm"
                  onClick={() => setDrops((ds) => ds.filter((_, j) => j !== i))}>✕</button>
              )}
            </div>
            <div className="flex gap-2 items-center flex-wrap">
              <input className={`${inputCls} flex-1 !min-w-[130px]`} placeholder="เริ่มจากไหน เช่น ลำปาง"
                value={d.origin} onChange={(e) => setDrop(i, { origin: e.target.value })} />
              <span className="text-slate-400 text-sm">➜</span>
              <input className={`${inputCls} flex-1 !min-w-[130px]`} placeholder="ไปส่งที่ไหน เช่น กรุงเทพ"
                value={d.destination} onChange={(e) => setDrop(i, { destination: e.target.value })} />
              <input className={`${inputCls} !w-24`} type="number" min="0" title="เบี้ยเลี้ยง (บาท)"
                value={d.allowance} onChange={(e) => setDrop(i, { allowance: e.target.value })} />
            </div>
          </div>
        ))}
      </div>
      {drops.length < 5 && (
        <Btn color="ghost" size="sm" onClick={() => setDrops((ds) => [...ds, emptyDrop()])}>＋ เพิ่มงานย่อย</Btn>
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
