/**
 * Cliente HTTP para la API MediCop.
 *
 * Seguridad:
 * - `credentials: "include"` envía la cookie httpOnly `medicop_session`.
 * - NO se almacena el JWT en localStorage/sessionStorage (inmune a XSS).
 * - Timeout duro de 30 s (60 s para upload de audio y generación LLM).
 * - 401 dispara redirect a /login (sesión expirada o revocada).
 */
import { ApiError } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const DEFAULT_TIMEOUT_MS = 30_000;

interface RequestOptions extends Omit<RequestInit, "body"> {
  json?: unknown;
  formData?: FormData;
  timeout?: number;
}

async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { json, formData, timeout = DEFAULT_TIMEOUT_MS, headers, ...rest } = options;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  const finalHeaders: Record<string, string> = {
    Accept: "application/json",
    ...(headers as Record<string, string> | undefined),
  };

  let body: BodyInit | undefined;
  if (json !== undefined) {
    finalHeaders["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (formData !== undefined) {
    body = formData;
    // No fijar Content-Type — el browser pone el boundary del multipart.
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...rest,
      headers: finalHeaders,
      body,
      credentials: "include",
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timer);
    if ((err as Error).name === "AbortError") {
      throw new ApiError(408, "La solicitud tardó demasiado y fue cancelada");
    }
    throw new ApiError(0, "No se pudo conectar con el servidor");
  } finally {
    clearTimeout(timer);
  }

  // Sesión expirada / revocada → redirect a login (solo en cliente)
  if (res.status === 401 && typeof window !== "undefined") {
    if (!window.location.pathname.startsWith("/login")) {
      window.location.href = "/login?expired=1";
    }
  }

  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text();
    }
    const message =
      typeof detail === "object" && detail !== null && "detail" in detail
        ? String((detail as { detail: unknown }).detail)
        : `Error ${res.status}`;
    throw new ApiError(res.status, message, detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return res.json() as Promise<T>;
  }
  return res.text() as Promise<T>;
}

export const apiClient = {
  get: <T>(path: string, options?: RequestOptions) =>
    apiFetch<T>(path, { method: "GET", ...options }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiFetch<T>(path, { method: "POST", json: body, ...options }),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiFetch<T>(path, { method: "PATCH", json: body, ...options }),
  delete: <T>(path: string, options?: RequestOptions) =>
    apiFetch<T>(path, { method: "DELETE", ...options }),
  upload: <T>(path: string, formData: FormData, options?: RequestOptions) =>
    apiFetch<T>(path, { method: "POST", formData, timeout: 120_000, ...options }),
};
