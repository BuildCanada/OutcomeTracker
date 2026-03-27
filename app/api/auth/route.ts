import { NextRequest, NextResponse } from "next/server";

const PASSWORD = "carneys1year";

function secondsUntil6am(): number {
  // Use Mountain Time (America/Edmonton)
  const now = new Date();
  const mt = new Date(
    now.toLocaleString("en-US", { timeZone: "America/Edmonton" }),
  );

  const target = new Date(mt);
  target.setHours(6, 0, 0, 0);

  // If it's already past 6am, target tomorrow's 6am
  if (mt >= target) {
    target.setDate(target.getDate() + 1);
  }

  return Math.floor((target.getTime() - mt.getTime()) / 1000);
}

export async function POST(request: NextRequest) {
  const body = await request.json();

  if (body.password !== PASSWORD) {
    return NextResponse.json({ error: "Wrong password" }, { status: 401 });
  }

  const maxAge = secondsUntil6am();
  const response = NextResponse.json({ success: true });
  response.cookies.set("tracker_auth", "authenticated", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/tracker",
    maxAge,
  });

  return response;
}
