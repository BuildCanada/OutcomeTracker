"use client";

import { SWRConfig } from "swr";

async function fetcher(...args: Parameters<typeof fetch>) {
  const [url, ...restArgs] = args;
  const options = restArgs[0] || {};
  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  return (await fetch(url, { ...options, headers })).json();
}

export default function SWRProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  return <SWRConfig value={{ fetcher }}>{children}</SWRConfig>;
}
