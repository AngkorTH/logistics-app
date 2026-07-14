// useOffline — hook อ่านสถานะออนไลน์/คิวค้างส่ง (แสดง Badge บนหน้าคนขับ)
import { useEffect, useState } from 'react'
import { queueAll } from './offlineQueue'
import { isOnline, subscribe } from './syncService'

export function useOffline() {
  const [state, setState] = useState({ online: isOnline(), pending: [] })

  useEffect(() => {
    let live = true
    const refresh = () =>
      queueAll().then((pending) => live && setState({ online: isOnline(), pending }))

    refresh()
    const unsub = subscribe((s) => live && setState(s))
    window.addEventListener('online', refresh)
    window.addEventListener('offline', refresh)
    return () => {
      live = false
      unsub()
      window.removeEventListener('online', refresh)
      window.removeEventListener('offline', refresh)
    }
  }, [])

  return state // { online: bool, pending: [{id, method, url, body, label, queuedAt}] }
}
