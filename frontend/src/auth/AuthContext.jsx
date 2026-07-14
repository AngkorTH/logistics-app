// Auth context — เก็บ JWT + ข้อมูลผู้ใช้ใน localStorage, ให้ทุกหน้าเรียก useAuth() ได้
import { createContext, useContext, useState } from 'react'
import { api, TOKEN_KEY, USER_KEY } from '../api/client'

const AuthCtx = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem(USER_KEY)) } catch { return null }
  })

  const login = async (identifier, password) => {
    const { data } = await api.post('/auth/login', { identifier, password })
    localStorage.setItem(TOKEN_KEY, data.access_token)
    localStorage.setItem(USER_KEY, JSON.stringify(data.user))
    setUser(data.user)
    return data.user
  }

  const logout = async () => {
    try { await api.post('/auth/logout') } catch { /* token อาจหมดอายุแล้ว — ล้าง local ต่อได้เลย */ }
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setUser(null)
  }

  return <AuthCtx.Provider value={{ user, login, logout }}>{children}</AuthCtx.Provider>
}

export const useAuth = () => useContext(AuthCtx)

// หน้าแรกตามสิทธิ์: Driver → mobile UI ของตัวเอง / Supervisor+ → dashboard
export const homeFor = (role) => (role === 'DRIVER' ? '/driver' : '/dashboard')
