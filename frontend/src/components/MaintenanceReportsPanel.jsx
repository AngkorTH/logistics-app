// 🔧 รายการแจ้งเหตุ/รถมีปัญหา (จากคนขับตอนรองาน) — แสดงให้คุมงาน/แอดมิน
// แต่ละรายการ: ทะเบียนรถ + รายละเอียด + รูปหลักฐาน + ปุ่มปิดเหตุ (ปลดล็อกรถกลับมาจ่ายงานได้)
import { useState } from 'react'
import { useMaintenanceReports, useResolveMaintenance } from '../api/hooks'
import { errMsg } from '../api/client'
import { ImageLightbox, PhotoThumb } from './ui'

export default function MaintenanceReportsPanel({ compact = false }) {
  const { data: reports, isLoading } = useMaintenanceReports('OPEN')
  const resolve = useResolveMaintenance()
  const [zoom, setZoom] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [err, setErr] = useState('')

  if (isLoading) return null
  const open = reports || []
  if (!open.length) return null

  const doResolve = async (id) => {
    setBusyId(id); setErr('')
    try { await resolve.mutateAsync({ id, note: '' }) }
    catch (e) { setErr(errMsg(e)) }
    finally { setBusyId(null) }
  }

  return (
    <div className="rounded-2xl bg-amber-50 ring-1 ring-amber-300 p-4 space-y-3">
      <div className="font-bold text-amber-800 flex items-center gap-2">
        🔧 รถแจ้งเหตุ/กำลังซ่อม
        <span className="text-xs bg-amber-500 text-white rounded-full px-2 py-0.5">{open.length}</span>
      </div>
      <div className="text-xs text-amber-700 -mt-1">
        รถเหล่านี้ถูกล็อก จ่ายงานไม่ได้จนกว่าจะกด "ปิดเหตุ / พร้อมใช้งาน"
      </div>
      <div className={`grid gap-2 ${compact ? '' : 'sm:grid-cols-2'}`}>
        {open.map((r) => (
          <div key={r.id} className="bg-white rounded-xl ring-1 ring-amber-200 p-3 flex gap-3">
            <PhotoThumb src={r.photo} label="หลักฐาน" onZoom={setZoom} size="w-16 h-16" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span className="font-bold text-slate-800 text-sm">🚛 {r.plate || 'ยังไม่ผูกรถ'}</span>
                <span className="text-[10px] text-slate-400">{r.code}</span>
              </div>
              <div className="text-xs text-slate-600 mt-0.5 break-words">{r.message || '—'}</div>
              <button onClick={() => doResolve(r.id)} disabled={busyId === r.id}
                className="mt-2 w-full py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-bold active:scale-[0.98] transition disabled:opacity-50">
                {busyId === r.id ? '⏳ กำลังปิด…' : '✅ ปิดเหตุ / พร้อมใช้งาน'}
              </button>
            </div>
          </div>
        ))}
      </div>
      {err && <div className="text-xs text-red-500">{err}</div>}
      <ImageLightbox image={zoom} onClose={() => setZoom(null)} />
    </div>
  )
}
