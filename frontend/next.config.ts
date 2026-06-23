import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  // Keep better-sqlite3 server-side only — it is a native addon
  serverExternalPackages: ['better-sqlite3'],
}

export default nextConfig
