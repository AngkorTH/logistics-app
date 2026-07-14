// หน้าจัดการพนักงาน (User Management) — Admin+ เท่านั้น
// ตารางรายชื่อ + ปุ่ม Edit (แก้ชื่อ/เบอร์/สถานะ) · คนขับให้ดาวได้ (0-5)
import { useState } from 'react'
import { useUsers, useUpdateUser, useRateDriver } from '../api/hooks'
import { errMsg } from '../api/client'
import { Btn, Field, Modal, Stars, ROLES, inputCls } from '../components/ui'

function EditModal({ u, onClose, onDone }) {
  const update = useUpdateUser()
  const rate = useRateDriver()
  const [name, setName] = useState(u.name)
  const [phone, setPhone] = useState(u.phone)
  const [active, setActive] = useState(u.active)
  const [rating, setRating] = useState(u.rating)
  const [err, setErr] = useState('')
  const isDriver = u.role === 'DRIVER'

  const save = async () => {
    setErr('')
    try {
      await update.mutateAsync({ id: u.id, name, phone, active })
      if (isDriver && rating !== u.rating) await rate.mutateAsync({ id: u.id, rating })
      onDone(`บันทึกข้อมูล ${u.emp_id} แล้ว`)
      onClose()
    } catch (e) { setErr(errMsg(e, 'บันทึกไม่สำเร็จ')) }
  }

  return (
    <Modal title={`✏️ แก้ข้อมูล ${u.emp_id}`} onClose={onClose}>
      <Field label="ชื่อ-สกุล"><input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} /></Field>
      <Field label="เบอร์โทร"><input className={inputCls} value={phone} onChange={(e) => setPhone(e.target.value)} /></Field>
      <Field label="สถานะบัญชี">
        <select className={inputCls} value={active ? '1' : '0'} onChange={(e) => setActive(e.target.value === '1')}>
          <option value="1">ใช้งานอยู่</option>
          <option value="0">ระงับการใช้งาน</option>
        </select>
      </Field>
      {isDriver && (
        <Field label="คะแนนดาว">
          <div className="flex items-center gap-2">
            {[0, 1, 2, 3, 4, 5].map((n) => (
              <button key={n} type="button" onClick={() => setRating(n)}
                className={`px-2 py-1 rounded ${rating === n ? 'bg-amber-100 ring-1 ring-amber-400' : 'hover:bg-slate-100'}`}>
                {n === 0 ? '—' : <Stars value={n} size={14} />}
              </button>
            ))}
          </div>
        </Field>
      )}
      {err && <div className="text-xs text-red-500 mt-2">{err}</div>}
      <div className="flex gap-2 mt-4">
        <Btn color="outline" className="flex-1" onClick={onClose}>ยกเลิก</Btn>
        <Btn color="blue" className="flex-1" onClick={save} disabled={update.isPending || rate.isPending}>บันทึก</Btn>
      </div>
    </Modal>
  )
}

export default function UsersPage() {
  const { data: users, isLoading, error } = useUsers()
  const [edit, setEdit] = useState(null)
  const [toast, setToast] = useState(null)
  const notify = (msg) => { setToast(msg); setTimeout(() => setToast(null), 3000) }

  if (isLoading) return <div className="text-sm text-slate-400">กำลังโหลด…</div>
  if (error) return <div className="text-sm text-red-500">โหลดข้อมูลไม่สำเร็จ</div>

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl ring-1 ring-slate-200 shadow-sm overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]">
          <thead className="bg-slate-50 text-slate-500 text-xs">
            <tr>
              <th className="text-left px-4 py-3">รหัส</th>
              <th className="text-left px-4 py-3">ชื่อ-สกุล</th>
              <th className="text-left px-4 py-3">เบอร์โทร</th>
              <th className="text-left px-4 py-3">ตำแหน่ง</th>
              <th className="text-left px-4 py-3">ดาว</th>
              <th className="text-left px-4 py-3">สถานะ</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {users.map((u) => (
              <tr key={u.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-medium text-slate-700">{u.emp_id}</td>
                <td className="px-4 py-3 text-slate-700">{u.name}</td>
                <td className="px-4 py-3 text-slate-500">{u.phone}</td>
                <td className="px-4 py-3 text-slate-500">{ROLES[u.role].icon} {ROLES[u.role].th}</td>
                <td className="px-4 py-3">{u.role === 'DRIVER' ? <Stars value={u.rating} size={14} /> : <span className="text-slate-300">—</span>}</td>
                <td className="px-4 py-3">
                  {u.active
                    ? <span className="text-xs text-emerald-600 bg-emerald-50 rounded-full px-2 py-0.5">ใช้งาน</span>
                    : <span className="text-xs text-red-500 bg-red-50 rounded-full px-2 py-0.5">ระงับ</span>}
                </td>
                <td className="px-4 py-3 text-right">
                  <Btn size="sm" color="ghost" onClick={() => setEdit(u)}>แก้ไข</Btn>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {edit && <EditModal u={edit} onClose={() => setEdit(null)} onDone={notify} />}
      {toast && <div className="fixed bottom-5 right-5 z-50 text-sm text-white px-4 py-2.5 rounded-xl shadow-lg fadein bg-slate-800">{toast}</div>}
    </div>
  )
}
