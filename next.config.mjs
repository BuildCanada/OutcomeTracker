/** @type {import('next').NextConfig} */
const nextConfig = {
  basePath: "/tracker",
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
        source: "/api/v1/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL}/:path*`,
      },
      {
        source: "/api/burndown/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL}/api/burndown/:path*`,
      },
    ];
  },
};

export default nextConfig;
