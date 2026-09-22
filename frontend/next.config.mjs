import path from "node:path";
/** Same-origin API proxy. The browser never needs the private API hostname. */
const backend = process.env.ATLAS_INTERNAL_API_URL || "http://api:8000";
export default {
  outputFileTracingRoot: path.resolve(process.cwd()),
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};
