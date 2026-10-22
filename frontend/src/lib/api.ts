/**
 * 双模式 API 客户端：
 *  - 后端可达 → 真实请求 FastAPI（前后端分离联调）
 *  - 后端不可达 → 自动切换「演示模式」，由 mock 数据驱动完整 UI
 */
const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) || "http://localhost:8000/api/v1";

let demo: boolean | null = null;
const listeners = new Set<(d: boolean) => void>();

export async function detectDemo(force = false): Promise<boolean> {
  if (demo !== null && !force) return demo;
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 1500);
    const healthUrl = BASE.replace(/\/api\/v1\/?$/, "") + "/health";
    const res = await fetch(healthUrl, { signal: ctrl.signal });
    clearTimeout(timer);
    demo = !res.ok;
  } catch {
    demo = true;
  }
  listeners.forEach((fn) => fn(demo!));
  return demo;
}

export function isDemo(): boolean {
  return demo === true;
}

export function onDemoChange(fn: (d: boolean) => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export const getToken = () => localStorage.getItem("resume_token");
export const setToken = (t: string) => localStorage.setItem("resume_token", t);
export const clearToken = () => {
  localStorage.removeItem("resume_token");
  localStorage.removeItem("resume_admin");
};

/** 当前登录用户是否管理员（登录时由后端响应写入） */
export const isAdmin = () => localStorage.getItem("resume_admin") === "1";
export const setAdmin = (v: boolean) => localStorage.setItem("resume_admin", v ? "1" : "0");

/** 默认请求超时。fetch 本身没有超时：连接挂起时 Promise 永远不 settle，
 *  启动流程会卡在「正在连接服务…」再也出不来。 */
const API_TIMEOUT_MS = 30_000;

/** 401 监听器：令牌中途失效时通知上层（路由守卫）回到登录页。
 *  这里只发通知、不直接跳转 —— api.ts 不持有路由。 */
const unauthorizedListeners = new Set<() => void>();

export function onUnauthorized(fn: () => void): () => void {
  unauthorizedListeners.add(fn);
  return () => unauthorizedListeners.delete(fn);
}

/** 登录/登出通知：App 的路由守卫状态只在启动时求值一次，登录页存好令牌、
 *  布局清掉凭据后必须显式同步过来，否则 navigate("/") 会被仍是 anon 的守卫
 *  原路弹回登录页（登出同理，会被仍是 authed 的守卫弹回应用）。 */
const loginListeners = new Set<() => void>();
const logoutListeners = new Set<() => void>();

export function onLogin(fn: () => void): () => void {
  loginListeners.add(fn);
  return () => loginListeners.delete(fn);
}

export function notifyLogin(): void {
  loginListeners.forEach((fn) => fn());
}

export function onLogout(fn: () => void): () => void {
  logoutListeners.add(fn);
  return () => logoutListeners.delete(fn);
}

export function notifyLogout(): void {
  logoutListeners.forEach((fn) => fn());
}

/** 调用真实后端（统一响应 {code,message,data} 解包） */
export async function api<T = any>(
  path: string, options: RequestInit = {}, timeoutMs = API_TIMEOUT_MS,
): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...options,
      signal: ctrl.signal,
      headers: {
        ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
        ...(options.headers || {}),
      },
    });
  } catch (err) {
    // abort 通常是超时；其他是网络故障。统一成可读错误，别把 TypeError 抛到 UI 上。
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`请求超时（${Math.round(timeoutMs / 1000)} 秒），请检查后端服务`);
    }
    throw new Error("无法连接后端服务，请检查网络或服务状态");
  } finally {
    clearTimeout(timer);
  }

  if (res.status === 401 && !path.startsWith("/auth/")) {
    // 登录/注册接口自己会返回 401（密码错误），不能当成「会话失效」处理。
    // 其余接口 401 = 令牌过期或被清掉：清本地凭据并让路由守卫切回登录页，
    // 否则用户只会看到一连串莫名其妙的「请求失败 (401)」。
    clearToken();
    unauthorizedListeners.forEach((fn) => fn());
    throw new Error("登录已失效，请重新登录");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.message || `请求失败 (${res.status})`);
  }
  const body = await res.json();
  if (body.code !== 0) throw new Error(body.message || "业务错误");
  return body.data as T;
}

/** 下载文件（PDF/报名表）
 *
 * 注意：必须显式传 method。fetch 不指定时默认 GET，而简历导出是 POST 接口，
 * 默认 GET 会拿到 405 Method Not Allowed（后端返回裸 {"detail":...}，前端只能看到状态码）。
 */
export async function apiDownload(path: string, filename: string, options: RequestInit = {}): Promise<void> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    method: options.method || "GET",
    headers: {
      ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
      // 带 body 的请求必须声明 JSON，否则后端 422
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.message || body?.detail || `下载失败 (${res.status})`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** 拉取二进制并生成 Object URL（图片预览等鉴权资源展示） */
export async function apiBlobUrl(path: string): Promise<string> {
  const res = await fetch(`${BASE}${path}`, {
    headers: getToken() ? { Authorization: `Bearer ${getToken()}` } : {},
  });
  if (!res.ok) throw new Error(`加载失败 (${res.status})`);
  return URL.createObjectURL(await res.blob());
}
