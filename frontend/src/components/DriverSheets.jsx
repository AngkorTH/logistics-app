// Driver Action Sheets — Mobile-First Bottom Sheet + Checklist ตรวจสภาพรถ (Phase 3A)
// ปุ่มใหญ่ ตัวหนังสือชัด ใช้กลางแดดได้ · ทุกฟอร์มเด้งเป็น Bottom Sheet ไม่เปลี่ยนหน้า
// Phase 4: ถ่ายรูปจริงผ่านกล้อง (pickImage) + thumbnail ยืนยันก่อนส่ง
import { useState } from 'react'
import { pickImage } from '../utils/image'

/* ---------- Bottom Sheet (มือถือเด้งจากล่าง) ---------- */
export function BottomSheet({ title, children, onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-white rounded-t-3xl shadow-2xl w-full max-w-md max-h-[88vh] overflow-y-auto fadein"
        onClick={(e) => e.stopPropagation()}>
        <div className="sticky top-0 bg-white pt-3 pb-2 px-5 border-b border-slate-100 z-10">
          <div className="w-12 h-1.5 bg-slate-200 rounded-full mx-auto mb-3" />
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-slate-800 text-lg">{title}</h3>
            <button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-2xl leading-none px-2">×</button>
          </div>
        </div>
        <div className="p-5 pb-8">{children}</div>
      </div>
    </div>
  )
}

/* ---------- Checklist ตรวจสภาพรถก่อนวิ่ง (ข้อ 1.2) ---------- */
export const CHECK_ITEMS = [
  { key: 'tires', label: '🛞 ลมยาง / สภาพยาง' },
  { key: 'lights', label: '💡 ไฟหน้า / ไฟเลี้ยว / ไฟเบรก' },
  { key: 'brakes', label: '🛑 ระบบเบรก' },
  { key: 'tarp', label: '🎪 สภาพผ้าใบ / อุปกรณ์คลุม' },
  { key: 'fluids', label: '🛢️ น้ำมันเครื่อง / น้ำหล่อเย็น' },
]

export function InspectionCard({ onSubmit, busy }) {
  // เริ่มต้น "ผ่าน" ทุกข้อ (เส้นทางปกติเร็วสุด) — คนขับแตะสลับข้อที่ชำรุดเป็นแดง
  const [items, setItems] = useState(Object.fromEntries(CHECK_ITEMS.map((c) => [c.key, true])))
  const [note, setNote] = useState('')
  const [photo, setPhoto] = useState(null) // Phase 4: dataURL รูปจุดชำรุดจริง
  const hasDefect = Object.values(items).some((v) => !v)

  return (
    <div className="bg-white rounded-2xl ring-2 ring-blue-300 p-4 shadow-sm space-y-3">
      <div className="font-bold text-slate-800 text-base">🔧 ตรวจสภาพรถก่อนวิ่ง (บังคับ)</div>
      <div className="text-xs text-slate-500 -mt-2">แตะรายการที่ "ชำรุด" ให้เป็นสีแดง แล้วกดส่งผลตรวจ</div>

      {CHECK_ITEMS.map((c) => (
        <button key={c.key}
          onClick={() => setItems((s) => ({ ...s, [c.key]: !s[c.key] }))}
          className={`w-full flex items-center justify-between px-4 py-3.5 rounded-xl text-base font-semibold ring-1 active:scale-[0.98] transition ${
            items[c.key]
              ? 'bg-emerald-50 ring-emerald-300 text-emerald-800'
              : 'bg-red-50 ring-red-300 text-red-700'
          }`}>
          <span>{c.label}</span>
          <span className="text-lg">{items[c.key] ? '✅ ผ่าน' : '❌ ชำรุด'}</span>
        </button>
      ))}

      {hasDefect && (
        <div className="space-y-2 bg-red-50 rounded-xl p-3 ring-1 ring-red-200">
          <div className="text-sm font-semibold text-red-700">
            พบจุดชำรุด — ต้องถ่ายรูปแนบส่งให้คนคุมงานประเมิน
          </div>
          <textarea value={note} onChange={(e) => setNote(e.target.value)}
            placeholder="อธิบายจุดชำรุด เช่น ยางหน้าซ้ายแตกลาย…" rows={2}
            className="w-full border border-red-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-red-200" />
          {/* Phase 4: เปิดกล้องถ่ายรูปจริง + โชว์ thumbnail ให้เห็นก่อนส่ง */}
          {photo && <img src={photo} alt="จุดชำรุด" className="w-full max-h-40 object-cover rounded-lg ring-1 ring-red-200" />}
          <button onClick={async () => { const img = await pickImage(); if (img) setPhoto(img) }}
            className={`w-full py-3 rounded-xl text-base font-bold active:scale-[0.98] transition ${
              photo ? 'bg-slate-100 text-slate-500' : 'bg-red-500 hover:bg-red-600 text-white'
            }`}>
            {photo ? '🔄 ถ่ายรูปใหม่' : '📷 ถ่ายรูปจุดชำรุด (บังคับ)'}
          </button>
        </div>
      )}

      <button
        disabled={busy || (hasDefect && !photo)}
        onClick={() => onSubmit({ items, defect_note: note, defect_photo_b64: hasDefect ? photo : null })}
        className="w-full py-4 rounded-2xl bg-blue-500 hover:bg-blue-600 text-white text-lg font-bold shadow active:scale-[0.98] transition disabled:opacity-40 disabled:cursor-not-allowed">
        {busy ? '⏳ กำลังส่งผลตรวจ…' : hasDefect ? '📨 ส่งให้คนคุมงานประเมิน' : '✅ ส่งผลตรวจ — ผ่านทุกข้อ'}
      </button>
    </div>
  )
}

/* ---------- SOS Bottom Sheet (ข้อ 1.4) ---------- */
const SOS_KINDS = [
  { key: 'BREAKDOWN', label: '🔧 รถเสีย / ขัดข้อง' },
  { key: 'ACCIDENT', label: '💥 อุบัติเหตุ' },
  { key: 'OTHER', label: '❓ เหตุอื่นๆ' },
]

export function SosSheet({ onClose, onSubmit, busy }) {
  const [kind, setKind] = useState('BREAKDOWN')
  const [message, setMessage] = useState('')
  const [photo, setPhoto] = useState(null) // Phase 4: dataURL รูปหน้างานจริง

  return (
    <BottomSheet title="🆘 แจ้งเหตุขัดข้อง / อุบัติเหตุ" onClose={onClose}>
      <div className="space-y-3">
        <div className="text-sm text-slate-500">
          ระบบจะส่งพิกัด GPS ปัจจุบันไปให้คนคุมงานทันที และทริปจะถูกพักชั่วคราวจนกว่าจะปิดเหตุ
        </div>
        <div className="grid gap-2">
          {SOS_KINDS.map((k) => (
            <button key={k.key} onClick={() => setKind(k.key)}
              className={`py-3.5 rounded-xl text-base font-bold ring-1 active:scale-[0.98] transition ${
                kind === k.key ? 'bg-red-500 text-white ring-red-500 shadow' : 'bg-white text-slate-700 ring-slate-300'
              }`}>
              {k.label}
            </button>
          ))}
        </div>
        <textarea value={message} onChange={(e) => setMessage(e.target.value)}
          placeholder="เล่าเหตุการณ์สั้นๆ เช่น ยางระเบิดเลนขวา กม.45…" rows={3}
          className="w-full border border-slate-300 rounded-xl px-3 py-2.5 text-base outline-none focus:ring-2 focus:ring-red-200" />
        {photo && <img src={photo} alt="หน้างาน" className="w-full max-h-40 object-cover rounded-lg ring-1 ring-slate-200" />}
        <button onClick={async () => { const img = await pickImage(); if (img) setPhoto(img) }}
          className={`w-full py-3.5 rounded-xl text-base font-bold active:scale-[0.98] transition ${
            photo ? 'bg-slate-100 text-slate-500' : 'bg-white ring-1 ring-slate-300 text-slate-700'
          }`}>
          {photo ? '🔄 ถ่ายรูปใหม่' : '📷 ถ่ายรูปหน้างาน'}
        </button>
        <button disabled={busy}
          onClick={() => onSubmit({ kind, message, photo_b64: photo })}
          className="w-full py-5 rounded-2xl bg-red-600 hover:bg-red-700 text-white text-xl font-extrabold shadow-lg active:scale-[0.98] transition disabled:opacity-50">
          {busy ? '⏳ กำลังส่ง…' : '🚨 ส่งแจ้งเหตุทันที'}
        </button>
      </div>
    </BottomSheet>
  )
}

/* ---------- แจ้งเหตุ/รถมีปัญหา ตอนรองาน (Report Issue) ---------- */
// บังคับกรอก 2 อย่าง: รายละเอียดปัญหา + รูปหลักฐาน · ส่งแล้วรถถูกตั้งเป็น "กำลังซ่อม"
export function ReportIssueSheet({ onClose, onSubmit, busy }) {
  const [message, setMessage] = useState('')
  const [photo, setPhoto] = useState(null) // dataURL รูปหลักฐาน (บังคับ)
  const valid = message.trim().length > 0 && !!photo

  return (
    <BottomSheet title="🔧 แจ้งเหตุ / ตรวจพบปัญหา" onClose={onClose}>
      <div className="space-y-3">
        <div className="rounded-xl bg-amber-50 ring-1 ring-amber-200 text-amber-700 text-sm px-3 py-2.5">
          ⚠️ เมื่อส่งแล้ว รถของคุณจะถูกตั้งเป็น <b>"กำลังซ่อม"</b> อัตโนมัติ —
          คนคุมงานจะจ่ายงานให้ไม่ได้จนกว่าจะปิดเหตุ
        </div>
        <div>
          <label className="block text-sm font-semibold text-slate-600 mb-1">รายละเอียดปัญหา (บังคับ)</label>
          <textarea value={message} onChange={(e) => setMessage(e.target.value)}
            placeholder="เช่น ยางแบนล้อหน้าซ้าย / เครื่องสตาร์ทไม่ติด / น้ำมันเครื่องรั่ว…" rows={3}
            className="w-full border border-slate-300 rounded-xl px-3 py-2.5 text-base outline-none focus:ring-2 focus:ring-amber-200" />
        </div>
        {photo && <img src={photo} alt="หลักฐาน" className="w-full max-h-48 object-cover rounded-lg ring-1 ring-slate-200" />}
        <button onClick={async () => { const img = await pickImage(); if (img) setPhoto(img) }}
          className={`w-full py-3.5 rounded-xl text-base font-bold active:scale-[0.98] transition ${
            photo ? 'bg-slate-100 text-slate-500' : 'bg-white ring-1 ring-slate-300 text-slate-700'
          }`}>
          {photo ? '🔄 ถ่ายรูปใหม่' : '📷 ถ่ายรูปหลักฐาน (บังคับ)'}
        </button>
        <button disabled={busy || !valid}
          onClick={() => onSubmit({ message: message.trim(), photo_b64: photo })}
          className="w-full py-5 rounded-2xl bg-amber-500 hover:bg-amber-600 text-white text-xl font-extrabold shadow-lg active:scale-[0.98] transition disabled:opacity-40 disabled:cursor-not-allowed">
          {busy ? '⏳ กำลังส่ง…' : '📨 ส่งแจ้งเหตุ'}
        </button>
        {!valid && (
          <div className="text-center text-xs text-slate-400">ต้องกรอกรายละเอียด และแนบรูปหลักฐานก่อนส่ง</div>
        )}
      </div>
    </BottomSheet>
  )
}

/* ---------- ยืนยันรูปก่อนส่ง (Phase 4) — thumbnail ให้คนขับเช็กก่อนเข้าคิว/ส่ง ---------- */
export function PhotoConfirmSheet({ draft, onClose, busy }) {
  // draft = { label, dataUrl, confirm() }
  if (!draft) return null
  return (
    <BottomSheet title={`📷 ${draft.label}`} onClose={onClose}>
      <div className="space-y-3">
        <img src={draft.dataUrl} alt={draft.label}
          className="w-full max-h-72 object-contain rounded-xl ring-1 ring-slate-200 bg-slate-50" />
        <div className="text-xs text-slate-400 text-center">
          ตรวจว่ารูปชัดอ่านออก — ถ้าออฟไลน์ ระบบจะเก็บรูปเข้าคิวและส่งเองเมื่อเน็ตกลับ
        </div>
        <button disabled={busy} onClick={draft.confirm}
          className="w-full py-4 rounded-2xl bg-emerald-500 hover:bg-emerald-600 text-white text-lg font-bold shadow active:scale-[0.98] transition disabled:opacity-50">
          {busy ? '⏳ กำลังส่ง…' : '✅ ใช้รูปนี้ — ส่งเลย'}
        </button>
        <button onClick={onClose} className="w-full py-2.5 text-sm text-slate-400">ถ่ายใหม่ / ยกเลิก</button>
      </div>
    </BottomSheet>
  )
}

/* ---------- เบิกเงินล่วงหน้า Bottom Sheet (ข้อ 1.3) ---------- */
const ADV_STATUS = {
  PENDING: { th: 'รออนุมัติ', cls: 'bg-amber-100 text-amber-700' },
  APPROVED: { th: 'อนุมัติแล้ว', cls: 'bg-emerald-100 text-emerald-700' },
  REJECTED: { th: 'ไม่อนุมัติ', cls: 'bg-red-100 text-red-600' },
}

export function AdvanceSheet({ onClose, onSubmit, busy, advances = [] }) {
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')
  const valid = Number(amount) > 0 && reason.trim().length > 0

  return (
    <BottomSheet title="💵 ขอเบิกเงินล่วงหน้า" onClose={onClose}>
      <div className="space-y-3">
        <div>
          <label className="block text-sm font-semibold text-slate-600 mb-1">ยอดเงินที่ต้องการ (บาท)</label>
          <input type="number" inputMode="numeric" min="1" value={amount}
            onChange={(e) => setAmount(e.target.value)} placeholder="เช่น 500"
            className="w-full border border-slate-300 rounded-xl px-4 py-3 text-2xl font-bold text-center outline-none focus:ring-2 focus:ring-blue-200" />
        </div>
        <div>
          <label className="block text-sm font-semibold text-slate-600 mb-1">เหตุผล (บังคับ)</label>
          <textarea value={reason} onChange={(e) => setReason(e.target.value)}
            placeholder="เช่น สำรองค่าน้ำมัน / ค่าที่พักระหว่างทาง…" rows={2}
            className="w-full border border-slate-300 rounded-xl px-3 py-2.5 text-base outline-none focus:ring-2 focus:ring-blue-200" />
        </div>
        <div className="text-xs text-slate-400">
          ยอดที่อนุมัติจะถูก "หักจากยอดจ่ายสุทธิ" ของเที่ยวโดยอัตโนมัติตอนปิดงาน
        </div>
        <button disabled={busy || !valid} onClick={() => onSubmit({ amount: Number(amount), reason })}
          className="w-full py-4 rounded-2xl bg-blue-500 hover:bg-blue-600 text-white text-lg font-bold shadow active:scale-[0.98] transition disabled:opacity-40">
          {busy ? '⏳ กำลังส่งคำขอ…' : '📨 ส่งคำขอเบิกเงิน'}
        </button>

        {advances.length > 0 && (
          <div className="pt-2 border-t border-slate-100">
            <div className="text-sm font-semibold text-slate-600 mb-2">ประวัติคำขอของฉัน</div>
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {[...advances].reverse().map((a) => {
                const st = ADV_STATUS[a.status] || ADV_STATUS.PENDING
                return (
                  <div key={a.id} className="flex items-center justify-between bg-slate-50 rounded-lg px-3 py-2">
                    <div>
                      <div className="text-sm font-bold text-slate-700">฿{(a.amount || 0).toLocaleString('th-TH')}</div>
                      <div className="text-[11px] text-slate-400 truncate max-w-[160px]">{a.reason}</div>
                    </div>
                    <span className={`text-[11px] font-semibold px-2 py-1 rounded-full ${st.cls}`}>
                      {st.th}{a.deducted_trip_id ? ' · หักแล้ว' : ''}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </BottomSheet>
  )
}
