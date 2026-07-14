// กระดิ่งแจ้งเตือน (กล่องจดหมายบริหาร) — Supervisor+ เท่านั้น
// แสดงจำนวนที่ยังไม่อ่าน + dropdown รายการล่าสุด · คลิกอ่านทีละอัน / อ่านทั้งหมด
import { useState } from 'react'
import { useNotifications, useMarkNotifRead } from '../api/hooks'

const ICON = { BILL_UPLOADED: '🧾', TRIP_DONE: '✅', TRIP_UNFROZEN: '🔓' }

export default function NotificationBell() {
  const [open, setOpen] = useState(false)
  const { data: list } = useNotifications()
  const mark = useMarkNotifRead()
  const items = list || []
  const unread = items.filter((n) => !n.read).length

  return (
    <div className="relative">
      <button onClick={() => setOpen((v) => !v)} className="relative w-9 h-9 rounded-full hover:bg-slate-100 text-lg" title="แจ้งเตือน">
        🔔
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)}></div>
          <div className="absolute right-0 mt-2 w-80 max-h-[70vh] overflow-y-auto bg-white rounded-xl shadow-2xl ring-1 ring-slate-200 z-40 fadein">
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-100 sticky top-0 bg-white">
              <span className="font-bold text-slate-700 text-sm">🔔 กล่องจดหมาย</span>
              {unread > 0 && (
                <button onClick={() => mark.mutate({ all: true })} className="text-[11px] text-blue-600 hover:underline">
                  อ่านทั้งหมด
                </button>
              )}
            </div>
            {!items.length ? (
              <div className="text-xs text-slate-300 text-center py-8">— ไม่มีการแจ้งเตือน —</div>
            ) : (
              <div className="divide-y divide-slate-100">
                {items.map((n) => (
                  <button key={n.id} onClick={() => !n.read && mark.mutate({ id: n.id })}
                    className={`w-full text-left px-4 py-2.5 hover:bg-slate-50 flex gap-2 ${n.read ? 'opacity-60' : ''}`}>
                    <span className="text-lg leading-none mt-0.5">{ICON[n.kind] || '📌'}</span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-1.5">
                        {!n.read && <span className="w-1.5 h-1.5 rounded-full bg-red-500 shrink-0"></span>}
                        <span className="text-xs font-semibold text-slate-700 truncate">{n.title}</span>
                      </span>
                      <span className="block text-[11px] text-slate-500">{n.message}</span>
                      <span className="block text-[10px] text-slate-400 mt-0.5">{new Date(n.at).toLocaleString('th-TH')}</span>
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
