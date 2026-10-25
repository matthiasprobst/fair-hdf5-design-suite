import { isRecord } from './validation';

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

let csrfToken = '';
export function setCsrfToken(token: string) {
  csrfToken = token;
}

export async function request(url: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.method && !['GET', 'HEAD'].includes(init.method)) headers.set('X-CSRF-Token', csrfToken);
  const response = await fetch(url, { ...init, headers, credentials: 'same-origin' });
  if (response.ok) return response;
  let message = `Request failed (HTTP ${response.status})`,
    code = 'request_failed';
  try {
    const body: unknown = await response.json();
    if (isRecord(body)) {
      if (typeof body.detail === 'string') message = body.detail;
      if (typeof body.code === 'string') code = body.code;
    }
  } catch {
    /* Preserve the HTTP status for non-JSON failures. */
  }
  if (response.status === 401 && !url.startsWith('/api/auth/'))
    window.dispatchEvent(new Event('fair:session-expired'));
  throw new ApiError(response.status, code, message);
}

export async function jsonRequest(
  url: string,
  method = 'GET',
  body?: unknown,
  headers?: HeadersInit,
  signal?: AbortSignal,
): Promise<unknown> {
  return (
    await request(url, {
      method,
      headers: { 'Content-Type': 'application/json', ...headers },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    })
  ).json();
}
