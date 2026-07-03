import { getIdentityAPIURL } from "@/lib/auth/session";

export function identityAPIURL() {
  return getIdentityAPIURL();
}

export function supplierDirectoryAPIURL() {
  return centralAPIURL();
}

export function talentAPIURL() {
  return (process.env.TALENT_API_URL ?? "https://playground.4geeks.com/tracker/api/v1").replace(/\/$/, "");
}

export function centralAPIURL() {
  return (process.env.CENTRAL_API_URL ?? "http://localhost:8003").replace(/\/$/, "");
}
