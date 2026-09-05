/** @type {import('next').NextConfig} */
const apiOrigin = (() => {
  try {
    return new URL(process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000").origin;
  } catch {
    return "'self'";
  }
})();
const developmentScriptPolicy = process.env.NODE_ENV === "production" ? "" : " 'unsafe-eval'";

const contentSecurityPolicy = [
  "default-src 'self'",
  "base-uri 'self'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "object-src 'none'",
  `script-src 'self' 'unsafe-inline'${developmentScriptPolicy}`,
  "style-src 'self' 'unsafe-inline'",
  "font-src 'self' data:",
  "img-src 'self' data: blob:",
  "media-src 'self' blob:",
  `connect-src 'self' ${apiOrigin}`,
].join("; ");

const nextConfig = {
  poweredByHeader: false,
  output: "standalone",
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  experimental: {
    optimizePackageImports: ["recharts"]
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "Content-Security-Policy", value: contentSecurityPolicy },
        ],
      },
    ];
  },
};

export default nextConfig;
