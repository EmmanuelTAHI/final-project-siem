/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  devIndicators: false,
  output: "standalone",
  // Next.js normalise les URL réécrites en supprimant le "/" final (ex:
  // /api/auth/login/ -> /api/auth/login), ce qui casse les endpoints DRF
  // qui exigent ce slash (APPEND_SLASH). On désactive cette normalisation.
  skipTrailingSlashRedirect: true,
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
      // Règle dédiée aux chemins se terminant par "/" : sans elle, Next.js
      // perd le slash final lors de l'interpolation de ":path*", ce qui
      // casse les endpoints DRF (APPEND_SLASH) comme /api/auth/login/.
      {
        source: "/api/:path*/",
        destination: `${target}/api/:path*/`,
      },
      {
        source: "/api/:path*",
        destination: `${target}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
