"use client";

import posthog from "posthog-js";
import type { CaptureResult } from "posthog-js";
import { PostHogProvider as PHProvider, usePostHog } from "posthog-js/react";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, Suspense } from "react";

// Third-party embeds (for example HubSpot) throw their own uncaught errors.
// Exception autocapture reports these, but they are not app bugs. Drop any
// exception whose every stack frame comes from one of these hosts.
const THIRD_PARTY_ERROR_HOSTS = ["hscollectedforms.net", "hs-scripts.com"];

function isThirdPartyException(event: CaptureResult): boolean {
  const exceptions = event.properties?.$exception_list;
  if (!Array.isArray(exceptions)) {
    return false;
  }

  const frames = exceptions.flatMap(
    (exception) => exception?.stacktrace?.frames ?? [],
  );
  if (frames.length === 0) {
    return false;
  }

  return frames.every((frame) => {
    const filename: string = frame?.filename ?? "";
    return THIRD_PARTY_ERROR_HOSTS.some((host) => filename.includes(host));
  });
}

export function PostHogProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    if (process.env.NEXT_PUBLIC_POSTHOG_KEY) {
      posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY, {
        api_host: "/tracker/ph",
        ui_host: "https://us.posthog.com",
        person_profiles: "always",
        capture_pageview: false,
        capture_pageleave: true,
        before_send: (event) => {
          if (event?.event === "$exception" && isThirdPartyException(event)) {
            return null;
          }
          return event;
        },
      });
    }
  }, []);

  return (
    <PHProvider client={posthog}>
      <SuspendedPostHogPageView />
      {children}
    </PHProvider>
  );
}

function PostHogPageView() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const posthog = usePostHog();

  useEffect(() => {
    if (pathname && posthog) {
      let url = window.origin + pathname;
      if (searchParams.toString()) {
        url = url + "?" + searchParams.toString();
      }
      posthog.capture("$pageview", { $current_url: url });
    }
  }, [pathname, searchParams, posthog]);

  return null;
}

function SuspendedPostHogPageView() {
  return (
    <Suspense fallback={null}>
      <PostHogPageView />
    </Suspense>
  );
}
