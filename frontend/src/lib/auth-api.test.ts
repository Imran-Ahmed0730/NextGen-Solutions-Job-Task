import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { apiRequest } from './auth-api';

describe('apiRequest session refresh', () => {
  beforeEach(() => {
    sessionStorage.clear();
    sessionStorage.setItem('access_token', 'expired-access');
    sessionStorage.setItem('refresh_token', 'current-refresh');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('shares one refresh between concurrent unauthorized requests', async () => {
    let resolveRefresh: ((response: Response) => void) | undefined;
    let markRefreshStarted: (() => void) | undefined;
    const refreshStarted = new Promise<void>((resolve) => {
      markRefreshStarted = resolve;
    });
    const refreshResponse = new Promise<Response>((resolve) => {
      resolveRefresh = resolve;
    });
    let refreshCount = 0;
    const requestCounts = new Map<string, number>();

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL): Promise<Response> => {
        const url = String(input);
        if (url.endsWith('/api/v1/auth/refresh')) {
          refreshCount += 1;
          markRefreshStarted?.();
          return refreshResponse;
        }

        const count = (requestCounts.get(url) ?? 0) + 1;
        requestCounts.set(url, count);
        if (count === 1) return new Response(null, { status: 401 });
        return new Response('{"ok":true}', { status: 200 });
      }),
    );

    const first = apiRequest<{ ok: boolean }>('/resource/first');
    const second = apiRequest<{ ok: boolean }>('/resource/second');
    await refreshStarted;
    expect(refreshCount).toBe(1);

    if (!resolveRefresh) throw new Error('Refresh response was not initialized');
    resolveRefresh(
      new Response(
        JSON.stringify({
          access_token: 'new-access',
          refresh_token: 'new-refresh',
          token_type: 'bearer',
          expires_in: 3600,
        }),
        { status: 200 },
      ),
    );

    await expect(Promise.all([first, second])).resolves.toEqual([{ ok: true }, { ok: true }]);
    expect(refreshCount).toBe(1);
    expect(sessionStorage.getItem('access_token')).toBe('new-access');
    expect(sessionStorage.getItem('refresh_token')).toBe('new-refresh');
  });
});
