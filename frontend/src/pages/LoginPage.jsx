// หน้า Login — ดีไซน์ตาม prototype (การ์ดขาวบนพื้น gradient slate) แต่ยิง API จริง
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth, homeFor } from '../auth/AuthContext'
import { errMsg } from '../api/client'
import { Btn, Field, inputCls, ROLES } from '../components/ui'

// ปุ่มล็อกอินด่วนสำหรับเดโม (รหัสผ่าน 1234 ตาม seed)
const QUICK = [
  { id: 'D01', role: 'DRIVER' },
  { id: 'SV01', role: 'SUPERVISOR' },
  { id: 'AD01', role: 'ADMIN' },
  { id: 'SA01', role: 'SUPER_ADMIN' },
]

export default function LoginPage() {
  const { login } = useAuth()
  const nav = useNavigate()
  const [ident, setIdent] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  // ข้อความแจ้งถูกดีดออกจาก Single-Session (ตั้งโดย api/client.js ตอนโดน 401)
  const [kicked] = useState(() => {
    const msg = sessionStorage.getItem('logi_kicked')
    sessionStorage.removeItem('logi_kicked')
    return msg || ''
  })

  const doLogin = async (id = ident, pw = password) => {
    if (!id.trim() || !pw) { setErr('กรอกเบอร์โทร/รหัสพนักงาน และรหัสผ่าน'); return }
    setBusy(true); setErr('')
    try {
      const user = await login(id.trim(), pw)
      nav(homeFor(user.role), { replace: true })
    } catch (e) {
      setErr(errMsg(e, 'เข้าสู่ระบบไม่สำเร็จ'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 to-slate-700 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-7 fadein">
        <div className="text-center mb-5">
          <div className="text-2xl font-bold text-slate-800">🚛 Logi<span className="text-orange-500">ERP</span></div>
          <div className="text-xs text-slate-400 mt-1">Driver Management System</div>
        </div>
        {kicked && <div className="text-xs bg-red-50 text-red-600 rounded-lg p-2.5 mb-3">⚠️ {kicked}</div>}
        <form onSubmit={(e) => { e.preventDefault(); doLogin() }}>
          <Field label="เบอร์โทร หรือ รหัสพนักงาน">
            <input className={inputCls} value={ident} autoFocus
              onChange={(e) => { setIdent(e.target.value); setErr('') }}
              placeholder="เช่น 0810000001 หรือ D01" />
          </Field>
          <Field label="รหัสผ่าน">
            <input className={inputCls} type="password" value={password}
              onChange={(e) => { setPassword(e.target.value); setErr('') }}
              placeholder="••••" />
          </Field>
          {err && <div className="text-xs text-red-500 mb-2">{err}</div>}
          <Btn type="submit" color="slate" className="w-full" disabled={busy}>
            {busy ? 'กำลังเข้าสู่ระบบ…' : 'เข้าสู่ระบบ'}
          </Btn>
        </form>
        <div className="mt-5 pt-4 border-t border-slate-100">
          <div className="text-[10px] text-slate-400 mb-2 text-center">— เข้าสู่ระบบด่วน (เดโม · รหัส 1234) —</div>
          <div className="grid grid-cols-2 gap-2">
            {QUICK.map((q) => (
              <button key={q.id} onClick={() => doLogin(q.id, '1234')} disabled={busy}
                className="text-xs border border-slate-200 rounded-lg py-2 hover:bg-slate-50 disabled:opacity-40">
                {ROLES[q.role].icon} {ROLES[q.role].th}
              </button>
            ))}
          </div>
        </div>
        <div className="text-[10px] text-slate-400 text-center mt-4">🔐 1 บัญชี = 1 Session (กันแชร์รหัส)</div>
      </div>
    </div>
  )
}
