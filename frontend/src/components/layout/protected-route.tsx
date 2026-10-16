import { useAuthStore } from '@/stores/auth-store'
import { Navigate, Outlet, useLocation } from 'react-router-dom'

// A session needs both a token and the user it belongs to; a half-cleared
// or hand-edited localStorage entry counts as signed out. An expired token
// is caught by the API client: refresh fails → clearSession → this
// component re-renders and redirects.
const useSignedIn = () => useAuthStore((s) => Boolean(s.accessToken && s.user))

/** Workspace pages: signed-out visitors go to /login, then come back. */
export function ProtectedRoute() {
  const signedIn = useSignedIn()
  const location = useLocation()

  if (!signedIn) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  return <Outlet />
}

/** Login / signup: a signed-in user has nothing to do there. */
export function GuestRoute() {
  const signedIn = useSignedIn()
  const from = (useLocation().state as { from?: Location } | null)?.from?.pathname
  return signedIn ? <Navigate to={from ?? '/workspace'} replace /> : <Outlet />
}
