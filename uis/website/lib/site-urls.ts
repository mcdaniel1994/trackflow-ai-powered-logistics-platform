const DEFAULT_BACKOFFICE_URL = "https://backoffice.forgehub.cloud";

// Both desktop and mobile navigation use this one public configuration seam.
export function getBackOfficeURL() {
  return (process.env.NEXT_PUBLIC_BACKOFFICE_URL ?? DEFAULT_BACKOFFICE_URL).replace(
    /\/$/,
    "",
  );
}
