// Sync Service — จุดเดียวที่จัดการ Offline Auto-Sync (Phase 3B ข้อ 1.1)
//
// หลักการ:
// - sendOrQueue(): ประทับ captured_at = "วินาทีที่กดปุ่มจริง" เสมอ แล้วพยายามส่ง
//   ถ้าออฟไลน์/เน็ตล่ม → เก็บเข้าคิว IndexedDB (รวมรูป Base64/Blob ได้)
// - flushQueue(): ไล่ส่งคิวตามลำดับที่กด · error เครือข่าย/5xx = หยุดรอรอบหน้า
//   · 4xx = ข้อมูลถูกปฏิเสธถาวร (เช่นส่งซ้ำ) → ทิ้งจากคิวแล้วไปต่อ
// - ดักจับ event 'online' ให้ flush อัตโนมัติทันทีที่เน็ตกลับ
//
// component ห้ามคุย IndexedDB เอง — ใช้ผ่านไฟล์นี้เท่านั้น
import { queueAdd, queueAll, queueRemove } from './offlineQueue.js'

let sender = null            // (method, url, body) => Promise — ฉีดจาก App (axios) หรือ mock ในเทสต์
let onFlushed = null         // callback หลัง flush สำเร็จ ≥1 รายการ (เช่น invalidate react-query)
const listeners = new Set()  // subscriber ของสถานะคิว (ใช้โดย useOffline)

export const configureSender = (fn) => { sender = fn }
export const isOnline = () => (typeof navigator === 'undefined' ? true : navigator.onLine)

export const subscribe = (fn) => {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

async function notify() {
  const pending = await queueAll()
  const state = { online: isOnline(), pending }
  listeners.forEach((fn) => fn(state))
  return state
}

/**
 * ส่ง request ทันทีถ้าออนไลน์ — ออฟไลน์/เน็ตล่มให้เก็บคิวไว้ส่งภายหลัง
 * คืน { queued: true } เมื่อเข้าคิว หรือ { queued: false, res } เมื่อส่งสำเร็จ
 * body จะถูกแนบ captured_at = เวลากดจริง เสมอ (backend ใช้เป็น timestamp ของข้อมูล)
 */
export async function sendOrQueue({ method = 'post', url, body = {}, label = '' }) {
  const payload = { ...body, captured_at: new Date().toISOString() }
  if (!isOnline()) {
    await queueAdd({ method, url, body: payload, label })
    await notify()
    return { queued: true }
  }
  try {
    const res = await sender(method, url, payload)
    return { queued: false, res }
  } catch (e) {
    if (!e.response) {
      // ไม่มี response = ปัญหาเครือข่าย (เน็ตหลุดกลางทาง) → เข้าคิว
      await queueAdd({ method, url, body: payload, label })
      await notify()
      return { queued: true }
    }
    throw e // 4xx/5xx ตอนออนไลน์ = business error ปกติ ให้ caller แสดงข้อความ
  }
}

let flushing = false

/** ไล่ส่งคิวทั้งหมดตามลำดับ — คืน { sent, left } */
export async function flushQueue() {
  if (flushing || !sender || !isOnline()) return { sent: 0, left: (await queueAll()).length }
  flushing = true
  let sent = 0
  try {
    const items = await queueAll()
    for (const item of items) {
      try {
        await sender(item.method, item.url, item.body)
        await queueRemove(item.id)
        sent++
      } catch (e) {
        if (e.response && e.response.status >= 400 && e.response.status < 500) {
          // ถูกปฏิเสธถาวร (เช่น ส่งซ้ำ/ข้อมูลตกยุค) — ทิ้งรายการนี้แล้วไปต่อ
          await queueRemove(item.id)
        } else {
          break // เครือข่าย/5xx — หยุดไว้รอ flush รอบถัดไป
        }
      }
    }
  } finally {
    flushing = false
  }
  const state = await notify()
  if (sent > 0 && onFlushed) onFlushed(sent)
  return { sent, left: state.pending.length }
}

/** เรียกครั้งเดียวตอนแอปเริ่ม — ดัก online/offline + flush ของค้างจากรอบก่อน */
export function initSync({ flushed } = {}) {
  onFlushed = flushed || null
  window.addEventListener('online', () => { flushQueue() })
  window.addEventListener('offline', () => { notify() })
  flushQueue() // มีของค้างจาก session ก่อน → ส่งเลยถ้าออนไลน์
}
