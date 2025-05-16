/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  async rewrites() {
    return [
      {
        source: "/ph/static/:path*",
        destination: "https://us-assets.i.posthog.com/static/:path*",
      },
      {
        source: "/en/tracker",
        destination: "/en/tracker",
      },
      {
        source: "/fr/tracker",
        destination: "/fr/tracker",
      },
      {
        source: "/tracker/:path*",
        destination: "/tracker/:path*",
      },
      {
        source: "/:path*",
        destination: "https://www.buildcanada.com/:path*",
      },
    ];
  },
};

export default nextConfig;
