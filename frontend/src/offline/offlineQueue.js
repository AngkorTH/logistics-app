// Offline Queue — IndexedDB wrapper กลาง (Phase 3B ข้อ 1.1)
// เก็บ request ที่ส่งไม่ได้ตอนออฟไลน์ รอ syncService flush เมื่อเน็ตกลับ
// รองรับ payload ทุกชนิดที่ structured-clone ได้: JSON, Base64 string และ Blob (รูปถ่าย)
const DB_NAME = 'logi_offline'
const STORE = 'queue'
const VERSION = 1

const idbFactory = () => globalThis.indexedDB

function openDB() {
  return new Promise((resolve, reject) => {
    const req = idbFactory().open(DB_NAME, VERSION)
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) {
        req.result.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

// รัน 1 operation บน object store แล้วปิด DB ให้เรียบร้อย
async function withStore(mode, fn) {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE, mode)
    const request = fn(t.objectStore(STORE))
    t.oncomplete = () => { db.close(); resolve(request?.result) }
    t.onerror = () => { db.close(); reject(t.error) }
    t.onabort = () => { db.close(); reject(t.error) }
  })
}

/** เพิ่มรายการเข้าคิว — item: { method, url, body, label } · คืน id */
export const queueAdd = (item) =>
  withStore('readwrite', (s) => s.add({ ...item, queuedAt: new Date().toISOString() }))

/** รายการทั้งหมดในคิว (เรียงตามลำดับที่กด — id autoIncrement) */
export const queueAll = () => withStore('readonly', (s) => s.getAll())

/** ลบรายการที่ส่งสำเร็จ/ทิ้งแล้วออกจากคิว */
export const queueRemove = (id) => withStore('readwrite', (s) => s.delete(id))

/** จำนวนรายการค้างส่ง */
export const queueCount = () => withStore('readonly', (s) => s.count())
