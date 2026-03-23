import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Don't protect the password page, auth API, or static assets
  if (
    pathname === "/password" ||
    pathname === "/tracker/password" ||
    pathname.startsWith("/api/auth") ||
    pathname.startsWith("/tracker/api/auth") ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/tracker/_next") ||
    pathname.includes(".")
  ) {
    return NextResponse.next();
  }

  const authCookie = request.cookies.get("tracker_auth");
  if (authCookie?.value === "authenticated") {
    return NextResponse.next();
  }

  const url = request.nextUrl.clone();
  url.pathname = "/password";
  return NextResponse.redirect(url);
}
