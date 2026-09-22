/** @type {import('next').NextConfig} */
const repo = "crowdtape";
const base = process.env.PAGES === "1" ? `/${repo}` : "";

export default {
  // Static export: the board holds no secrets and needs no server. It fetches the JSON
  // the recorder publishes, at runtime, from its own origin - so a new snapshot appears
  // without rebuilding anything.
  output: "export",
  basePath: base,
  assetPrefix: base ? `${base}/` : "",
  // The data URL has to be known at build time. Deriving it from window.location breaks
  // on nested routes - /board/ would ask for /board/data/latest.json.
  env: { NEXT_PUBLIC_BASE_PATH: base },
  images: { unoptimized: true },
  trailingSlash: true,
};
