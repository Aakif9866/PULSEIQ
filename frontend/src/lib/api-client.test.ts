import { apiClient, ApiError, newRequestId, REQUEST_ID_HEADER } from '@/lib/api-client'
import { afterEach, describe, expect, it, vi } from 'vitest'

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('request ids', () => {
  it('sends a fresh X-Request-ID on every request', async () => {
    // A fresh Response per call — a body can only be read once.
    const fetchMock = vi.fn().mockImplementation(async () => jsonResponse(200, { ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await apiClient.get('/a')
    await apiClient.get('/b')

    const ids = fetchMock.mock.calls.map(([, init]) => init.headers[REQUEST_ID_HEADER])
    expect(ids[0]).toMatch(UUID_V4)
    expect(ids[1]).toMatch(UUID_V4)
    expect(ids[0]).not.toBe(ids[1])
  })

  it("puts the server's echoed request id on the ApiError", async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(500, { detail: 'Something went wrong.' }, { 'X-Request-ID': 'server-id-1' }),
      ),
    )

    const error = await apiClient.get('/boom').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).requestId).toBe('server-id-1')
    expect((error as ApiError).message).toBe('Something went wrong.')
  })

  it('falls back to the id it sent when the response carries none', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(502, { detail: 'Bad gateway' }))
    vi.stubGlobal('fetch', fetchMock)

    const error = (await apiClient.get('/x').catch((e: unknown) => e)) as ApiError
    const sent = fetchMock.mock.calls[0][1].headers[REQUEST_ID_HEADER]
    expect(error.requestId).toBe(sent)
  })

  it('still builds a valid v4 UUID where crypto.randomUUID is unavailable (plain http)', () => {
    // Captured before stubbing — after stubGlobal, globalThis.crypto IS
    // the stub, and delegating to it would recurse forever.
    const realCrypto = globalThis.crypto
    vi.stubGlobal('crypto', {
      getRandomValues: (arr: Uint8Array<ArrayBuffer>) => realCrypto.getRandomValues(arr),
    })
    // The stub above has no randomUUID — the insecure-context case.
    expect(newRequestId()).toMatch(UUID_V4)
  })
})
