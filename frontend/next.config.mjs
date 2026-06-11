/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  devIndicators: false,
  output: "standalone",
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "**",
      },
    ],
  },
  async rewrites() {
    // API_INTERNAL_URL est une variable serveur (non exposée au navigateur) qui
    // permet au conteneur frontend de joindre le backend sur le réseau Docker
    // (ex: http://backend:8000), tout en laissant le navigateur appeler /api/*
    // en relatif (NEXT_PUBLIC_API_URL="").
    const target =
      process.env.API_INTERNAL_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${target}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
