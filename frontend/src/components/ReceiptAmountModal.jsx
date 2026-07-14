// Modal จัดการยอดเงินใบเสร็จ OCR — แทน window.prompt เดิม (แก้บั๊กปุ่ม "ยืนยันยอด" task 4)
// 2 โหมด:
//   mode="approve" → ยืนยันยอด (แก้ตัวเลขได้ก่อนอนุมัติ) · ไม่บังคับเหตุผล
//   mode="edit"    → แก้ยอดเงิน OCR (task 2) · 🚨 บังคับกรอก "เหตุผล" ก่อนถึงจะกดยืนยันได้
import { useState } from 'react'
import { useApproveReceipt, useEditReceiptAmount } from '../api/hooks'
import { errMsg } from '../api/client'
import { Btn, Field, Modal, inputCls, money } from './ui'

const KIND_TH = { FUEL: '⛽ บิลน้ำมัน', TOLL: '🛣️ บิลทางหลวง' }

export default function ReceiptAmountModal({ receipt, mode = 'approve', label, onClose, onDone, onErr }) {
  const [amount, setAmount] = useState(String(receipt.amount ?? ''))
  const [reason, setReason] = useState('')
  const [err, setErr] = useState('')

  const approve = useApproveReceipt()
  const edit = useEditReceiptAmount()
  const isEdit = mode === 'edit'
  const pending = approve.isPending || edit.isPending

  // โหมด edit บังคับต้องมีเหตุผล ถึงจะกดยืนยันได้
  const canSubmit = amount !== '' && Number(amount) >= 0 && (!isEdit || reason.trim())

  const submit = async () => {
    setErr('')
    try {
      if (isEdit) {
        await edit.mutateAsync({ receiptId: receipt.id, new_amount: Number(amount), reason: reason.trim() })
        onDone?.(`✏️ แก้ยอดเงินเป็น ${money(Number(amount))} (บันทึกเหตุผลลง Audit แล้ว)`)
      } else {
        await approve.mutateAsync({ receiptId: receipt.id, amount: Number(amount) })
        onDone?.(`✅ ยืนยันยอด ${money(Number(amount))} — นับเข้ายอดจริงแล้ว`)
      }
      onClose()
    } catch (e) {
      const m = errMsg(e)
      setErr(m); onErr?.(m)
    }
  }

  const title = isEdit ? '✏️ แก้ไขยอดเงินใบเสร็จ' : '✅ ยืนยันยอดบิล'

  return (
    <Modal title={title} onClose={onClose}>
      <div className="text-sm text-slate-600 mb-3">
        {KIND_TH[receipt.kind] || 'ใบเสร็จ'}{label && <span className="text-slate-400"> · {label}</span>}
        <span className="text-slate-400"> · ยอดเดิม {money(receipt.amount)}</span>
      </div>

      {isEdit && (
        <div className="rounded-lg bg-amber-50 text-amber-700 text-xs px-3 py-2 mb-3">
          ⚠️ คุณแน่ใจหรือไม่ที่จะแก้ไขยอดเงินนี้? การแก้ไขจะถูกบันทึกลงระบบ Audit Log
        </div>
      )}

      <Field label={isEdit ? 'ยอดเงินใหม่ (บาท)' : 'ยอดเงิน (แก้ตัวเลขได้ก่อนอนุมัติ)'}>
        <input className={inputCls} type="number" min="0" value={amount} autoFocus
          onChange={(e) => setAmount(e.target.value)} />
      </Field>

      {isEdit && (
        <Field label="เหตุผลในการแก้ไข (บังคับ)">
          <input className={inputCls} value={reason} onChange={(e) => setReason(e.target.value)}
            placeholder="เช่น OCR อ่านเลขผิด บิลจริง 650" />
        </Field>
      )}

      {err && <div className="text-xs text-red-500 mb-3">{err}</div>}

      <div className="flex gap-2 mt-1">
        <Btn color="outline" className="flex-1" onClick={onClose}>ยกเลิก</Btn>
        <Btn color={isEdit ? 'orange' : 'green'} className="flex-1" disabled={!canSubmit || pending} onClick={submit}>
          {isEdit ? 'ยืนยันการแก้ไข' : 'ยืนยันยอด'}
        </Btn>
      </div>
    </Modal>
  )
}
