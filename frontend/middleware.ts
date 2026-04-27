/**
 * Middleware de autenticación — gatea las rutas autenticadas.
 *
 * Usa la presencia del cookie `medicop_session` (httpOnly) como check de
 * sesión. La validez del token se verifica en el backend en cada request.
 * Si la cookie falta, redirige a /login.
 */
import { NextResponse, type NextRequest } from "next/server";

const SESSION_COOKIE = "medicop_session";

const PROTECTED_PREFIXES = ["/dashboard", "/patients", "/consultation"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isProtected = PROTECTED_PREFIXES.some((p) =>
    pathname === p || pathname.startsWith(p + "/"),
  );
  if (!isProtected) {
    return NextResponse.next();
  }

  const session = request.cookies.get(SESSION_COOKIE);
  if (!session) {
    const url = new URL("/login", request.url);
    url.searchParams.set("from", pathname);
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  // Aplica a todo excepto /login, /api, /_next/*, archivos estáticos
  matcher: ["/((?!login|api|_next/static|_next/image|favicon.ico).*)"],
};
