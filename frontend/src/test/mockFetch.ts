import { vi } from "vitest";

type JsonValue = unknown;

type FetchHandler = (url: URL, init?: RequestInit) => { status?: number; body: JsonValue };

export function installFetchMock(handler: FetchHandler): { calls: URL[] } {
  const calls: URL[] = [];
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const raw = typeof input === "string" ? input : input.toString();
    const url = new URL(raw);
    calls.push(url);
    const response = handler(url, init);
    const status = response.status ?? 200;
    return {
      ok: status >= 200 && status < 300,
      status,
      async json() {
        return response.body;
      },
      async text() {
        return JSON.stringify(response.body);
      },
    } as Response;
  });
  vi.stubGlobal("fetch", mock);
  return { calls };
}
