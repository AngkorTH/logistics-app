// react-query hooks — จุดเดียวที่คุยกับ Backend (Trips / Evidence / Finance / Correction)
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import { sendOrQueue } from '../offline/syncService'

// ---------- Trips ----------
export const useTrips = () =>
  useQuery({ queryKey: ['trips'], queryFn: () => api.get('/trips').then((r) => r.data) })

export const useTrip = (id) =>
  useQuery({ queryKey: ['trips', id], queryFn: () => api.get(`/trips/${id}`).then((r) => r.data), enabled: !!id })

// helper: mutation ที่พอสำเร็จให้ refresh ข้อมูลทริป + คิวจ่ายงาน (สถานะคนขับคำนวณจากทริป)
const useTripMutation = (fn) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trips'] })
      qc.invalidateQueries({ queryKey: ['dispatch'] })  // คิวงานอิงสถานะทริป ต้อง refresh ด้วย
    },
  })
}

// ---------- ฟอร์มจ่ายงาน (สร้างทริป + meta) ----------
export const useDrivers = () =>
  useQuery({ queryKey: ['drivers'], queryFn: () => api.get('/trips/meta/drivers').then((r) => r.data) })
export const useVehicles = () =>
  useQuery({ queryKey: ['vehicles'], queryFn: () => api.get('/trips/meta/vehicles').then((r) => r.data) })
export const useCreateTrip = () =>
  useTripMutation(({ driver_id, distance_km, drops }) => api.post('/trips', { driver_id, distance_km, drops }))

// ---------- State machine ----------
// ข้อ 2.1: จ่ายงานไม่ต้องส่ง plate — backend ดึงจากคลังรถที่ผูกคนขับอัตโนมัติ
export const useAssign = () =>
  useTripMutation(({ tripId, difficulty, force }) =>
    api.post(`/trips/${tripId}/assign`, { difficulty, force }))
// ปุ่มฝั่งคนขับใช้ sendOrQueue — ออฟไลน์แล้วเก็บคิว IndexedDB ส่งเองเมื่อเน็ตกลับ (Phase 3B)
export const useFinishLoading = () =>
  useTripMutation(({ tripId, lat, lng, force }) =>
    sendOrQueue({ url: `/trips/${tripId}/finish-loading`, body: { lat, lng, force }, label: '✅ ขึ้นของเสร็จ' }))
// task 1: เปลี่ยนสถานะทริปแบบ Manual — บังคับ reason (invalidate dispatch ด้วย)
export const useOverrideStatus = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ tripId, status, reason }) => api.post(`/trips/${tripId}/override-status`, { status, reason }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['trips'] }); qc.invalidateQueries({ queryKey: ['dispatch'] }) },
  })
}
export const useCloseTrip = () =>
  useTripMutation(({ tripId, force }) => api.post(`/trips/${tripId}/close`, { lat: 0, lng: 0, force }))
// ปลดล็อกการเงิน (Supervisor/Admin) — บังคับ reason · เด้งแจ้งเตือน
export const useUnfreeze = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ tripId, reason }) => api.post(`/trips/${tripId}/unfreeze`, { reason }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['trips'] }); qc.invalidateQueries({ queryKey: ['notifications'] }) },
  })
}

// ---------- Evidence ----------
export const useUploadReceipt = () =>
  useTripMutation(({ dropId, kind, ocr_amount, ocr_date, photo_b64 }) =>
    sendOrQueue({
      url: `/drops/${dropId}/receipt`, body: { kind, ocr_amount, ocr_date, photo_b64 },
      label: kind === 'FUEL' ? '⛽ บิลน้ำมัน' : '🛣️ บิลทางหลวง',
    }))
export const useApproveReceipt = () =>
  useTripMutation(({ receiptId, amount }) => api.post(`/receipts/${receiptId}/approve`, { amount }))
// task 2: แก้ยอดเงิน OCR แบบ manual — บังคับ new_amount + reason
export const useEditReceiptAmount = () =>
  useTripMutation(({ receiptId, new_amount, reason }) => api.patch(`/receipts/${receiptId}/amount`, { new_amount, reason }))
export const useUploadTarp = () =>
  useTripMutation(({ dropId, photo_b64 }) =>
    sendOrQueue({ url: `/drops/${dropId}/tarp`, body: { photo_b64 }, label: '🖼️ รูปผ้าใบ' }))
export const useRecordDelivery = () =>
  useTripMutation(({ dropId, lat, lng, photo_b64 }) =>
    sendOrQueue({ url: `/drops/${dropId}/delivery`, body: { lat, lng, photo_b64 }, label: '📸 ส่งของสำเร็จ' }))

// ---------- Pre-trip Inspection (ข้อ 1.2) ----------
export const useInspection = (tripId) =>
  useQuery({
    queryKey: ['inspection', tripId],
    queryFn: () => api.get(`/trips/${tripId}/inspection`).then((r) => r.data),
    enabled: !!tripId,
    // Phase 5: ผลประเมินมาถึงผ่าน realtime WS topic ['inspection'] — ปุ่มปลดล็อกทันที
  })
export const useSubmitInspection = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ tripId, items, defect_note, defect_photo_b64 }) =>
      api.post(`/trips/${tripId}/inspection`, { items, defect_note, defect_photo_b64 }),
    onSuccess: (_, { tripId }) => qc.invalidateQueries({ queryKey: ['inspection', tripId] }),
  })
}

// ---------- Advance Payment (ข้อ 1.3) ----------
export const useAdvances = () =>
  useQuery({
    queryKey: ['advances'],
    queryFn: () => api.get('/advances').then((r) => r.data),
    // Phase 5: ผลอนุมัติมาถึงผ่าน realtime WS topic ['advances']
  })
export const useRequestAdvance = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ amount, reason }) => api.post('/advances', { amount, reason }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['advances'] }),
  })
}

// ---------- SOS / Incident (ข้อ 1.4) ----------
export const useSos = () =>
  useTripMutation(({ tripId, kind, message, lat, lng, photo_b64 }) =>
    sendOrQueue({ url: `/trips/${tripId}/sos`, body: { kind, message, lat, lng, photo_b64 }, label: '🆘 แจ้งเหตุฉุกเฉิน' }))

// ---------- ฝั่งคุมงาน/แอดมิน (Phase 3C) ----------
// แท็บ "รอตรวจ" (ข้อ 2.2): ทริปที่คนขับส่งงานจบ รอล็อกการเงิน — backend เรียงเก่า→ใหม่ให้แล้ว
export const usePendingReview = () =>
  useQuery({
    queryKey: ['pending-review'],
    queryFn: () => api.get('/trips/pending-review').then((r) => r.data),
    // Phase 5: realtime WS topic ['pending-review']
  })
// รายการตรวจสภาพรถรอประเมิน (จุดชำรุด)
export const usePendingInspections = () =>
  useQuery({
    queryKey: ['inspections-pending'],
    queryFn: () => api.get('/inspections/pending').then((r) => r.data),
    // Phase 5: realtime WS topic ['inspections-pending']
  })
export const useReviewInspection = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, approve, note }) => api.post(`/inspections/${id}/review`, { approve, note }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['inspections-pending'] }),
  })
}
// เหตุฉุกเฉิน (SOS) — poll ถี่หน่อยเพื่อให้ alert แดงเด้งไว
export const useIncidents = (status) =>
  useQuery({
    queryKey: ['incidents', status],
    queryFn: () =>
      api.get('/incidents', { params: status ? { status_filter: status } : undefined }).then((r) => r.data),
    // Phase 5: 🚨 SOS มาถึงผ่าน realtime WS topic ['incidents'] — เร็วกว่า poll 10 วิเดิม
  })
export const useResolveIncident = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, note }) => api.post(`/incidents/${id}/resolve`, { note }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['incidents'] }); qc.invalidateQueries({ queryKey: ['trips'] }) },
  })
}
// ตัดสินคำขอเบิกเงิน (Supervisor+)
export const useDecideAdvance = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, approve }) => api.post(`/advances/${id}/${approve ? 'approve' : 'reject'}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['advances'] }),
  })
}

// ---------- Finance ----------
export const usePenalty = () =>
  useTripMutation(({ tripId, amount, reason }) => api.post(`/trips/${tripId}/penalty`, { amount, reason }))
export const useBonus = () =>
  useTripMutation(({ tripId, amount }) => api.post(`/trips/${tripId}/bonus`, { amount }))

// ---------- Trip Adjustment (แก้ข้อมูลทริป — บังคับ edit_reason) ----------
// payload: { tripId, edit_reason, distance_km?, difficulty?, bonus?, penalty?, penalty_reason?, allowances? }
export const useAdjustTrip = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ tripId, ...body }) => api.patch(`/trips/${tripId}/adjust`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trips'] })
      qc.invalidateQueries({ queryKey: ['penalties'] })
    },
  })
}

// ---------- Correction ----------
export const useCorrections = () =>
  useQuery({ queryKey: ['corrections'], queryFn: () => api.get('/corrections').then((r) => r.data) })
export const useRequestCorrection = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ tripId, field_key, new_val, reason }) => api.post(`/trips/${tripId}/corrections`, { field_key, new_val, reason }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['corrections'] }),
  })
}
export const useDecideCorrection = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, action, reason }) => api.post(`/corrections/${id}/${action}`, { reason }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['corrections'] }); qc.invalidateQueries({ queryKey: ['trips'] }) },
  })
}

// ==================== Management Suite (Supervisor/Admin — Driver เข้าไม่ได้) ====================

// ---------- Smart Dispatch Queue ----------
// q = คำค้น (ชื่อคนขับ/ทะเบียนรถ) — ส่งเป็น query param ?q= ให้ backend กรอง
export const useDispatchQueue = (q = '') =>
  useQuery({
    queryKey: ['dispatch', q],
    queryFn: () => api.get('/dispatch/queue', { params: q ? { q } : undefined }).then((r) => r.data),
    // Phase 5: ไม่ poll แล้ว — realtime WS invalidate ['dispatch'] ให้ทันทีที่มีการเปลี่ยนแปลง
    refetchOnWindowFocus: true,    // กลับมาโฟกัสแท็บ → refresh (กันพลาดช่วง WS หลุด)
  })

// ---------- Penalty (หลายรายการ) ----------
// filters = { driver_name, month, year } → ส่งเป็น query params ให้ backend กรอง
export const usePenaltyList = (filters = {}) =>
  useQuery({
    queryKey: ['penalties', filters],
    queryFn: () => {
      const params = {}
      if (filters.driver_name) params.driver_name = filters.driver_name
      if (filters.month) params.month = filters.month
      if (filters.year) params.year = filters.year
      return api.get('/penalties', { params }).then((r) => r.data)
    },
  })
export const useAddPenalty = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ tripId, amount, reason }) => api.post(`/trips/${tripId}/penalties`, { amount, reason }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['penalties'] }); qc.invalidateQueries({ queryKey: ['trips'] }) },
  })
}

// ---------- Notifications (กล่องจดหมายบริหาร) ----------
export const useNotifications = ({ unread = false } = {}) =>
  useQuery({
    queryKey: ['notifications', unread],
    queryFn: () => api.get('/notifications', { params: unread ? { unread: true } : undefined }).then((r) => r.data),
    // Phase 5: กระดิ่งอัปเดตผ่าน realtime WS topic ['notifications'] แทน polling
  })
export const useMarkNotifRead = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, all }) => (all ? api.post('/notifications/read-all') : api.post(`/notifications/${id}/read`)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  })
}

// ---------- Deduction Leaderboard (task 3) ----------
export const useLeaderboard = ({ month, year } = {}) =>
  useQuery({
    queryKey: ['leaderboard', month, year],
    queryFn: () => {
      const params = {}
      if (month) params.month = month
      if (year) params.year = year
      return api.get('/penalties/leaderboard', { params }).then((r) => r.data)
    },
  })

// ---------- Audit Log (task 5, Admin+) ----------
// "ประวัติการแก้" (ข้อ 3.1) — กรองด้วย ใคร(who)/เดือน/ปี เพิ่มได้
export const useAuditLogs = ({ action, target, who, month, year } = {}) =>
  useQuery({
    queryKey: ['audit-logs', action, target, who, month, year],
    queryFn: () => {
      const params = {}
      if (action) params.action = action
      if (target) params.target = target
      if (who) params.who = who
      if (month) params.month = month
      if (year) params.year = year
      return api.get('/audit-logs', { params }).then((r) => r.data)
    },
  })

// ---------- User Management + Rating ----------
export const useUsers = () =>
  useQuery({ queryKey: ['users'], queryFn: () => api.get('/users').then((r) => r.data) })
export const useUpdateUser = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...patch }) => api.patch(`/users/${id}`, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}
export const useRateDriver = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, rating }) => api.post(`/users/${id}/rating`, { rating }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['users'] }); qc.invalidateQueries({ queryKey: ['dispatch'] }) },
  })
}
// ประวัติทริปรายเดือน — ส่ง year+month เพิ่ม → backend คืน trips[] (ตารางรายเที่ยว)
// enabled: ต้องมี userId เสมอ · flow ใหม่บังคับกด "ยืนยัน" ก่อน (ตั้ง enabled=false จนกดยืนยัน)
export const useMonthlyHistory = (userId, { year, month, enabled = true } = {}) =>
  useQuery({
    queryKey: ['history', userId, year, month],
    queryFn: () => {
      const params = {}
      if (year) params.year = year
      if (month) params.month = month
      return api.get(`/users/${userId}/history/monthly`, { params }).then((r) => r.data)
    },
    enabled: !!userId && enabled,
  })

// ---------- Vehicle Assignment ----------
export const useVehiclesAdmin = () =>
  useQuery({ queryKey: ['vehicles-admin'], queryFn: () => api.get('/vehicles').then((r) => r.data) })
export const useCreateVehicle = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ plate, model, std_km_l }) => api.post('/vehicles', { plate, model, std_km_l }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['vehicles-admin'] }),
  })
}
export const useAssignVehicle = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, driver_id }) => api.post(`/vehicles/${id}/assign`, { driver_id }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['vehicles-admin'] }),
  })
}
