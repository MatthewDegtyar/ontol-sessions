// The website serves saved results from public/demo-data. Set NEXT_PUBLIC_LIVE_API=1 to use the FastAPI backend instead.
const live = process.env.NEXT_PUBLIC_LIVE_API === "1";
const api = process.env.API_URL || "http://127.0.0.1:8500";
export default { async rewrites() { return live ? [{ source: "/api/:path*", destination: `${api}/api/:path*` }] : []; } };
