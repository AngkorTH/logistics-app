// ศูนย์อนุมัติ — 2 ส่วน:
// 1) OCR Draft Approval: Supervisor+ ยืนยันยอดบิลน้ำมัน/ทางหลวง (draft ไม่นับเข้ายอดจนกว่าจะอนุมัติ)
// 2) Correction Workflow: คำขอปลดล็อกการเงิน — ปุ่มอนุมัติ/ปฏิเสธเห็นเฉพาะ Super Admin
import { useState } from 'react'
import { useCorrections, useDecideCorrection } from '../api/hooks'
import { errMsg } from '../api/client'
import { Btn, money } from './ui'
import { isViewable } from '../utils/image'
import ReceiptAmountModal from './ReceiptAmountModal'

const KIND_TH = { FUEL: '⛽ บิลน้ำมัน', TOLL: '🛣️ บิลทางหลวง' }
const CORR_BADGE = {
  PENDING: 'bg-amber-100 text-amber-700',
  APPROVED: 'bg-emerald-100 text-emerald-700',
  REJECTED: 'bg-red-100 text-red-600',
}
const CORR_TH = { PENDING: 'รออนุมัติ', APPROVED: 'อนุมัติแล้ว', REJECTED: 'ปฏิเสธ' }

// ดึงบิล draft ทั้งหมดจากทริปที่ยังไม่ freeze
// รวมทั้งบิลรายจุดส่ง (drops) และบิลแจ้งเติมน้ำมันระหว่างทาง (trip_receipts — ไม่ผูกจุด)
export const pendingReceipts = (trips) =>
  (trips || []).flatMap((t) =>
    t.frozen ? [] : [
      ...t.drops.flatMap((d) =>
        d.receipts.filter((r) => !r.approved).map((r) => ({ ...r, trip: t, drop: d }))),
      ...(t.trip_receipts || []).filter((r) => !r.approved).map((r) => ({ ...r, trip: t, drop: null })),
    ])

export default function ApprovalCenter({ trips, isSuperAdmin, onDone, onErr }) {
  const { data: corrections } = useCorrections()
  const decide = useDecideCorrection()
  const drafts = pendingReceipts(trips)
  // แก้บั๊ก task 4: เปิด Modal ยืนยันยอด (แทน window.prompt ที่กดไม่ติดในบาง browser)
  const [approving, setApproving] = useState(null)

  const doDecide = async (c, action) => {
    const label = action === 'approve' ? 'อนุมัติ' : 'ปฏิเสธ'
    if (!window.confirm(`${label}คำขอ ${c.code}: ${c.field_label} ${money(c.old_val)} → ${money(c.new_val)}?`)) return
    try {
      await decide.mutateAsync({ id: c.id, action, reason: '' })
      onDone?.(`${action === 'approve' ? '✅ อนุมัติ' : '⛔ ปฏิเสธ'}คำขอ ${c.code} แล้ว`)
    } catch (e) { onErr?.(errMsg(e)) }
  }

  return (
    <div className="grid md:grid-cols-2 gap-4">
      {/* ---- OCR Draft Approval ---- */}
      <div className="bg-white rounded-xl ring-1 ring-slate-200 shadow-sm p-4">
        <div className="font-bold text-slate-700 text-sm mb-1">🧾 บิลรอตรวจ — เปิดรูปแล้วคีย์ยอด ({drafts.length})</div>
        <div className="text-[11px] text-slate-400 mb-3">
          ระบบไม่อ่านบิลอัตโนมัติแล้ว — กดที่รูปเพื่อดูบิล แล้วพิมพ์ยอดเงินกับวันที่เอง
        </div>
        {!drafts.length && <div className="text-xs text-slate-400 py-4 text-center">ไม่มีบิลค้างตรวจ 🎉</div>}
        <div className="space-y-2">
          {drafts.map((r) => (
            <div key={r.id} className="flex items-center gap-3 rounded-lg bg-amber-50 px-3 py-2">
              {/* รูปบิลจริงที่คนขับถ่ายมา — คลิกเปิด modal คีย์ยอด */}
              <button onClick={() => setApproving(r)} className="shrink-0">
                {isViewable(r.photo) ? (
                  <img src={r.photo} alt="บิล" loading="lazy"
                    className="w-12 h-12 rounded-lg object-cover ring-1 ring-amber-300 hover:ring-blue-400 transition" />
                ) : (
                  <span className="w-12 h-12 rounded-lg bg-slate-100 ring-1 ring-slate-200 flex items-center justify-center text-lg">🧾</span>
                )}
              </button>
              <div className="text-xs text-slate-700 flex-1 min-w-0">
                <span className="font-medium">
                  {r.trip.code} · {r.drop ? `จุด ${r.drop.seq}` : 'เติมระหว่างทาง'}
                </span> — {KIND_TH[r.kind]}
                <div className="text-[10px] text-slate-400 truncate">
                  {r.drop ? r.drop.name : `${r.liters || 0} ลิตร`} · ยังไม่ได้คีย์ยอด
                </div>
              </div>
              <Btn size="sm" color="green" onClick={() => setApproving(r)}>คีย์ยอด</Btn>
            </div>
          ))}
        </div>
      </div>

      {approving && (
        <ReceiptAmountModal receipt={approving} mode="approve"
          label={`${approving.trip.code} ${approving.drop ? `จุด ${approving.drop.seq}` : 'เติมระหว่างทาง'}`}
          onClose={() => setApproving(null)} onDone={onDone} onErr={onErr} />
      )}

      {/* ---- Correction Workflow ---- */}
      <div className="bg-white rounded-xl ring-1 ring-slate-200 shadow-sm p-4">
        <div className="font-bold text-slate-700 text-sm mb-3">
          🔓 คำขอปลดล็อกการเงิน {isSuperAdmin ? '(คุณอนุมัติได้)' : '(รอ Super Admin)'}
        </div>
        {!corrections?.length && <div className="text-xs text-slate-400 py-4 text-center">ไม่มีคำขอ</div>}
        <div className="space-y-2">
          {(corrections || []).map((c) => (
            <div key={c.id} className="rounded-lg ring-1 ring-slate-100 px-3 py-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-700">{c.code} · ทริป #{c.trip_id}</span>
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${CORR_BADGE[c.status]}`}>{CORR_TH[c.status]}</span>
              </div>
              <div className="text-xs text-slate-600 mt-1">
                {c.field_label}: <span className="line-through text-slate-400">{money(c.old_val)}</span> → <span className="font-semibold">{money(c.new_val)}</span>
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">โดย {c.requester_name} · เหตุผล: {c.reason}</div>
              {c.status === 'PENDING' && isSuperAdmin && (
                <div className="flex gap-2 mt-2">
                  <Btn size="sm" color="green" className="flex-1" onClick={() => doDecide(c, 'approve')}>👑 อนุมัติ</Btn>
                  <Btn size="sm" color="red" className="flex-1" onClick={() => doDecide(c, 'reject')}>ปฏิเสธ</Btn>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
