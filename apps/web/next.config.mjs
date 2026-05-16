/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: { typedRoutes: false },
  async rewrites() {
    const api = process.env.API_BASE_URL || "http://localhost:8000";
    return [{ source: "/api-proxy/:path*", destination: `${api}/:path*` }];
  },
};

export default nextConfig;
