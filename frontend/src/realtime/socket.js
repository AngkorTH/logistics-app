// Realtime client (Phase 5) — รับ event 'invalidate' จาก backend ผ่าน WebSocket
// แทนระบบ polling เดิม: backend ยิงสัญญาณตอนข้อมูลเปลี่ยน → UI refetch ทันทีครั้งเดียว
//
// - auth ด้วย JWT ตัวเดิมผ่าน query string (?token=)
// - หลุด/ยังไม่ login → reconnect อัตโนมัติแบบ exponential backoff (สูงสุด 30 วิ)
// - ต่อสำเร็จ → ส่ง event 'connected' ให้ caller invalidate ทั้งหมดหนึ่งครั้ง (เก็บตกช่วงหลุด)
import { TOKEN_KEY } from '../api/client'

let ws = null
let retry = 0
let handler = null

const wsUrl = () => {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/ws?token=${localStorage.getItem(TOKEN_KEY) || ''}`
}

function connect() {
  if (!localStorage.getItem(TOKEN_KEY)) return scheduleRetry() // ยังไม่ login — รอแล้วลองใหม่
  try {
    ws = new WebSocket(wsUrl())
  } catch {
    return scheduleRetry()
  }
  ws.onopen = () => { retry = 0; handler?.({ event: 'connected' }) }
  ws.onmessage = (e) => {
    try { handler?.(JSON.parse(e.data)) } catch { /* ข้าม frame ที่ parse ไม่ได้ */ }
  }
  ws.onclose = () => { ws = null; scheduleRetry() }
  ws.onerror = () => { try { ws?.close() } catch { /* ปิดไปแล้ว */ } }
}

function scheduleRetry() {
  const delay = Math.min(30000, 1000 * 2 ** Math.min(retry++, 5))
  setTimeout(connect, delay)
}

/** เรียกครั้งเดียวตอนแอปเริ่ม — onEvent รับ {event:'connected'} และ {event:'invalidate', topics:[..]} */
export function initRealtime(onEvent) {
  handler = onEvent
  connect()
}
