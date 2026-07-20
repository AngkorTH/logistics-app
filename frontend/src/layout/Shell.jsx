// Shell layout — Sidebar (desktop) + TopBar + Bottom nav (mobile) ตาม prototype
import { useState } from 'react'
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { ROLES } from '../components/ui'
import NotificationBell from '../components/NotificationBell'
import SosAlert from '../components/SosAlert'
import MaintenanceAlert from '../components/MaintenanceAlert'

// เมนูตามสิทธิ์ (role-based) — 🚨 Driver เห็นได้แค่ /driver เท่านั้น
// ชุดบริหารทั้งหมด (Dispatch/Users/Vehicles/History) ไม่ปรากฏต่อ Driver เด็ดขาด
const SUP = ['SUPERVISOR', 'ADMIN', 'SUPER_ADMIN']  // Supervisor ขึ้นไป
const ADM = ['ADMIN', 'SUPER_ADMIN']                // Admin ขึ้นไป
const NAV = [
  { path: '/driver',      th: 'งานของฉัน',      icon: '🚚', roles: ['DRIVER'] },
  { path: '/my-history',  th: 'ประวัติของฉัน',  icon: '📅', roles: ['DRIVER'] },
  { path: '/dashboard',   th: 'แดชบอร์ด',       icon: '📊', roles: SUP },
  { path: '/dispatch',    th: 'จัดการคิวงาน',   icon: '🚦', roles: SUP },
  { path: '/pending-review', th: 'รอตรวจ',      icon: '🗒️', roles: SUP },
  { path: '/approvals',   th: 'คิวอนุมัติ',     icon: '✅', roles: SUP },
  // ข้อ 3.1: "ประวัติรวม" เป็น Hub เดียว — ประวัติทริป/ประวัติการแก้/ประวัติหักเงิน ย้ายเข้าไปอยู่ข้างใน
  { path: '/master-history', th: 'ประวัติรวม',  icon: '🗂️', roles: SUP },
  { path: '/users',       th: 'จัดการพนักงาน',  icon: '👥', roles: ADM },
  { path: '/vehicles',    th: 'คลังรถยนต์',     icon: '🚙', roles: ADM },
  { path: '/corrections', th: 'คำขอแก้ไข',      icon: '🔓', roles: ['SUPER_ADMIN'] },
]

const TITLE = {
  '/driver': 'งานของฉัน',
  '/my-history': 'ประวัติงานและเงินของฉัน',
  '/dashboard': 'แดชบอร์ด — ภาพรวม',
  '/dispatch': 'จัดการคิวงาน (Smart Dispatch)',
  '/pending-review': 'รอตรวจ — ทริปที่รอยืนยันความถูกต้อง',
  '/approvals': 'คิวอนุมัติ — SOS / ตรวจสภาพรถ / เบิกเงินล่วงหน้า',
  '/master-history': 'ประวัติรวม — ทริป / การแก้ไข / หักเงิน',
  '/history': 'ประวัติทริปรายเดือน',
  '/penalties': 'ประวัติและสรุปการหักเงิน',
  '/users': 'จัดการพนักงาน',
  '/vehicles': 'คลังรถยนต์',
  '/admin-audit-log': 'Audit Log — ประวัติเหตุการณ์',
  '/corrections': 'คำขอปลดล็อกการเงิน',
}

export default function Shell() {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  const { pathname } = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const visibleNav = NAV.filter((n) => n.roles.includes(user.role))

  const doLogout = async () => { await logout(); nav('/login', { replace: true }) }

  return (
    <div className="min-h-screen flex bg-slate-100">
      {/* SIDEBAR */}
      <aside className={`fixed md:static z-40 inset-y-0 left-0 w-60 bg-slate-900 text-slate-300 flex flex-col transition-transform ${sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}>
        <div className="px-5 py-5 border-b border-slate-800">
          <div className="font-bold text-white text-lg">🚛 Logi<span className="text-orange-400">ERP</span></div>
          <div className="text-[10px] text-slate-500 mt-0.5">Driver Management System</div>
        </div>
        <nav className="flex-1 py-3 overflow-y-auto">
          {visibleNav.map((n) => (
            <NavLink key={n.path} to={n.path} onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                `w-full flex items-center gap-3 px-5 py-2.5 text-sm ${isActive ? 'bg-slate-800 text-white border-l-2 border-orange-400' : 'hover:bg-slate-800/50'}`}>
              <span>{n.icon}</span><span>{n.th}</span>
            </NavLink>
          ))}
        </nav>
        <div className="px-5 py-3 border-t border-slate-800 text-[10px] text-slate-500">
          🔐 Single Session · 1 อุปกรณ์/บัญชี
        </div>
      </aside>
      {sidebarOpen && <div className="fixed inset-0 bg-black/30 z-30 md:hidden" onClick={() => setSidebarOpen(false)}></div>}

      {/* MAIN */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-white border-b border-slate-200 px-4 md:px-6 py-3 flex items-center justify-between gap-3 sticky top-0 z-20">
          <div className="flex items-center gap-3 min-w-0">
            <button className="md:hidden text-slate-500 text-xl" onClick={() => setSidebarOpen(true)}>☰</button>
            <div className="min-w-0">
              <h1 className="font-bold text-slate-800 text-lg truncate">{TITLE[pathname] || 'LogiERP'}</h1>
              <div className="text-xs text-slate-400 truncate">{pathname}</div>
            </div>
          </div>
          <div className="flex items-center gap-2 md:gap-3">
            {SUP.includes(user.role) && <NotificationBell />}
            <div className="hidden sm:block text-right">
              <div className="text-sm font-medium text-slate-700">{user.name}</div>
              <div className="text-[10px] text-slate-400">{ROLES[user.role].icon} {ROLES[user.role].th}</div>
            </div>
            <button onClick={doLogout} className="w-9 h-9 rounded-full bg-slate-800 text-white text-sm font-bold" title="ออกจากระบบ">
              {user.name[0]}
            </button>
          </div>
        </header>

        {/* 🚨 Alert แดง SOS + 🔧 รถแจ้งเหตุ/กำลังซ่อม — เห็นเฉพาะทีมบริหาร (Supervisor+) */}
        {SUP.includes(user.role) && <SosAlert />}
        {SUP.includes(user.role) && <MaintenanceAlert />}

        <main className="flex-1 overflow-y-auto p-4 md:p-6 pb-20 md:pb-6">
          <Outlet />
        </main>

        {/* MOBILE BOTTOM NAV */}
        <nav className="md:hidden fixed bottom-0 inset-x-0 bg-white border-t border-slate-200 flex justify-around py-1.5 z-20">
          {visibleNav.slice(0, 5).map((n) => (
            <NavLink key={n.path} to={n.path}
              className={({ isActive }) =>
                `flex flex-col items-center text-[10px] px-2 py-1 ${isActive ? 'text-orange-500' : 'text-slate-400'}`}>
              <span className="text-lg">{n.icon}</span>{n.th}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  )
}
