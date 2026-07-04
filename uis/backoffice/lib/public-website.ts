const DEFAULT_PUBLIC_WEBSITE_URL =
  "https://trackflow-ai-powered-logistics-plat.vercel.app";

// Keep the public-site destination in one server-side configuration seam so
// login surfaces never need to duplicate deployment-specific URLs.
export function getPublicWebsiteURL() {
  return (process.env.PUBLIC_WEBSITE_URL ?? DEFAULT_PUBLIC_WEBSITE_URL).replace(
    /\/$/,
    "",
  );
}
