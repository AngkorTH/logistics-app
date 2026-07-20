// หน้าคลังรถยนต์ (Vehicle Assignment) — Admin+ เท่านั้น
// แสดงรายการรถ + คนขับที่รับผิดชอบ · เพิ่มรถใหม่ · ผูก/ถอดคนขับประจำรถ
import { useState } from 'react'
import { useVehiclesAdmin, useCreateVehicle, useAssignVehicle, useDrivers, useSetVehicleStatus } from '../api/hooks'
import { errMsg } from '../api/client'
import { Btn, Field, Modal, inputCls } from '../components/ui'
import MaintenanceReportsPanel from '../components/MaintenanceReportsPanel'

function AddModal({ onClose, onDone }) {
  const create = useCreateVehicle()
  const [plate, setPlate] = useState('')
  const [model, setModel] = useState('')
  const [err, setErr] = useState('')
  const save = async () => {
    if (!plate.trim()) return setErr('กรอกทะเบียนรถ')
    setErr('')
    try { await create.mutateAsync({ plate, model, std_km_l: 3.5 }); onDone(`เพิ่มรถ ${plate} แล้ว`); onClose() }
    catch (e) { setErr(errMsg(e, 'เพิ่มรถไม่สำเร็จ')) }
  }
  return (
    <Modal title="🚙 เพิ่มทะเบียนรถ" onClose={onClose}>
      <Field label="ทะเบียนรถ"><input className={inputCls} value={plate} onChange={(e) => setPlate(e.target.value)} placeholder="เช่น 1กก1234" /></Field>
      <Field label="รุ่นรถ"><input className={inputCls} value={model} onChange={(e) => setModel(e.target.value)} placeholder="เช่น ISUZU" /></Field>
      {err && <div className="text-xs text-red-500 mt-2">{err}</div>}
      <div className="flex gap-2 mt-4">
        <Btn color="outline" className="flex-1" onClick={onClose}>ยกเลิก</Btn>
        <Btn color="blue" className="flex-1" onClick={save} disabled={create.isPending}>บันทึก</Btn>
      </div>
    </Modal>
  )
}

/* 🔧 แอดมินสั่งรถเข้าซ่อม / ปลดล็อกกลับมาใช้งาน — บังคับกรอกเหตุผล (ลง Audit + แจ้งเตือน) */
function StatusModal({ vehicle, onClose, onDone }) {
  const setStatus = useSetVehicleStatus()
  const [reason, setReason] = useState('')
  const [err, setErr] = useState('')
  const toRepair = vehicle.status !== 'MAINTENANCE'
  const next = toRepair ? 'MAINTENANCE' : 'AVAILABLE'

  const save = async () => {
    if (!reason.trim()) return setErr('ต้องกรอกเหตุผลเสมอ')
    setErr('')
    try {
      await setStatus.mutateAsync({ id: vehicle.id, status: next, reason: reason.trim() })
      onDone(toRepair ? `🔧 ตั้งรถ ${vehicle.plate} เป็น "กำลังซ่อม" แล้ว — จ่ายงานไม่ได้จนกว่าจะปลดล็อก`
                      : `✅ ปลดล็อกรถ ${vehicle.plate} กลับมาใช้งานได้แล้ว`)
      onClose()
    } catch (e) { setErr(errMsg(e, 'เปลี่ยนสถานะรถไม่สำเร็จ')) }
  }

  return (
    <Modal title={toRepair ? `🔧 แจ้งรถเข้าซ่อม — ${vehicle.plate}` : `✅ ปลดล็อกรถ — ${vehicle.plate}`} onClose={onClose}>
      <div className={`rounded-lg text-xs px-3 py-2 mb-3 ${toRepair ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-700'}`}>
        {toRepair
          ? '⚠️ รถที่อยู่สถานะ "กำลังซ่อม" จะถูกล็อกไม่ให้จ่ายงาน จนกว่าจะปลดล็อก'
          : 'รถจะกลับมาพร้อมใช้งาน และจ่ายงานได้ตามปกติ'}
      </div>
      <Field label="เหตุผล (บังคับ — บันทึกลง Audit Log)">
        <input className={inputCls} value={reason} autoFocus onChange={(e) => setReason(e.target.value)}
          placeholder={toRepair ? 'เช่น เข้าศูนย์เปลี่ยนยาง' : 'เช่น ซ่อมเสร็จแล้ว ตรวจสภาพผ่าน'} />
      </Field>
      {err && <div className="text-xs text-red-500 mt-2">{err}</div>}
      <div className="flex gap-2 mt-4">
        <Btn color="outline" className="flex-1" onClick={onClose}>ยกเลิก</Btn>
        <Btn color={toRepair ? 'orange' : 'green'} className="flex-1" onClick={save} disabled={setStatus.isPending}>
          {toRepair ? 'ยืนยันเข้าซ่อม' : 'ยืนยันปลดล็อก'}
        </Btn>
      </div>
    </Modal>
  )
}

export default function VehiclesPage() {
  const { data: vehicles, isLoading, error } = useVehiclesAdmin()
  const { data: drivers } = useDrivers()
  const assign = useAssignVehicle()
  const [add, setAdd] = useState(false)
  const [statusTarget, setStatusTarget] = useState(null)  // รถที่กำลังจะเปลี่ยนสถานะซ่อม
  const [toast, setToast] = useState(null)
  const notify = (msg) => { setToast(msg); setTimeout(() => setToast(null), 3000) }

  const driverName = (id) => (drivers || []).find((d) => d.id === id)?.name

  if (isLoading) return <div className="text-sm text-slate-400">กำลังโหลด…</div>
  if (error) return <div className="text-sm text-red-500">โหลดข้อมูลไม่สำเร็จ</div>

  const onAssign = async (id, driver_id) => {
    try { await assign.mutateAsync({ id, driver_id: driver_id ? Number(driver_id) : null }); notify('อัปเดตคนขับประจำรถแล้ว') }
    catch { notify('อัปเดตไม่สำเร็จ') }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Btn color="blue" onClick={() => setAdd(true)}>＋ เพิ่มรถ</Btn>
      </div>

      {/* รถที่คนขับแจ้งเหตุ/กำลังซ่อม + ปุ่มปิดเหตุ (ปลดล็อกรถ) */}
      <MaintenanceReportsPanel />

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {vehicles.map((v) => (
          <div key={v.id} className={`bg-white rounded-xl ring-1 shadow-sm p-4 space-y-2 ${
            v.status === 'MAINTENANCE' ? 'ring-amber-300' : 'ring-slate-200'}`}>
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-800">🚛 {v.plate}</span>
              <span className="text-xs text-slate-400">{v.model || '—'}</span>
            </div>
            <div className="flex items-center gap-2">
              {v.status === 'MAINTENANCE' ? (
                <span className="text-[11px] font-bold text-amber-700 bg-amber-100 rounded-full px-2 py-0.5">🔧 กำลังซ่อม</span>
              ) : (
                <span className="text-[11px] font-bold text-emerald-700 bg-emerald-100 rounded-full px-2 py-0.5">✅ พร้อมใช้งาน</span>
              )}
              {/* ปุ่มนี้อยู่ในหน้า Admin+ เท่านั้น (route /vehicles) และ backend บังคับ require_admin ซ้ำอีกชั้น */}
              <Btn size="sm" color={v.status === 'MAINTENANCE' ? 'green' : 'ghost'}
                className="ml-auto" onClick={() => setStatusTarget(v)}>
                {v.status === 'MAINTENANCE' ? '✅ ปลดล็อกรถ' : '🔧 แจ้งเข้าซ่อม'}
              </Btn>
            </div>
            <div>
              <label className="block text-[10px] text-slate-400 mb-1">คนขับประจำรถ</label>
              <select className={inputCls} value={v.driver_id || ''} onChange={(e) => onAssign(v.id, e.target.value)}>
                <option value="">— ยังไม่ผูกคนขับ —</option>
                {(drivers || []).map((d) => <option key={d.id} value={d.id}>{d.emp_id} · {d.name}</option>)}
              </select>
              {v.driver_id && <div className="text-[11px] text-emerald-600 mt-1">ประจำการ: {driverName(v.driver_id) || `#${v.driver_id}`}</div>}
            </div>
          </div>
        ))}
        {!vehicles.length && <div className="text-sm text-slate-300">ยังไม่มีรถในคลัง</div>}
      </div>

      {add && <AddModal onClose={() => setAdd(false)} onDone={notify} />}
      {statusTarget && (
        <StatusModal vehicle={statusTarget} onClose={() => setStatusTarget(null)} onDone={notify} />
      )}
      {toast && <div className="fixed bottom-5 right-5 z-50 text-sm text-white px-4 py-2.5 rounded-xl shadow-lg fadein bg-slate-800">{toast}</div>}
    </div>
  )
}
