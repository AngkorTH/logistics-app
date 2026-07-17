// หน้าคลังรถยนต์ (Vehicle Assignment) — Admin+ เท่านั้น
// แสดงรายการรถ + คนขับที่รับผิดชอบ · เพิ่มรถใหม่ · ผูก/ถอดคนขับประจำรถ
import { useState } from 'react'
import { useVehiclesAdmin, useCreateVehicle, useAssignVehicle, useDrivers } from '../api/hooks'
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

export default function VehiclesPage() {
  const { data: vehicles, isLoading, error } = useVehiclesAdmin()
  const { data: drivers } = useDrivers()
  const assign = useAssignVehicle()
  const [add, setAdd] = useState(false)
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
            <div>
              {v.status === 'MAINTENANCE' ? (
                <span className="text-[11px] font-bold text-amber-700 bg-amber-100 rounded-full px-2 py-0.5">🔧 กำลังซ่อม</span>
              ) : (
                <span className="text-[11px] font-bold text-emerald-700 bg-emerald-100 rounded-full px-2 py-0.5">✅ พร้อมใช้งาน</span>
              )}
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
      {toast && <div className="fixed bottom-5 right-5 z-50 text-sm text-white px-4 py-2.5 rounded-xl shadow-lg fadein bg-slate-800">{toast}</div>}
    </div>
  )
}
