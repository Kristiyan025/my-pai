/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  async rewrites() {
    const orchestratorUrl =
      process.env.ORCHESTRATOR_URL || "http://localhost:8020";
    return [
      {
        source: "/api/:path*",
        destination: `${orchestratorUrl}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
