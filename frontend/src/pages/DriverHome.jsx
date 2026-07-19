// Driver App — Mobile-First 100% (การ์ดใหญ่ ปุ่มใหญ่ อ่านง่ายกลางแดด)
// State Machine UI: ⚪ รองาน · 🟠 ตรวจสภาพรถ (บังคับ) → ปุ่ม "ขึ้นของเสร็จแล้ว" (→GREEN + GPS)
// · 🟢 ลิสต์จุดส่ง Multi-Drop + 4 ปุ่มหลักฐานต่อจุด
// Phase 3A: Checklist ตรวจรถล็อกปุ่มเริ่มงาน · SOS · เบิกเงินล่วงหน้า (Bottom Sheet ทั้งคู่)
import { useState } from 'react'
import {
  useTrips, useFinishLoading, useUploadReceipt, useUploadTarp, useRecordDelivery,
  useInspection, useSubmitInspection, useAdvances, useRequestAdvance, useSos, useReportIssue,
  useLogFuel, useEndTrip,
} from '../api/hooks'
import { errMsg } from '../api/client'
import { DIFFICULTY, ImageLightbox, PhotoThumb, STATUS, StatusPill, money } from '../components/ui'
import { AdvanceSheet, EndTripSheet, InspectionCard, PhotoConfirmSheet, RefuelSheet, SosSheet, ReportIssueSheet } from '../components/DriverSheets'
import { pickImage } from '../utils/image'
import { useOffline } from '../offline/useOffline'

// ดึงพิกัด GPS ปัจจุบัน — ถ้าเบราว์เซอร์ไม่ให้สิทธิ์/timeout ใช้พิกัดสำนักงานเป็น fallback
const getGps = () =>
  new Promise((resolve) => {
    const fallback = { lat: 13.7367, lng: 100.5231 }
    if (!navigator.geolocation) return resolve(fallback)
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude }),
      () => resolve(fallback),
      { timeout: 5000 },
    )
  })

// จำลองผลอ่าน OCR ฝั่ง client (backend เก็บเป็น Draft รอ Supervisor ตรวจเสมอ)
const mockOcr = (kind) =>
  kind === 'FUEL' ? 1000 + Math.floor(Math.random() * 1500) : 100 + Math.floor(Math.random() * 300)

export default function DriverHome() {
  const { data: trips, isLoading, error } = useTrips()
  const finishLoading = useFinishLoading()
  const uploadReceipt = useUploadReceipt()
  const uploadTarp = useUploadTarp()
  const delivery = useRecordDelivery()
  const submitInspection = useSubmitInspection()
  const requestAdvance = useRequestAdvance()
  const sos = useSos()
  const reportIssue = useReportIssue()
  const logFuel = useLogFuel()
  const endTrip = useEndTrip()
  const { data: advances } = useAdvances()

  const [toast, setToast] = useState(null)
  const [busyKey, setBusyKey] = useState(null)   // กันกดปุ่มซ้ำระหว่างรอ API
  const [sheet, setSheet] = useState(null)        // 'sos' | 'advance' | 'issue' | 'refuel' | null
  const [reinspect, setReinspect] = useState(false) // ขอเปิดฟอร์มตรวจใหม่หลัง REJECTED
  const [photoDraft, setPhotoDraft] = useState(null)  // Phase 4: รูปที่ถ่ายรอยืนยันก่อนส่ง
  const [zoom, setZoom] = useState(null)              // Phase 4: ขยายดูรูปเต็มจอ
  // ทริปที่รอกรอก "เลขไมล์จบ" — เก็บแยกจาก active เพราะทริปพลิกเป็น WHITE ทันทีที่ส่งครบทุกจุด
  const [endTarget, setEndTarget] = useState(null)    // { id, code, odometer_start } | null

  // Offline Auto-Sync (Phase 3B): สถานะเน็ต + คิวค้างส่ง
  const { online, pending } = useOffline()
  const isQueued = (url) => pending.some((p) => p.url === url) // ปุ่มนี้มีรายการรอส่งอยู่ไหม

  // ทริปที่กำลังวิ่งอยู่ (ORANGE/GREEN) — ถ้าไม่มีคือสถานะรองาน
  const active = (trips || []).find((t) => !t.frozen && t.status !== 'WHITE')
  // ผลตรวจสภาพรถล่าสุดของทริปนี้ (โหลดเฉพาะตอนมีทริป)
  const { data: inspection } = useInspection(active?.id)
  const inspectionOk = !!inspection && ['PASSED', 'APPROVED'].includes(inspection.status)

  const notify = (msg, kind = 'green') => { setToast({ msg, kind }); setTimeout(() => setToast(null), 3500) }
  const run = async (key, fn, okMsg) => {
    setBusyKey(key)
    try {
      const out = await fn()
      if (out?.queued) notify('📴 ออฟไลน์ — บันทึกไว้แล้ว จะส่งเข้าระบบอัตโนมัติเมื่อเน็ตกลับ', 'amber')
      else if (okMsg) notify(okMsg)
    } catch (e) {
      notify(errMsg(e), 'red')
    } finally {
      setBusyKey(null)
    }
  }

  if (isLoading) return <div className="text-center text-slate-400 py-16">กำลังโหลดงาน…</div>
  if (error) return <div className="text-center text-red-500 py-16 text-sm">โหลดข้อมูลไม่สำเร็จ — ตรวจสอบสัญญาณ/Backend</div>

  // 🟢/🔴 แถบสถานะเน็ต + จำนวนรายการรอส่ง (ข้อกำหนด 3B-3)
  const netBadge = (
    <div className={`rounded-xl px-4 py-2.5 text-center text-sm font-bold ring-1 ${
      online ? 'bg-emerald-50 ring-emerald-200 text-emerald-700' : 'bg-red-50 ring-red-300 text-red-600'
    }`}>
      {online ? '🟢 ออนไลน์' : '🔴 ออฟไลน์ — แอปจะบันทึกข้อมูลไว้ส่งภายหลัง กดทำงานต่อได้เลย'}
      {pending.length > 0 && (
        <span className="block text-xs font-semibold mt-0.5 text-amber-600">
          🕓 รอส่งเข้าระบบ {pending.length} รายการ{online ? ' — กำลังทยอยส่ง…' : ''}
        </span>
      )}
    </div>
  )

  /* ---------- Sheets ที่ใช้ร่วมทุกสถานะ ---------- */
  const sheets = (
    <>
      {sheet === 'advance' && (
        <AdvanceSheet advances={advances || []} busy={busyKey === 'advance'} onClose={() => setSheet(null)}
          onSubmit={({ amount, reason }) =>
            run('advance', async () => {
              await requestAdvance.mutateAsync({ amount, reason })
              setSheet(null)
            }, `📨 ส่งคำขอเบิก ${money(amount)} แล้ว — รอคนคุมงานอนุมัติ`)} />
      )}
      {sheet === 'sos' && active && (
        <SosSheet busy={busyKey === 'sos'} onClose={() => setSheet(null)}
          onSubmit={({ kind, message, photo_b64 }) =>
            run('sos', async () => {
              const gps = await getGps()
              await sos.mutateAsync({ tripId: active.id, kind, message, photo_b64, ...gps })
              setSheet(null)
            }, '🚨 แจ้งเหตุแล้ว! ทริปถูกพักชั่วคราว — คนคุมงานได้รับแจ้งเตือนทันที')} />
      )}
      {sheet === 'issue' && !active && (
        <ReportIssueSheet busy={busyKey === 'issue'} onClose={() => setSheet(null)}
          onSubmit={({ message, photo_b64 }) =>
            run('issue', async () => {
              await reportIssue.mutateAsync({ message, photo_b64 })
              setSheet(null)
            }, '🔧 แจ้งเหตุแล้ว! รถถูกตั้งเป็น "กำลังซ่อม" — คนคุมงานได้รับแจ้งเตือน')} />
      )}
      {sheet === 'refuel' && active && (
        <RefuelSheet busy={busyKey === 'refuel'} onClose={() => setSheet(null)}
          onSubmit={({ liters, photo_b64 }) =>
            run('refuel', async () => {
              await logFuel.mutateAsync({
                tripId: active.id, liters, photo_b64, ocr_amount: mockOcr('FUEL'),
              })
              setSheet(null)
            }, `⛽ บันทึกเติมน้ำมัน ${liters} ลิตรแล้ว — รอคนคุมงานยืนยันยอดเงิน`)} />
      )}
      {endTarget && (
        <EndTripSheet busy={busyKey === 'end'} odometerStart={endTarget.odometer_start}
          onClose={() => setEndTarget(null)}
          onSubmit={({ odometer_end }) =>
            run('end', async () => {
              try {
                await endTrip.mutateAsync({ tripId: endTarget.id, odometer_end })
              } catch (e) {
                // 409 = ยังส่งของไม่ครบ (warn-don't-block) → ยืนยันแล้วส่งซ้ำด้วย force
                if (e.response?.status === 409 && window.confirm(errMsg(e))) {
                  await endTrip.mutateAsync({ tripId: endTarget.id, odometer_end, force: true })
                } else throw e
              }
              setEndTarget(null)
            }, '🏁 จบงานแล้ว — ระบบคำนวณระยะทางและอัตราสิ้นเปลืองให้เรียบร้อย')} />
      )}
      <PhotoConfirmSheet draft={photoDraft} busy={busyKey === 'photo'} onClose={() => setPhotoDraft(null)} />
      <ImageLightbox image={zoom} onClose={() => setZoom(null)} />
      <ToastView toast={toast} />
    </>
  )

  // Phase 4: ถ่ายรูป → โชว์ thumbnail ยืนยัน → ค่อยส่งจริง (ผ่านคิว offline ได้)
  const captureThen = async (label, send) => {
    const img = await pickImage()
    if (!img) return
    setPhotoDraft({
      label, dataUrl: img,
      confirm: () => run('photo', async () => { await send(img); setPhotoDraft(null) }),
    })
  }

  // ปุ่มเบิกเงิน (ทุกสถานะ) + SOS (เฉพาะตอนมีทริปวิ่ง) + แจ้งเหตุรถมีปัญหา (เฉพาะตอนรองาน/ขาว)
  const actionRow = (
    <div className="grid gap-2 grid-cols-2">
      {/* ⛽ บันทึกเติมน้ำมัน — เฉพาะช่วงกำลังวิ่งงาน (🟠/🟢) · ล็อกเมื่อทริปถูกพักจาก SOS */}
      {active && (
        <button onClick={() => setSheet('refuel')} disabled={active.paused}
          className="col-span-2 py-3.5 rounded-xl bg-white ring-1 ring-slate-300 text-slate-700 text-base font-bold active:scale-[0.98] transition disabled:opacity-40 disabled:cursor-not-allowed">
          ⛽ บันทึกเติมน้ำมัน
        </button>
      )}
      <button onClick={() => setSheet('advance')}
        className="py-3.5 rounded-xl bg-white ring-1 ring-blue-300 text-blue-600 text-base font-bold active:scale-[0.98] transition">
        💵 ขอเบิกเงินล่วงหน้า
      </button>
      {active ? (
        <button onClick={() => setSheet('sos')}
          className="py-3.5 rounded-xl bg-red-50 ring-1 ring-red-300 text-red-600 text-base font-bold active:scale-[0.98] transition">
          🆘 แจ้งเหตุฉุกเฉิน
        </button>
      ) : (
        // สถานะรองาน (ขาว): แจ้งรถมีปัญหา → ตั้งรถเป็น "กำลังซ่อม"
        <button onClick={() => setSheet('issue')}
          className="py-3.5 rounded-xl bg-amber-50 ring-1 ring-amber-300 text-amber-700 text-base font-bold active:scale-[0.98] transition">
          🔧 แจ้งเหตุ/ตรวจพบปัญหา
        </button>
      )}
    </div>
  )

  /* ---------- ⚪ WHITE: รองาน ---------- */
  if (!active) {
    return (
      <div className="max-w-md mx-auto space-y-4 pt-10 fadein">
        {netBadge}
        <div className="text-center">
          <div className="text-6xl mb-4">🛌</div>
          <div className="text-xl font-bold text-slate-700">รองาน</div>
          <div className="text-sm text-slate-400 mt-2 mb-6">ยังไม่มีเที่ยววิ่งที่ได้รับมอบหมาย<br />เมื่อคนคุมงานจ่ายงาน สถานะจะเปลี่ยนเป็น 🟠 อัตโนมัติ</div>
        </div>
        {actionRow}
        {sheets}
      </div>
    )
  }

  const s = STATUS[active.status]
  const allowanceTotal = active.drops.reduce((sm, d) => sm + d.allowance, 0)
  // 1 ขาต่อครั้ง: คนขับเห็นเฉพาะ "งานล่าสุด" ที่คนคุมงานเพิ่งจ่ายมา (ขาที่ยังไม่ส่ง seq มากสุด)
  // ขาถัดไปจะโผล่ก็ต่อเมื่อคนคุมงานจ่ายงานย่อยใบใหม่เท่านั้น
  const currentLeg = [...active.drops].filter((d) => !d.delivered).sort((a, b) => a.seq - b.seq).pop()
  const legNo = currentLeg ? currentLeg.seq : active.drops.length

  // 🚨 ป้ายเตือนทริปถูกพัก (SOS ค้าง) — ล็อกทุกปุ่มเดินหน้า
  const pausedBanner = active.paused && (
    <div className="bg-red-600 text-white rounded-2xl p-4 text-center shadow-lg">
      <div className="text-lg font-extrabold">🚨 ทริปถูกพักชั่วคราว (แจ้งเหตุฉุกเฉินแล้ว)</div>
      <div className="text-sm mt-1 text-red-100">รอคนคุมงาน/แอดมินปิดเหตุ จึงจะทำรายการต่อได้</div>
    </div>
  )

  /* ---------- 🟠 ORANGE: ตรวจสภาพรถ → ขึ้นของเสร็จ ---------- */
  if (active.status === 'ORANGE') {
    const showForm = !active.paused && (!inspection || (inspection.status === 'REJECTED' && reinspect))
    return (
      <div className="max-w-md mx-auto space-y-4 fadein">
        {netBadge}
        <TripHeader trip={active} s={s} allowanceTotal={allowanceTotal} />
        {pausedBanner}
        {/* งานปัจจุบัน 1 ใบเท่านั้น — ขาถัดไปจะโผล่เมื่อคนคุมงานจ่ายงานใหม่ */}
        <div className="bg-orange-50 ring-1 ring-orange-200 rounded-2xl p-5 text-center">
          <div className="text-sm text-orange-700 font-medium mb-1">📦 งานที่ต้องทำตอนนี้ (ขาที่ {legNo})</div>
          <div className="text-lg font-bold text-slate-700 py-0.5">
            {currentLeg ? (currentLeg.origin || '—') : '—'}
            <span className="text-orange-500 mx-1.5">➜</span>
            {currentLeg ? (currentLeg.destination || currentLeg.name) : '—'}
          </div>
          {currentLeg && (
            <div className="mt-2 inline-block rounded-lg bg-emerald-50 ring-1 ring-emerald-200 px-3 py-1.5">
              <span className="text-sm font-bold text-emerald-700">💰 เบี้ยเลี้ยงขานี้ {money(currentLeg.allowance)}</span>
              {currentLeg.revenue > 0 && (
                <span className="text-[11px] text-slate-500 ml-2">
                  ({money(currentLeg.revenue)} × {(DIFFICULTY[currentLeg.difficulty]?.rate * 100 || 0).toFixed(0)}% · {DIFFICULTY[currentLeg.difficulty]?.th})
                </span>
              )}
            </div>
          )}
          <div className="text-xs text-orange-500 mt-2">🔔 อย่าลืมเตรียมคลุมผ้าใบก่อนออกรถ!</div>
        </div>

        {/* ---- ด่านตรวจสภาพรถ (ข้อ 1.2) ---- */}
        {showForm && (
          <InspectionCard busy={busyKey === 'inspect'}
            onSubmit={({ items, defect_note, defect_photo_b64, odometer_start, odometer_photo_b64 }) =>
              run('inspect', async () => {
                const res = await submitInspection.mutateAsync({
                  tripId: active.id, items, defect_note, defect_photo_b64,
                  odometer_start, odometer_photo_b64,
                })
                setReinspect(false)
                notify(res.data?.status === 'PASSED' || Object.values(items).every(Boolean)
                  ? `✅ ตรวจรถผ่าน + บันทึกเลขไมล์ ${odometer_start.toLocaleString('th-TH')} กม. — เริ่มงานได้เลย!`
                  : '📨 ส่งจุดชำรุดให้คนคุมงานประเมินแล้ว — รอผลอนุมัติ')
              })} />
        )}
        {inspection?.status === 'PENDING_REVIEW' && (
          <div className="bg-amber-50 ring-1 ring-amber-300 rounded-2xl p-4 text-center">
            <div className="text-base font-bold text-amber-700">⏳ พบจุดชำรุด — รอคนคุมงานประเมิน</div>
            <div className="text-xs text-amber-600 mt-1">เมื่ออนุมัติแล้ว ปุ่มเริ่มงานจะปลดล็อกอัตโนมัติ</div>
          </div>
        )}
        {inspection?.status === 'REJECTED' && !reinspect && (
          <div className="bg-red-50 ring-1 ring-red-300 rounded-2xl p-4 text-center space-y-2">
            <div className="text-base font-bold text-red-700">🚫 ไม่ผ่านการประเมิน — ห้ามวิ่ง</div>
            <div className="text-xs text-red-500">{inspection.defect_note || 'ติดต่อคนคุมงาน แล้วตรวจสภาพรถใหม่หลังแก้ไข'}</div>
            <button onClick={() => setReinspect(true)}
              className="w-full py-3 rounded-xl bg-red-500 hover:bg-red-600 text-white font-bold active:scale-[0.98] transition">
              🔧 แก้ไขแล้ว — ตรวจสภาพรถอีกครั้ง
            </button>
          </div>
        )}
        {inspectionOk && (
          <div className="bg-emerald-50 ring-1 ring-emerald-300 rounded-xl px-4 py-2.5 text-center text-sm font-bold text-emerald-700">
            ✅ ตรวจสภาพรถผ่านแล้ว{inspection.status === 'APPROVED' ? ' (คนคุมงานอนุมัติ)' : ''}
          </div>
        )}

        {/* ---- ปุ่มขึ้นของเสร็จ — ล็อกจนกว่าตรวจรถผ่าน (ข้อกำหนด 3A-2) ---- */}
        <button
          disabled={busyKey === 'load' || !inspectionOk || active.paused || isQueued(`/trips/${active.id}/finish-loading`)}
          onClick={async () => {
            // เลขไมล์เริ่ม + รูปหน้าปัดถูกบันทึกไปแล้วตอนส่งผลตรวจสภาพรถ — ที่นี่เหลือแค่ GPS ต้นทาง
            const gps = await getGps()
            run('load', () => finishLoading.mutateAsync({ tripId: active.id, ...gps }),
              '📍 บันทึก GPS ต้นทางแล้ว → สถานะ 🟢 กำลังไปส่ง')
          }}
          className="w-full py-5 rounded-2xl bg-emerald-500 hover:bg-emerald-600 active:scale-[0.98] transition text-white text-xl font-bold shadow-lg disabled:opacity-40 disabled:cursor-not-allowed">
          {busyKey === 'load' ? '⏳ กำลังบันทึก…'
            : isQueued(`/trips/${active.id}/finish-loading`) ? '🕓 บันทึกแล้ว — รอส่งเมื่อเน็ตกลับ'
            : inspectionOk ? '✅ ขึ้นของเสร็จแล้ว' : '🔒 ขึ้นของเสร็จแล้ว'}
        </button>
        {!inspectionOk && !active.paused && (
          <div className="text-center text-sm font-bold text-red-600 -mt-2">
            ⚠️ กรุณาตรวจสภาพรถให้ผ่านก่อนเริ่มงาน
          </div>
        )}
        <div className="text-center text-[11px] text-slate-400">
          เลขไมล์เริ่มถูกบันทึกตอนส่งผลตรวจสภาพรถแล้ว · กดแล้วระบบบันทึกพิกัด GPS ต้นทางอัตโนมัติ
        </div>
        {actionRow}
        {sheets}
      </div>
    )
  }

  /* ---------- 🟢 GREEN: กำลังไปส่ง (งานปัจจุบัน 1 ใบ + 4 ปุ่มหลักฐาน) ---------- */
  const locked = active.paused // SOS ค้าง — ล็อกปุ่มหลักฐานทุกจุด
  return (
    <div className="max-w-md mx-auto space-y-4 fadein">
      {netBadge}
      <TripHeader trip={active} s={s} allowanceTotal={allowanceTotal} />
      {pausedBanner}
      <div className="text-sm font-semibold text-emerald-700 text-center">
        ส่งรูป “ส่งของสำเร็จ” ของขานี้ แล้วจะกลับเป็น “รองาน” ทันที
        <div className="text-xs font-normal text-slate-400 mt-0.5">ขาถัดไปจะขึ้นให้เมื่อคนคุมงานจ่ายงานใหม่</div>
      </div>

      {/* งานปัจจุบันใบเดียว — ขาที่ส่งไปแล้วไม่ต้องโชว์ให้คนขับอีก */}
      {(currentLeg ? [currentLeg] : []).map((d) => {
        // นับ "รอส่ง" (คิวออฟไลน์) เป็นส่งแล้วบน UI — กันคนขับกดซ้ำระหว่างรอเน็ต
        const qKind = (k) => pending.some((p) => p.url === `/drops/${d.id}/receipt` && p.body?.kind === k)
        const hasFuel = d.receipts.some((r) => r.kind === 'FUEL') || qKind('FUEL')
        const hasToll = d.receipts.some((r) => r.kind === 'TOLL') || qKind('TOLL')
        const qTarp = isQueued(`/drops/${d.id}/tarp`)
        const qDlv = isQueued(`/drops/${d.id}/delivery`)
        return (
          <div key={d.id} className={`rounded-2xl p-4 ring-1 shadow-sm ${d.delivered ? 'bg-slate-50 ring-slate-200 opacity-70' : 'bg-white ring-emerald-200'}`}>
            <div className="flex items-center justify-between mb-3">
              <div className="font-bold text-slate-800 text-base">
                {d.delivered ? '✅' : '📍'} จุด {d.seq}: {d.origin || '—'}
                <span className="text-orange-500 mx-1">➜</span>{d.destination || d.name}
              </div>
              <div className="text-right">
                <div className="text-sm font-bold text-emerald-700">{money(d.allowance)}</div>
                {d.revenue > 0 && (
                  <div className="text-[10px] text-slate-400">
                    {money(d.revenue)} × {(DIFFICULTY[d.difficulty]?.rate * 100 || 0).toFixed(0)}%
                  </div>
                )}
              </div>
            </div>
            {d.delivered ? (
              <div className="flex items-center gap-2">
                <div className="text-xs text-slate-400 flex-1">ส่งสำเร็จแล้ว · 🛰 {d.gps}</div>
                <PhotoThumb src={d.photo} label="รูปส่งของ" onZoom={setZoom} size="w-10 h-10" />
                <PhotoThumb src={d.tarp} label="ผ้าใบ" onZoom={setZoom} size="w-10 h-10" />
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                {/* 1) บิลน้ำมัน — OCR อ่านยอดเป็น Draft */}
                <EvidenceBtn icon="⛽" label={hasFuel ? 'ส่งบิลน้ำมันแล้ว' : 'บิลน้ำมัน'} done={hasFuel}
                  busy={busyKey === `fuel-${d.id}`} disabled={locked}
                  onClick={() => captureThen(`⛽ บิลน้ำมัน จุด ${d.seq}`, async (img) => {
                    const amt = mockOcr('FUEL')
                    await uploadReceipt.mutateAsync({ dropId: d.id, kind: 'FUEL', ocr_amount: amt, photo_b64: img })
                    notify(`🤖 OCR อ่านบิลน้ำมัน ${money(amt)} — Draft รอคนคุมงานยืนยัน`)
                  })} />
                {/* 2) บิลทางหลวง */}
                <EvidenceBtn icon="🛣️" label={hasToll ? 'ส่งบิลทางหลวงแล้ว' : 'บิลทางหลวง'} done={hasToll}
                  busy={busyKey === `toll-${d.id}`} disabled={locked}
                  onClick={() => captureThen(`🛣️ บิลทางหลวง จุด ${d.seq}`, async (img) => {
                    const amt = mockOcr('TOLL')
                    await uploadReceipt.mutateAsync({ dropId: d.id, kind: 'TOLL', ocr_amount: amt, photo_b64: img })
                    notify(`🤖 OCR อ่านบิลทางหลวง ${money(amt)} — Draft รอคนคุมงานยืนยัน`)
                  })} />
                {/* 3) รูปผ้าใบ (soft — ไม่บังคับก่อนวิ่ง) */}
                <EvidenceBtn icon="🖼️" label={qTarp ? 'รูปผ้าใบ (รอส่ง)' : d.tarp ? 'ส่งรูปผ้าใบแล้ว' : 'รูปผ้าใบ'}
                  done={d.tarp || qTarp}
                  busy={busyKey === `tarp-${d.id}`} disabled={locked}
                  onClick={() => captureThen(`🖼️ รูปผ้าใบ จุด ${d.seq}`, async (img) => {
                    await uploadTarp.mutateAsync({ dropId: d.id, photo_b64: img })
                    notify(`🖼️ อัปโหลดรูปผ้าใบจุด ${d.seq} สำเร็จ`)
                  })} />
                {/* 4) รูปส่งของสำเร็จ + GPS ปลายทาง */}
                <EvidenceBtn icon={qDlv ? '🕓' : '📸'} label={qDlv ? 'ส่งของสำเร็จ (รอส่ง)' : 'ส่งของสำเร็จ'} accent
                  done={qDlv}
                  busy={busyKey === `dlv-${d.id}`} disabled={locked}
                  onClick={() => captureThen(`📸 รูปส่งของสำเร็จ จุด ${d.seq}`, async (img) => {
                    const gps = await getGps()
                    await delivery.mutateAsync({ dropId: d.id, ...gps, photo_b64: img })
                    notify(`📍 ขาที่ ${d.seq} ส่งสำเร็จ! กลับเป็น "รองาน" — รอคนคุมงานจ่ายงานถัดไป`)
                  })} />
              </div>
            )}
          </div>
        )
      })}
      {/* 🧭 บันทึกเลขไมล์ปลายเที่ยว — ใช้คิดระยะทาง/อัตราสิ้นเปลืองรวมของทั้งเที่ยว
           การ "จบเที่ยว" จริงเป็นหน้าที่คนคุมงาน ไม่ใช่ปุ่มนี้ */}
      <button disabled={locked}
        onClick={() => setEndTarget({ id: active.id, code: active.code, odometer_start: active.odometer_start })}
        className="w-full py-4 rounded-2xl bg-slate-800 hover:bg-slate-900 text-white text-lg font-bold shadow active:scale-[0.98] transition disabled:opacity-40 disabled:cursor-not-allowed">
        🧭 บันทึกเลขไมล์ปลายเที่ยว
      </button>
      {actionRow}
      {sheets}
    </div>
  )
}

/* ---------- ส่วนประกอบย่อย ---------- */
function TripHeader({ trip, s, allowanceTotal }) {
  return (
    <div className={`rounded-2xl ring-2 ${s.ring} ${s.color} p-4 shadow-sm`}>
      <div className="flex items-center justify-between">
        <div className="text-lg font-bold text-slate-800">{trip.code}</div>
        <StatusPill status={trip.status} />
      </div>
      <div className="text-sm text-slate-500 mt-1">🚛 {trip.plate || '—'} · เบี้ยเลี้ยงรวม {money(allowanceTotal)}</div>
    </div>
  )
}

function EvidenceBtn({ icon, label, onClick, done, busy, accent, disabled }) {
  return (
    <button onClick={onClick} disabled={done || busy || disabled}
      className={`py-3.5 rounded-xl text-sm font-semibold active:scale-[0.97] transition flex flex-col items-center gap-1 ${
        done ? 'bg-slate-100 text-slate-400'
          : accent ? 'bg-emerald-500 hover:bg-emerald-600 text-white shadow'
          : 'bg-white ring-1 ring-slate-300 text-slate-700 hover:bg-slate-50'
      } disabled:cursor-not-allowed disabled:opacity-50`}>
      <span className="text-2xl">{busy ? '⏳' : done ? '✔' : icon}</span>
      {label}
    </button>
  )
}

function ToastView({ toast }) {
  if (!toast) return null
  return (
    <div className={`fixed bottom-20 inset-x-4 z-[60] text-sm text-white px-4 py-3 rounded-xl shadow-lg text-center fadein ${
      toast.kind === 'red' ? 'bg-red-500' : toast.kind === 'amber' ? 'bg-amber-500' : 'bg-slate-800'}`}>
      {toast.msg}
    </div>
  )
}
