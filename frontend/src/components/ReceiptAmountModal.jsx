// Modal จัดการยอดเงินใบเสร็จ — 🚫 ไม่มี OCR แล้ว คนคุมงานเปิดรูปดูแล้วคีย์เอง
// 2 โหมด:
//   mode="approve" → ยืนยันบิล · บังคับกรอก "ยอดเงิน" + "วันที่บนบิล" ทั้งคู่ (อ่านจากรูป)
//   mode="edit"    → แก้ยอดเงินภายหลัง · บังคับกรอก "เหตุผล" ก่อนถึงจะกดยืนยันได้
import { useState } from 'react'
import { useApproveReceipt, useEditReceiptAmount } from '../api/hooks'
import { errMsg } from '../api/client'
import { Btn, Field, Modal, inputCls, money } from './ui'
import { isViewable } from '../utils/image'

const KIND_TH = { FUEL: '⛽ บิลน้ำมัน', TOLL: '🛣️ บิลทางหลวง' }
const today = () => new Date().toISOString().slice(0, 10)

export default function ReceiptAmountModal({ receipt, mode = 'approve', label, onClose, onDone, onErr }) {
  const [amount, setAmount] = useState(receipt.amount ? String(receipt.amount) : '')
  const [date, setDate] = useState(receipt.date || today())
  const [reason, setReason] = useState('')
  const [err, setErr] = useState('')

  const approve = useApproveReceipt()
  const edit = useEditReceiptAmount()
  const isEdit = mode === 'edit'
  const pending = approve.isPending || edit.isPending

  // approve: บังคับยอด + วันที่ · edit: บังคับยอด + เหตุผล
  const amountOk = amount !== '' && Number(amount) >= 0
  const canSubmit = amountOk && (isEdit ? !!reason.trim() : !!date.trim())

  const submit = async () => {
    setErr('')
    try {
      if (isEdit) {
        await edit.mutateAsync({ receiptId: receipt.id, new_amount: Number(amount), reason: reason.trim() })
        onDone?.(`✏️ แก้ยอดเงินเป็น ${money(Number(amount))} (บันทึกเหตุผลลง Audit แล้ว)`)
      } else {
        await approve.mutateAsync({ receiptId: receipt.id, amount: Number(amount), date: date.trim() })
        onDone?.(`✅ บันทึกยอด ${money(Number(amount))} (บิลวันที่ ${date}) — นับเข้ายอดจริงแล้ว`)
      }
      onClose()
    } catch (e) {
      const m = errMsg(e)
      setErr(m); onErr?.(m)
    }
  }

  const title = isEdit ? '✏️ แก้ไขยอดเงินใบเสร็จ' : '🧾 ตรวจบิล — คีย์ยอดเงินและวันที่'

  return (
    <Modal title={title} onClose={onClose}>
      <div className="text-sm text-slate-600 mb-3">
        {KIND_TH[receipt.kind] || 'ใบเสร็จ'}{label && <span className="text-slate-400"> · {label}</span>}
      </div>

      {/* 📷 รูปบิลจริงที่คนขับถ่ายมา — คนคุมงานอ่านตัวเลขจากรูปนี้แล้วพิมพ์ลงช่องข้างล่าง */}
      {isViewable(receipt.photo) ? (
        <a href={receipt.photo} target="_blank" rel="noreferrer" className="block mb-3">
          <img src={receipt.photo} alt="รูปบิล"
            className="w-full max-h-72 object-contain rounded-lg ring-1 ring-slate-200 bg-slate-50" />
          <div className="text-[11px] text-blue-600 text-center mt-1">🔍 คลิกที่รูปเพื่อเปิดดูเต็มขนาด</div>
        </a>
      ) : (
        <div className="rounded-lg bg-slate-50 text-slate-400 text-xs px-3 py-4 text-center mb-3">
          — ไม่มีรูปบิลแนบมา —
        </div>
      )}

      {isEdit && (
        <div className="rounded-lg bg-amber-50 text-amber-700 text-xs px-3 py-2 mb-3">
          ⚠️ คุณแน่ใจหรือไม่ที่จะแก้ไขยอดเงินนี้? การแก้ไขจะถูกบันทึกลงระบบ Audit Log
        </div>
      )}

      <Field label="ยอดเงินบนบิล (บาท) — อ่านจากรูปแล้วพิมพ์เอง">
        <input className={inputCls} type="number" min="0" value={amount} autoFocus
          onChange={(e) => setAmount(e.target.value)} placeholder="เช่น 1850" />
      </Field>

      {!isEdit && (
        <Field label="วันที่บนบิล (บังคับ)">
          <input className={inputCls} type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </Field>
      )}

      {isEdit && (
        <Field label="เหตุผลในการแก้ไข (บังคับ)">
          <input className={inputCls} value={reason} onChange={(e) => setReason(e.target.value)}
            placeholder="เช่น คีย์ยอดผิด บิลจริง 650" />
        </Field>
      )}

      {err && <div className="text-xs text-red-500 mb-3">{err}</div>}

      <div className="flex gap-2 mt-1">
        <Btn color="outline" className="flex-1" onClick={onClose}>ยกเลิก</Btn>
        <Btn color={isEdit ? 'orange' : 'green'} className="flex-1" disabled={!canSubmit || pending} onClick={submit}>
          {isEdit ? 'ยืนยันการแก้ไข' : 'บันทึกยอด + ยืนยันบิล'}
        </Btn>
      </div>
      {!canSubmit && (
        <div className="text-[11px] text-slate-400 text-center mt-2">
          {isEdit ? 'ต้องกรอกยอดเงินและเหตุผลก่อน' : 'ต้องกรอกทั้งยอดเงินและวันที่บนบิลก่อน'}
        </div>
      )}
    </Modal>
  )
}
