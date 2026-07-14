// Image helpers (Phase 4) — เปิดกล้อง/เลือกรูปจากเครื่อง แล้วย่อเป็น Base64 (JPEG)
// ย่อรูปฝั่ง client ก่อนเข้าคิว offline เสมอ: กัน IndexedDB/payload บวม และไม่ชนลิมิต 8MB ของ backend

const MAX_DIM = 1280   // ด้านยาวสุดหลังย่อ (พอสำหรับซูมดูใบเสร็จ/จุดชำรุด)
const QUALITY = 0.72

/** เปิดกล้องหลัง (มือถือ) หรือ file picker → คืน dataURL (jpeg ย่อแล้ว) หรือ null ถ้ายกเลิก */
export function pickImage() {
  return new Promise((resolve) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'image/*'
    input.capture = 'environment' // มือถือ: เปิดกล้องหลังทันที · เดสก์ท็อป: file picker ปกติ
    input.onchange = async () => {
      const file = input.files?.[0]
      if (!file) return resolve(null)
      try {
        resolve(await downscaleToDataUrl(file))
      } catch {
        resolve(null)
      }
    }
    // Safari ต้องอยู่ใน DOM ตอน click
    input.style.display = 'none'
    document.body.appendChild(input)
    input.click()
    setTimeout(() => input.remove(), 60000)
  })
}

/** ย่อรูปด้วย canvas → dataURL image/jpeg */
export function downscaleToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(url)
      const scale = Math.min(1, MAX_DIM / Math.max(img.width, img.height))
      const canvas = document.createElement('canvas')
      canvas.width = Math.round(img.width * scale)
      canvas.height = Math.round(img.height * scale)
      canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height)
      resolve(canvas.toDataURL('image/jpeg', QUALITY))
    }
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('อ่านไฟล์รูปไม่ได้')) }
    img.src = url
  })
}

/** URL รูปนี้เป็นไฟล์จริงที่เปิดดูได้ไหม (ข้อมูลเก่าเป็น marker "attached" เปิดไม่ได้) */
export const isViewable = (src) =>
  !!src && (src.startsWith('/uploads/') || src.startsWith('data:image/'))
