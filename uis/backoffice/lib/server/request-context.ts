import { headers } from "next/headers";

export type ServerAPIContext = {
  baseUrl: string;
  cookieHeader: string;
};

export async function getServerAPIContext(): Promise<ServerAPIContext> {
  const headerStore = await headers();
  const host = headerStore.get("host") ?? "localhost:3000";
  const protocol = headerStore.get("x-forwarded-proto") ?? "http";

  return {
    baseUrl: `${protocol}://${host}`,
    cookieHeader: headerStore.get("cookie") ?? "",
  };
}

export async function getRequestPath() {
  const headerStore = await headers();
  return headerStore.get("x-trackflow-path") ?? "/";
}
