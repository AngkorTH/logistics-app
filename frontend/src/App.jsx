// Role-Based Routing — Login → redirect ตามสิทธิ์ / กันเข้าหน้าที่ role ไม่มีสิทธิ์
import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth, homeFor } from './auth/AuthContext'
import { api } from './api/client'
import { configureSender, initSync } from './offline/syncService'
import { initRealtime } from './realtime/socket'
import Shell from './layout/Shell'
import LoginPage from './pages/LoginPage'
import DriverHome from './pages/DriverHome'
import MyHistoryPage from './pages/MyHistoryPage'
import Dashboard from './pages/Dashboard'
import DispatchPage from './pages/DispatchPage'
import UsersPage from './pages/UsersPage'
import VehiclesPage from './pages/VehiclesPage'
import HistoryPage from './pages/HistoryPage'
import PenaltyPage from './pages/PenaltyPage'
import AuditLogPage from './pages/AuditLogPage'
import PendingReviewPage from './pages/PendingReviewPage'
import ApprovalsPage from './pages/ApprovalsPage'
import MasterHistoryPage from './pages/MasterHistoryPage'

const SUP = ['SUPERVISOR', 'ADMIN', 'SUPER_ADMIN']
const ADM = ['ADMIN', 'SUPER_ADMIN']

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

// การ์ด route: ยังไม่ login → /login · role ไม่อยู่ในลิสต์ → เด้งกลับหน้าแรกของตัวเอง
function Protected({ roles, children }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  if (roles && !roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />
  return children
}

function AppRoutes() {
  const { user } = useAuth()
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to={homeFor(user.role)} replace /> : <LoginPage />} />
      <Route element={<Protected><Shell /></Protected>}>
        <Route path="/driver" element={<Protected roles={['DRIVER']}><DriverHome /></Protected>} />
        {/* ประวัติงาน+เงินของคนขับเอง — backend ปล่อยให้ดูได้เฉพาะ id ตัวเอง */}
        <Route path="/my-history" element={<Protected roles={['DRIVER']}><MyHistoryPage /></Protected>} />
        <Route path="/dashboard" element={<Protected roles={SUP}><Dashboard /></Protected>} />
        <Route path="/dispatch" element={<Protected roles={SUP}><DispatchPage /></Protected>} />
        <Route path="/pending-review" element={<Protected roles={SUP}><PendingReviewPage /></Protected>} />
        <Route path="/approvals" element={<Protected roles={SUP}><ApprovalsPage /></Protected>} />
        <Route path="/master-history" element={<Protected roles={SUP}><MasterHistoryPage /></Protected>} />
        <Route path="/history" element={<Protected roles={SUP}><HistoryPage /></Protected>} />
        <Route path="/penalties" element={<Protected roles={SUP}><PenaltyPage /></Protected>} />
        <Route path="/admin-audit-log" element={<Protected roles={ADM}><AuditLogPage /></Protected>} />
        <Route path="/users" element={<Protected roles={ADM}><UsersPage /></Protected>} />
        <Route path="/vehicles" element={<Protected roles={ADM}><VehiclesPage /></Protected>} />
      </Route>
      <Route path="*" element={<Navigate to={user ? homeFor(user.role) : '/login'} replace />} />
    </Routes>
  )
}

export default function App() {
  // Offline Auto-Sync (Phase 3B): ฉีด axios ให้ syncService + ดัก online/offline
  // เมื่อ flush คิวสำเร็จ → refresh ข้อมูลทริปทั้งหมดให้ UI ตรงกับ backend
  useEffect(() => {
    configureSender((method, url, body) => api[method](url, body))
    initSync({ flushed: () => queryClient.invalidateQueries() })
    // Realtime (Phase 5): backend ยิง event ตอนข้อมูลเปลี่ยน → invalidate เฉพาะ topic นั้น
    // แทน polling เดิมทั้งหมด · ต่อติดใหม่ = invalidate ทั้งหมดหนึ่งครั้ง (เก็บตกช่วงออฟไลน์)
    initRealtime((msg) => {
      if (msg.event === 'connected') queryClient.invalidateQueries()
      if (msg.event === 'invalidate') {
        msg.topics?.forEach((t) => queryClient.invalidateQueries({ queryKey: [t] }))
      }
    })
  }, [])

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
