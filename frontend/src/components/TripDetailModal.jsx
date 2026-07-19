// Modal รายละเอียดทริป (Supervisor) — หลักฐานรายจุด + อนุมัติบิล OCR + การเงิน + ปิดงาน
// กฎสำคัญ: หักเงินต้องมีเหตุผล · ปิดงาน = freeze ถาวร · 409 = เตือนให้ยืนยัน (force)
import { useState } from 'react'
import {
  useTrip, usePenalty, useBonus, useCloseTrip, useCompleteTrip, useRequestCorrection,
} from '../api/hooks'
import { errMsg } from '../api/client'
import { Btn, Field, ImageLightbox, Modal, PhotoThumb, StatusPill, inputCls, money } from './ui'
import AddDropModal from './AddDropModal'
import TripAdjustModal from './TripAdjustModal'
import ReceiptAmountModal from './ReceiptAmountModal'
import StatusOverrideModal from './StatusOverrideModal'
import UnfreezeModal from './UnfreezeModal'

const KIND_TH = { FUEL: '⛽ บิลน้ำมัน', TOLL: '🛣️ บิลทางหลวง' }

export default function TripDetailModal({ tripId, onClose, onDone, isSuperAdmin }) {
  const { data: t } = useTrip(tripId)
  const penalty = usePenalty()
  const bonus = useBonus()
  const closeTrip = useCloseTrip()
  const completeTrip = useCompleteTrip()
  const requestCorr = useRequestCorrection()

  const [showAddDrop, setShowAddDrop] = useState(false)
  const [showAdjust, setShowAdjust] = useState(false)
  const [showStatus, setShowStatus] = useState(false)
  const [showUnfreeze, setShowUnfreeze] = useState(false)
  const [receiptModal, setReceiptModal] = useState(null)  // { receipt, mode }
  const [err, setErr] = useState('')
  const [penAmt, setPenAmt] = useState('')
  const [penReason, setPenReason] = useState('')
  const [bonusAmt, setBonusAmt] = useState('')
  const [corr, setCorr] = useState({ field_key: 'fuel', new_val: '', reason: '' })
  const [zoom, setZoom] = useState(null)  // Phase 4: ขยายดูรูปหลักฐานเต็มจอ

  if (!t) return null
  const fin = t.finance
  // Dynamic Multi-Drop: เที่ยวหลักยัง Active จนกว่า Supervisor จะกด "จบเที่ยว" (completed_at)
  const active = !t.completed_at && !t.frozen
  // บิลเติมน้ำมันที่ผูกกับทริปตรงๆ (ไม่ผูกจุดส่ง) — คนขับกด "บันทึกเติมน้ำมัน" ระหว่างทาง
  const fuelLogs = t.trip_receipts || []
  // ลิตรรวมทั้งทริป = บิลเติมระหว่างทาง + บิลน้ำมันรายจุดที่กรอกลิตรไว้ (ตรงกับสูตรฝั่ง backend)
  const fuelLiters =
    fuelLogs.reduce((sm, r) => sm + (r.liters || 0), 0) +
    t.drops.reduce((sm, d) => sm + d.receipts.reduce((s2, r) => s2 + (r.kind === 'FUEL' ? r.liters || 0 : 0), 0), 0)

  const run = async (fn, okMsg) => {
    setErr('')
    try {
      await fn()
      if (okMsg) onDone?.(okMsg)
    } catch (e) {
      setErr(errMsg(e))
    }
  }

  // ปิดงาน: 409 = TransitionWarning (รูปไม่ครบ) → เด้งยืนยันแล้วส่งซ้ำด้วย force=True (Override)
  const doClose = async () => {
    setErr('')
    try {
      await closeTrip.mutateAsync({ tripId: t.id })
      onDone?.(`🔒 ล็อกการเงิน ${t.code} แล้ว (ปิดบัญชีทริป)`)
    } catch (e) {
      if (e.response?.status === 409 && window.confirm(errMsg(e))) {
        try {
          await closeTrip.mutateAsync({ tripId: t.id, force: true })
          onDone?.(`🔒 ล็อกการเงิน ${t.code} (Override ส่งไม่ครบ) แล้ว`)
        } catch (e2) { setErr(errMsg(e2)) }
      } else if (e.response?.status !== 409) setErr(errMsg(e))
    }
  }

  // จบเที่ยวหลัก: 409 = ยังส่งงานย่อยไม่ครบ → ยืนยันแล้วส่งซ้ำด้วย force
  const doComplete = async () => {
    setErr('')
    try {
      await completeTrip.mutateAsync({ tripId: t.id })
      onDone?.(`🏁 จบเที่ยว ${t.code} แล้ว — รอตรวจบิล/ล็อกการเงิน`)
    } catch (e) {
      if (e.response?.status === 409 && window.confirm(errMsg(e))) {
        try {
          await completeTrip.mutateAsync({ tripId: t.id, force: true })
          onDone?.(`🏁 จบเที่ยว ${t.code} (Override ส่งไม่ครบ) แล้ว`)
        } catch (e2) { setErr(errMsg(e2)) }
      } else if (e.response?.status !== 409) setErr(errMsg(e))
    }
  }

  return (
    <Modal title={`${t.code} · ${t.plate || 'ยังไม่ผูกทะเบียน'}`} onClose={onClose} wide>
      <div className="flex items-center justify-between mb-4 gap-2 flex-wrap">
        <StatusPill status={t.status} />
        {t.frozen ? (
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-blue-600">🔒 ล็อกการเงิน — ฟอร์มถูกล็อกไว้</span>
            {/* Safety Unlock (ข้อ 3.2): ต้องมี popup ยืนยันก่อน แล้วค่อยกรอกเหตุผลปลดล็อก */}
            <Btn color="red" size="sm"
              onClick={() => {
                if (window.confirm('คุณต้องการปลดล็อกเพื่อแก้ไขข้อมูลประวัติใช่หรือไม่?\n\nการปลดล็อกและทุกการแก้ไขจะถูกบันทึกลง "ประวัติการแก้" อัตโนมัติ')) {
                  setShowUnfreeze(true)
                }
              }}>
              🔓 ปลดล็อกเพื่อแก้ไข (Unlock)
            </Btn>
          </div>
        ) : (
          <div className="flex gap-2">
            <Btn color="ghost" size="sm" onClick={() => setShowStatus(true)}>🔧 เปลี่ยนสถานะ</Btn>
            <Btn color="ghost" size="sm" onClick={() => setShowAdjust(true)}>✏️ แก้ไขข้อมูลทริป</Btn>
          </div>
        )}
      </div>

      {showAddDrop && (
        <AddDropModal trip={t} onClose={() => setShowAddDrop(false)} onDone={onDone} />
      )}
      {showAdjust && (
        <TripAdjustModal trip={t} onClose={() => setShowAdjust(false)} onDone={onDone} />
      )}
      {showStatus && (
        <StatusOverrideModal trip={t} onClose={() => setShowStatus(false)} onDone={onDone} onErr={(m) => setErr(m)} />
      )}
      {showUnfreeze && (
        <UnfreezeModal trip={t} onClose={() => setShowUnfreeze(false)} onDone={onDone} />
      )}
      {receiptModal && (
        <ReceiptAmountModal receipt={receiptModal.receipt} mode={receiptModal.mode}
          label={receiptModal.label || `จุด ${receiptModal.seq}`}
          onClose={() => setReceiptModal(null)} onDone={onDone} onErr={(m) => setErr(m)} />
      )}

      {/* ---- 🧭 เลขไมล์ตอนเริ่มงาน + รูปหน้าปัด (ให้แอดมินเทียบเลขที่คนขับพิมพ์กับรูปจริง) ---- */}
      <div className="rounded-lg ring-1 ring-slate-200 p-3 mb-4 flex items-center gap-3">
        <PhotoThumb src={t.odometer_start_photo} label="หน้าปัดไมล์ตอนเริ่มงาน" onZoom={setZoom} size="w-16 h-16" />
        <div className="min-w-0">
          <div className="text-sm font-medium text-slate-700">🧭 เลขไมล์ตอนเริ่มงาน</div>
          <div className="text-xl font-bold text-slate-800">
            {t.odometer_start != null ? `${t.odometer_start.toLocaleString('th-TH')} กม.` : '—'}
          </div>
          <div className="text-[11px] text-slate-400">
            {t.odometer_start_photo
              ? 'คลิกรูปเพื่อขยาย — ตรวจว่าเลขบนหน้าปัดตรงกับเลขที่คนขับพิมพ์'
              : 'ยังไม่มีรูปหน้าปัดไมล์ (ทริปเก่าก่อนมีระบบบังคับถ่ายรูป)'}
          </div>
        </div>
        {t.odometer_end != null && (
          <div className="ml-auto text-right">
            <div className="text-[11px] text-slate-400">เลขไมล์จบ</div>
            <div className="text-base font-bold text-slate-700">{t.odometer_end.toLocaleString('th-TH')} กม.</div>
          </div>
        )}
      </div>

      {/* ---- งานย่อย (Sub-Trips) + หลักฐาน + บิล ---- */}
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-medium text-slate-700">
          📦 งานย่อย (Sub-Trips) · {t.drops.length} ใบ
          {active
            ? <span className="ml-2 text-[10px] font-semibold text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded">เที่ยวหลักยัง Active</span>
            : <span className="ml-2 text-[10px] font-semibold text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">จบเที่ยวแล้ว</span>}
        </div>
        {active && t.drops.length < 5 && (
          <Btn color="ghost" size="sm" onClick={() => setShowAddDrop(true)}>＋ เพิ่มงานย่อย</Btn>
        )}
      </div>
      <div className="space-y-3 mb-4">
        {t.drops.map((d) => (
          <div key={d.id} className="rounded-lg ring-1 ring-slate-200 p-3">
            <div className="flex items-center justify-between text-sm">
              <div className="font-medium text-slate-700">
                {d.delivered ? '✅' : '⬜'} จุด {d.seq}:{' '}
                <span className="text-slate-500">{d.origin || '—'}</span>
                <span className="text-orange-500 mx-1">➜</span>
                <span>{d.destination || d.name}</span>
              </div>
              <div className="text-xs text-slate-400">เบี้ยเลี้ยง {money(d.allowance)}</div>
            </div>
            {/* Phase 4: รูปหลักฐานจริง — คลิกเพื่อขยายดูเต็มจอ */}
            <div className="flex items-center gap-2 mt-2">
              <PhotoThumb src={d.tarp} label={`ผ้าใบ จุด ${d.seq}`} onZoom={setZoom} />
              <PhotoThumb src={d.photo} label={`ส่งของ จุด ${d.seq}`} onZoom={setZoom} />
              {!d.tarp && !d.photo && <span className="text-[11px] text-slate-300">ยังไม่มีรูปหลักฐาน</span>}
              {d.gps && <span className="text-[11px] text-slate-400 ml-auto">📍 {d.gps}</span>}
            </div>
            {d.receipts.map((r) => (
              <div key={r.id} className={`mt-2 flex items-center justify-between gap-2 rounded-md px-2.5 py-1.5 text-xs ${r.approved ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                <span className="min-w-0 flex items-center gap-2">
                  <PhotoThumb src={r.photo} label={`${KIND_TH[r.kind]} จุด ${d.seq}`} onZoom={setZoom} size="w-9 h-9" />
                  <span>
                    {KIND_TH[r.kind]} {money(r.amount)}
                    {r.liters > 0 && ` · ${r.liters.toFixed(2)} ลิตร`}
                    {r.date && ` (${r.date})`} — {r.approved ? 'อนุมัติแล้ว' : '🤖 OCR Draft รอตรวจ'}
                  </span>
                </span>
                {!t.frozen && (
                  <div className="flex gap-1.5 shrink-0">
                    {/* ยืนยันยอด (task 4 — เปิด Modal แทน window.prompt) */}
                    {!r.approved && (
                      <Btn size="sm" color="green" onClick={() => setReceiptModal({ receipt: r, mode: 'approve', seq: d.seq })}>
                        ยืนยันยอด
                      </Btn>
                    )}
                    {/* แก้ไขยอดเงิน OCR (task 2 — บังคับเหตุผล) */}
                    <Btn size="sm" color="ghost" onClick={() => setReceiptModal({ receipt: r, mode: 'edit', seq: d.seq })}>
                      ✏️ แก้ยอด
                    </Btn>
                  </div>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* ---- ⛽ เติมน้ำมันระหว่างทาง + อัตราสิ้นเปลือง (Phase 5) ---- */}
      <div className="rounded-lg ring-1 ring-slate-200 p-3 mb-4">
        <div className="flex items-center justify-between mb-2">
          <div className="text-sm font-medium text-slate-700">⛽ การเติมน้ำมันระหว่างทาง</div>
          <div className="text-xs text-slate-500">
            ลิตรรวม <b className="text-slate-700">{fuelLiters.toFixed(2)} ลิตร</b>
          </div>
        </div>

        {/* อัตราสิ้นเปลืองที่ระบบคำนวณตอนจบงาน (ระยะทาง ÷ ลิตรรวม) */}
        <div className="rounded-md bg-blue-50 ring-1 ring-blue-200 px-3 py-2 mb-2 flex items-center justify-between">
          <span className="text-xs text-blue-700">📊 อัตราสิ้นเปลือง (km/L)</span>
          <span className="text-lg font-bold text-blue-700">
            {t.km_per_liter != null ? `${t.km_per_liter} กม./ลิตร` : '—'}
          </span>
        </div>
        <div className="text-[11px] text-slate-400 mb-2">
          ระยะทาง {t.distance_km?.toLocaleString('th-TH') || 0} กม.
          {t.odometer_start != null && t.odometer_end != null
            ? ` (ไมล์ ${t.odometer_start.toLocaleString('th-TH')} → ${t.odometer_end.toLocaleString('th-TH')})`
            : ''}
          {t.km_per_liter == null && ' · ยังคิด km/L ไม่ได้ — ต้องมีจำนวนลิตรและเลขไมล์จบก่อน'}
        </div>

        {fuelLogs.length === 0 ? (
          <div className="text-[11px] text-slate-300">คนขับยังไม่ได้แจ้งเติมน้ำมันในทริปนี้</div>
        ) : (
          fuelLogs.map((r) => (
            <div key={r.id} className={`mt-2 flex items-center justify-between gap-2 rounded-md px-2.5 py-1.5 text-xs ${r.approved ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
              <span className="min-w-0 flex items-center gap-2">
                {/* รูปสลิปน้ำมันที่คนขับส่งมา — คลิกขยายเต็มจอ */}
                <PhotoThumb src={r.photo} label="สลิปน้ำมัน" onZoom={setZoom} size="w-9 h-9" />
                <span>
                  <b>{(r.liters || 0).toFixed(2)} ลิตร</b> · {money(r.amount)}
                  {r.date && ` (${r.date})`} — {r.approved ? 'อนุมัติแล้ว' : '🤖 OCR Draft รอตรวจ'}
                </span>
              </span>
              {!t.frozen && (
                <div className="flex gap-1.5 shrink-0">
                  {!r.approved && (
                    <Btn size="sm" color="green" onClick={() => setReceiptModal({ receipt: r, mode: 'approve', label: '⛽ เติมระหว่างทาง' })}>
                      ยืนยันยอด
                    </Btn>
                  )}
                  <Btn size="sm" color="ghost" onClick={() => setReceiptModal({ receipt: r, mode: 'edit', label: '⛽ เติมระหว่างทาง' })}>
                    ✏️ แก้ยอด
                  </Btn>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* ---- สรุปการเงิน ---- */}
      <div className="rounded-lg bg-slate-50 p-3 text-sm mb-4">
        <div className="font-medium text-slate-700 mb-1.5">💰 สรุปการเงิน</div>
        <div className="grid grid-cols-2 gap-y-1 text-xs text-slate-600">
          <span>เบี้ยเลี้ยงรวม</span><span className="text-right">{money(fin.allowance_total)}</span>
          <span>โบนัส</span><span className="text-right">{money(fin.bonus)}</span>
          <span>ยอดหัก {t.penalty_reason && `(${t.penalty_reason})`}</span><span className="text-right text-red-500">-{money(fin.penalty)}</span>
          <span className="font-semibold">เบี้ยเลี้ยงสุทธิ</span><span className="text-right font-semibold">{money(fin.allowance_net)}</span>
          <span>ค่าน้ำมัน (อนุมัติแล้ว)</span><span className="text-right">{money(fin.fuel_total)}</span>
          <span>ค่าทางหลวง (อนุมัติแล้ว)</span><span className="text-right">{money(fin.toll_total)}</span>
          <span>หักเบิกเงินล่วงหน้า</span><span className="text-right text-red-500">-{money(fin.advance_total)}</span>
          <span className="font-bold text-slate-800">ยอดจ่ายสุทธิ (Payout)</span>
          <span className="text-right font-bold text-slate-800">{money(fin.payout_net)}</span>
        </div>
      </div>

      {/* ---- ปฏิบัติการการเงิน — Safety Unlock (ข้อ 3.2):
           frozen = ฟอร์มโชว์แต่ถูก Disabled ทั้งหมด จนกว่าจะกดปลดล็อกด้านบน ---- */}
      <div className={`mb-4 space-y-3 ${t.frozen ? 'opacity-50' : ''}`}>
        {t.frozen && (
          <div className="text-[11px] font-semibold text-blue-600">
            🔒 ฟอร์มด้านล่างถูกล็อก — กดปุ่ม "🔓 ปลดล็อกเพื่อแก้ไข" ด้านบนก่อนจึงจะแก้ได้
          </div>
        )}
        <div className="flex gap-2 items-end">
          <Field label="หักเงิน (บาท) — หักจากเบี้ยเลี้ยงรวมเท่านั้น">
            <input className={inputCls} type="number" min="0" value={penAmt} disabled={t.frozen}
              onChange={(e) => setPenAmt(e.target.value)} />
          </Field>
          <Field label="เหตุผล (บังคับ)">
            <input className={inputCls} value={penReason} disabled={t.frozen}
              onChange={(e) => setPenReason(e.target.value)} placeholder="เช่น ไม่คลุมผ้าใบจุด 2" />
          </Field>
          <Btn color="red" className="mb-3" disabled={penalty.isPending || t.frozen}
            onClick={() => run(() => penalty.mutateAsync({ tripId: t.id, amount: Number(penAmt), reason: penReason }), `🔔 หักเงิน ${money(Number(penAmt))} — แจ้ง Admin แล้ว`)}>
            หักเงิน
          </Btn>
        </div>
        <div className="flex gap-2 items-end">
          <Field label="โบนัสทริป (บาท)">
            <input className={inputCls} type="number" min="0" value={bonusAmt} disabled={t.frozen}
              onChange={(e) => setBonusAmt(e.target.value)} />
          </Field>
          <Btn color="blue" className="mb-3" disabled={bonus.isPending || t.frozen}
            onClick={() => run(() => bonus.mutateAsync({ tripId: t.id, amount: Number(bonusAmt) }), '💾 บันทึกโบนัสแล้ว')}>
            บันทึกโบนัส
          </Btn>
        </div>
      </div>

      {/* ---- ขอปลดล็อก (ทริป freeze แล้ว) ---- */}
      {t.frozen && (
        <div className="mb-4 rounded-lg ring-1 ring-blue-200 bg-blue-50/50 p-3">
          <div className="text-xs font-medium text-slate-700 mb-2">🔓 ขอปลดล็อกแก้ตัวเลข (ส่งให้ Super Admin อนุมัติ)</div>
          <div className="flex gap-2">
            <select className={inputCls} value={corr.field_key} onChange={(e) => setCorr({ ...corr, field_key: e.target.value })}>
              <option value="fuel">ค่าน้ำมัน</option>
              <option value="toll">ค่าทางหลวง</option>
              <option value="bonus">โบนัส</option>
              <option value="penalty">ยอดหัก</option>
            </select>
            <input className={inputCls} type="number" placeholder="ค่าใหม่" value={corr.new_val}
              onChange={(e) => setCorr({ ...corr, new_val: e.target.value })} />
          </div>
          <input className={`${inputCls} mt-2`} placeholder="เหตุผล (บังคับ)" value={corr.reason}
            onChange={(e) => setCorr({ ...corr, reason: e.target.value })} />
          <Btn color="blue" size="sm" className="mt-2 w-full" disabled={requestCorr.isPending}
            onClick={() => run(() => requestCorr.mutateAsync({ tripId: t.id, field_key: corr.field_key, new_val: Number(corr.new_val), reason: corr.reason }), '📨 ส่งคำขอปลดล็อกให้ Super Admin แล้ว')}>
            ส่งคำขอปลดล็อก
          </Btn>
        </div>
      )}

      {err && <div className="text-xs text-red-500 mb-3">{err}</div>}
      <ImageLightbox image={zoom} onClose={() => setZoom(null)} />

      <div className="flex gap-2">
        <Btn color="outline" className="flex-1" onClick={onClose}>ปิดหน้าต่าง</Btn>
        {/* จบเที่ยวหลัก — เที่ยวจบสมบูรณ์ได้ก็ต่อเมื่อ Supervisor กดปุ่มนี้เท่านั้น */}
        {active && (
          <Btn color="green" className="flex-1" disabled={completeTrip.isPending} onClick={doComplete}>
            🏁 จบเที่ยว (Complete)
          </Btn>
        )}
        {/* ล็อกการเงิน: ทำได้หลังจบเที่ยวแล้ว (หรือทริปเก่าที่มี closed_at) และยังไม่ล็อก */}
        {!t.frozen && (t.completed_at || t.closed_at) && (
          <Btn color="slate" className="flex-1" disabled={closeTrip.isPending} onClick={doClose}>
            🔒 ล็อกการเงิน (ปิดบัญชี)
          </Btn>
        )}
      </div>
    </Modal>
  )
}
