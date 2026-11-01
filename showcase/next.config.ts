import type { NextConfig } from "next";

// Static export: `npm run build` writes the whole site to out/.
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  agentRules: false,
};

export default nextConfig;
