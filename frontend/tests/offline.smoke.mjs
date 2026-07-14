// Smoke test: Offline Queue + Sync Service (Phase 3B)
// รัน: node tests/offline.smoke.mjs (ใช้ fake-indexeddb จำลอง IndexedDB)
import 'fake-indexeddb/auto'
import assert from 'node:assert/strict'
import { queueAll, queueCount } from '../src/offline/offlineQueue.js'
import { configureSender, sendOrQueue, flushQueue } from '../src/offline/syncService.js'

// จำลอง navigator.onLine สลับได้
let onLine = false
Object.defineProperty(globalThis, 'navigator', {
  value: { get onLine() { return onLine } },
  configurable: true,
})

const sentLog = []
let failMode = null // null | 'network' | 400 | 500
configureSender(async (method, url, body) => {
  if (failMode === 'network') { const e = new Error('Network Error'); throw e }
  if (typeof failMode === 'number') { const e = new Error(`HTTP ${failMode}`); e.response = { status: failMode }; throw e }
  sentLog.push({ method, url, body })
  return { data: 'ok' }
})

const t0 = Date.now()

// ---------- 1) ออฟไลน์: sendOrQueue ต้องเข้าคิว + ประทับ captured_at ณ ตอนกด ----------
onLine = false
const r1 = await sendOrQueue({ url: '/drops/1/delivery', body: { lat: 13.8, lng: 100.6 }, label: 'ส่งของ' })
assert.equal(r1.queued, true)
const r2 = await sendOrQueue({ url: '/drops/1/tarp', body: { photo_b64: 'AAAA' }, label: 'ผ้าใบ' })
assert.equal(r2.queued, true)
assert.equal(await queueCount(), 2)

const items = await queueAll()
assert.ok(items[0].body.captured_at, 'ต้องมี captured_at')
const capturedMs = Date.parse(items[0].body.captured_at)
assert.ok(Math.abs(capturedMs - t0) < 5000, 'captured_at ต้องเป็นเวลาตอนกด ไม่ใช่อนาคต')
assert.equal(items[1].body.photo_b64, 'AAAA', 'payload รูป (Base64) ต้องถูกเก็บครบ')
console.log('✅ 1) ออฟไลน์เข้าคิว + captured_at ตอนกด + เก็บ Base64 ได้')

// ---------- 2) ออฟไลน์อยู่: flush ต้องไม่ส่งอะไร ----------
let out = await flushQueue()
assert.equal(out.sent, 0)
assert.equal(await queueCount(), 2)
console.log('✅ 2) ยังออฟไลน์ — flush ไม่ส่ง ของยังอยู่ครบ')

// ---------- 3) เน็ตกลับ: flush ส่งครบตามลำดับที่กด ----------
onLine = true
out = await flushQueue()
assert.equal(out.sent, 2)
assert.equal(await queueCount(), 0)
assert.deepEqual(sentLog.map((s) => s.url), ['/drops/1/delivery', '/drops/1/tarp'], 'ต้องส่งตามลำดับกด')
assert.equal(Date.parse(sentLog[0].body.captured_at), capturedMs, 'เวลาใน payload ต้องเป็นตอนกด ไม่ใช่ตอน sync')
console.log('✅ 3) เน็ตกลับ — ส่งครบตามลำดับ + เวลาเดิมตอนกด')

// ---------- 4) เน็ตล่มกลางทาง (ไม่มี response): เข้าคิวแทน error ----------
failMode = 'network'
const r3 = await sendOrQueue({ url: '/trips/9/finish-loading', body: { lat: 1, lng: 2 } })
assert.equal(r3.queued, true)
assert.equal(await queueCount(), 1)
console.log('✅ 4) เน็ตหลุดกลางทาง — เข้าคิวอัตโนมัติ')

// ---------- 5) flush เจอ 5xx: หยุดรอรอบหน้า (ของไม่หาย) ----------
failMode = 500
out = await flushQueue()
assert.equal(out.sent, 0)
assert.equal(await queueCount(), 1, '5xx ต้องไม่ทิ้งรายการ')
console.log('✅ 5) 5xx — หยุดไว้รอรอบหน้า ของไม่หาย')

// ---------- 6) flush เจอ 4xx (เช่นส่งซ้ำ): ทิ้งรายการแล้วไปต่อ ----------
failMode = 400
out = await flushQueue()
assert.equal(await queueCount(), 0, '4xx = ปฏิเสธถาวร ต้องทิ้งจากคิว')
console.log('✅ 6) 4xx — ทิ้งรายการที่ถูกปฏิเสธถาวร คิวไม่ตัน')

// ---------- 7) ออนไลน์ปกติ: ส่งตรง ไม่เข้าคิว ----------
failMode = null
const r4 = await sendOrQueue({ url: '/drops/2/delivery', body: { lat: 3, lng: 4 } })
assert.equal(r4.queued, false)
assert.equal(await queueCount(), 0)
console.log('✅ 7) ออนไลน์ — ส่งตรงทันที ไม่เข้าคิว')

console.log('\n🎉 Offline Queue + Sync ผ่านทั้ง 7 ข้อ')
