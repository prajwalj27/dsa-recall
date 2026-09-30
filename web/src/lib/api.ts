/** Minimal fetch wrapper for the FastAPI backend (proxied to /api in dev). */
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    throw new Error(`${init?.method ?? 'GET'} /api${path} failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export type Health = { status: string; version: string }
