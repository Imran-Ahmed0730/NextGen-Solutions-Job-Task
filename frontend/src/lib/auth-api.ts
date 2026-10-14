const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export function getApiUrl(path: string): string {
  return `${API_URL}${path}`;
}

export type SessionTokens = {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_in: number;
};

export type Profile = {
  id: number;
  username: string;
  email: string | null;
  mobile: string | null;
  full_name: string;
  roles: string[];
  permissions: string[];
};

export function storeSession(tokens: SessionTokens) {
  sessionStorage.setItem('access_token', tokens.access_token);
  sessionStorage.setItem('refresh_token', tokens.refresh_token);
}

export function clearSession() {
  sessionStorage.removeItem('access_token');
  sessionStorage.removeItem('refresh_token');
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

let refreshInFlight: Promise<SessionTokens | null> | null = null;

function refreshSession(): Promise<SessionTokens | null> {
  if (!refreshInFlight) {
    const refreshToken = sessionStorage.getItem('refresh_token');
    if (!refreshToken) return Promise.resolve(null);

    refreshInFlight = fetch(getApiUrl('/api/v1/auth/refresh'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
      .then(async (response) => {
        if (!response.ok) {
          clearSession();
          return null;
        }
        const tokens = (await response.json()) as SessionTokens;
        storeSession(tokens);
        return tokens;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  options: { authenticated?: boolean; retry?: boolean } = {},
): Promise<T> {
  const authenticated = options.authenticated ?? true;
  const headers = new Headers(init.headers);
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  let accessToken: string | null = null;
  if (authenticated) {
    accessToken = sessionStorage.getItem('access_token');
    if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  }

  let response = await fetch(getApiUrl(path), { ...init, headers });
  if (
    response.status === 401 &&
    authenticated &&
    options.retry !== false &&
    !path.endsWith('/refresh')
  ) {
    const latestAccessToken = sessionStorage.getItem('access_token');
    if (latestAccessToken && latestAccessToken !== accessToken) {
      headers.set('Authorization', `Bearer ${latestAccessToken}`);
      response = await fetch(`${API_URL}${path}`, { ...init, headers });
    } else {
      const tokens = await refreshSession();
      if (tokens) {
        headers.set('Authorization', `Bearer ${tokens.access_token}`);
        response = await fetch(`${API_URL}${path}`, { ...init, headers });
      } else {
        clearSession();
      }
    }
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === 'string') message = payload.detail;
      else if (payload.detail) message = JSON.stringify(payload.detail);
    } catch {
      message = `Request failed (${response.status})`;
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
