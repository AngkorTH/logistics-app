// axios instance กลาง — แนบ JWT อัตโนมัติ + ดักจับ 401 (session ถูกดีด/token หมดอายุ)
import axios from 'axios'

export const TOKEN_KEY = 'logi_token'
export const USER_KEY = 'logi_user'

export const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 401 = token ใช้ไม่ได้แล้ว (หมดอายุ หรือโดน Single-Session ดีดออก) → ล้างแล้วส่งกลับหน้า login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err.response?.status
    const url = err.config?.url || ''
    const isLogin = url.includes('/auth/login')
    // 401 = token ใช้ไม่ได้ (หมดอายุ/โดนดีด) → ล้าง+กลับ login
    // 403 = สิทธิ์ไม่พอ/บัญชีถูกระงับ → บังคับ logout กลับ login ทันที (ตาม requirement)
    if ((status === 401 || status === 403) && !isLogin) {
      const detail = err.response?.data?.detail || ''
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
      if (detail.includes('อุปกรณ์อื่น')) sessionStorage.setItem('logi_kicked', detail)
      else if (status === 403) sessionStorage.setItem('logi_kicked', detail || 'สิทธิ์การเข้าถึงไม่เพียงพอ — กรุณาเข้าสู่ระบบใหม่')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

// ดึงข้อความ error ภาษาไทยจาก response ของ FastAPI
export const errMsg = (err, fallback = 'เกิดข้อผิดพลาด') =>
  err?.response?.data?.detail || fallback
