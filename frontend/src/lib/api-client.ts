import { useAuthStore } from '@/stores/auth-store'

const API_BASE_URL = import.meta.env.VITE_API_URL ?? '/api/v1'

// Sent on every request and echoed back by the backend
// (app/core/middleware.py), so an error a user sees in the browser and
// the server's log lines / trace for it share one id — the "frontend"
// end of docs/PHASES.md Phase 8 step 5's request-id threading.
export const REQUEST_ID_HEADER = 'X-Request-ID'

export function newRequestId(): string {
  // crypto.randomUUID only exists in secure contexts (https, localhost);
  // getRandomValues works everywhere, so fall back to building a v4 UUID
  // from it rather than dropping correlation over plain http.
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

export class ApiError extends Error {
  status: number
  detail?: unknown
  /** The id the server logged this request under — shown to the user as
   * a reference they can quote. Prefers the server's echo; falls back to
   * the id this client sent (e.g. a network error with no response). */
  requestId?: string

  constructor(status: number, message: string, detail?: unknown, requestId?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.requestId = requestId
  }
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
  auth?: boolean
}

async function request<T>(path: string, { body, auth = true, headers, ...init }: RequestOptions = {}): Promise<T> {
  const token = auth ? useAuthStore.getState().accessToken : null
  // FormData bodies (file uploads) must keep the browser-generated
  // multipart Content-Type (with boundary) — never JSON-encode or override it.
  const isFormData = body instanceof FormData
  const requestId = newRequestId()

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      [REQUEST_ID_HEADER]: requestId,
      ...headers,
    },
    body: isFormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (response.status === 401 && auth) {
    useAuthStore.getState().clearSession()
  }

  if (!response.ok) {
    let detail: unknown
    try {
      detail = await response.json()
    } catch {
      detail = undefined
    }
    const message =
      detail && typeof detail === 'object' && 'detail' in detail
        ? String((detail as { detail: unknown }).detail)
        : `Request failed with status ${response.status}`
    throw new ApiError(
      response.status,
      message,
      detail,
      response.headers.get(REQUEST_ID_HEADER) ?? requestId,
    )
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

export const apiClient = {
  get: <T>(path: string, options?: RequestOptions) => request<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'POST', body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'PUT', body }),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'PATCH', body }),
  delete: <T>(path: string, options?: RequestOptions) => request<T>(path, { ...options, method: 'DELETE' }),
  upload: <T>(path: string, formData: FormData, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'POST', body: formData }),
}
