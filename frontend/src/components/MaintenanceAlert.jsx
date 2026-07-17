// 🔧 แถบเตือนรถแจ้งเหตุ/กำลังซ่อม — เด้งบนทุกหน้าของคุมงาน/แอดมินเมื่อมีเหตุ OPEN
// คลิกไปหน้า "จัดการคิวงาน" เพื่อดูรายละเอียด + ปิดเหตุ (ปลดล็อกรถ)
import { Link } from 'react-router-dom'
import { useMaintenanceReports } from '../api/hooks'

export default function MaintenanceAlert() {
  const { data: reports } = useMaintenanceReports('OPEN')
  if (!reports || reports.length === 0) return null

  return (
    <Link to="/dispatch"
      className="block bg-amber-500 hover:bg-amber-600 text-white px-4 py-2.5 text-sm font-bold text-center">
      🔧 มีรถแจ้งเหตุ/กำลังซ่อม {reports.length} คัน — จ่ายงานคันนั้นไม่ได้จนกว่าจะปิดเหตุ · คลิกเพื่อจัดการ
    </Link>
  )
}
