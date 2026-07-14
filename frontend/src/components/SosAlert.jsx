// 🚨 SOS Alert แดง (ข้อ 1.4) — เด้งบนทุกหน้าของคนคุมงาน/แอดมินทันทีที่มีเหตุ OPEN
// poll ผ่าน useIncidents ทุก 10 วิ · คลิกแล้วพาไปหน้า "คิวอนุมัติ" เพื่อจัดการ
import { Link } from 'react-router-dom'
import { useIncidents } from '../api/hooks'

export default function SosAlert() {
  const { data: incidents } = useIncidents('OPEN')
  if (!incidents || incidents.length === 0) return null

  return (
    <Link to="/approvals"
      className="block bg-red-600 hover:bg-red-700 text-white px-4 py-2.5 text-sm font-bold text-center animate-pulse">
      🚨 มีเหตุฉุกเฉิน {incidents.length} รายการ! ทริปถูกพักอยู่ — คลิกเพื่อดูรายละเอียดและปิดเหตุ
    </Link>
  )
}
