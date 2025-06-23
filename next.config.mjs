/** @type {import('next').NextConfig} */
const nextConfig = {
  basePath: "/tracker",
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  // async redirects() {
  //   return [
  //     {
  //       source: "/tracker",
  //       destination: "/en/tracker",
  //       permanent: false,
  //     },
  //   ];
  // },
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
    ];
  },
};

export default nextConfig;
