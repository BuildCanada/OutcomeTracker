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
  async redirects() {
    return [
      {
        source: "/tracker",
        destination: "/en/tracker",
        permanent: false,
      },
    ];
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
        source: "/en/tracker/:path*",
        destination: "/en/tracker/:path*",
      },
      {
        source: "/promise/:path*",
        destination: "/promise/:path*",
      },
      {
        source: "/fr/tracker",
        destination: "/fr/tracker",
      },
      {
        source: "/en/admin",
        destination: "/admin",
      },
      {
        source: "/fr/admin",
        destination: "/admin",
      },
      {
        source: "/api/:path*",
        destination: "/api/:path*",
      },
      {
        source: "/:path*",
        // TODO: switch this over on webflow to be the main page that other things redirect to.
        destination: "https://flying-buffalo.buildcanada.com/:path*",
        // destination: "https://www.buildcanada.com/:path*",
      },
    ];
  },
};

export default nextConfig;
