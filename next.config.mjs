import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  basePath: "/tracker",
  transpilePackages: ["chartjs-adapter-date-fns"],
  webpack: (config) => {
    // Force all chart.js imports to resolve to the same instance
    // (pnpm creates separate copies for react-chartjs-2)
    config.resolve.alias["chart.js"] = path.resolve(
      __dirname,
      "node_modules/chart.js",
    );
    return config;
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return [
      {
        source: "/ph/static/:path*",
        destination: "https://us-assets.i.posthog.com/static/:path*",
      },
      {
        source: "/ph/decide",
        destination: "https://us.i.posthog.com/decide",
      },
      {
        source: "/ph/:path*",
        destination: "https://us.i.posthog.com/:path*",
      },
      {
        source: "/api/v1/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL}/:path*`,
      },
      {
        source: "/api/burndown/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL}/api/burndown/:path*`,
      },
      {
        source: "/api/dashboard/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL}/api/dashboard/:path*`,
      },
    ];
  },
};

export default nextConfig;
