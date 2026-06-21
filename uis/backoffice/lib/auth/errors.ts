import type { AuthAPIError } from "@/lib/auth/types";

export async function parseAPIError(response: Response): Promise<AuthAPIError> {
  let payload: unknown;

  try {
    payload = await response.json();
  } catch {
    payload = undefined;
  }

  const error: AuthAPIError = {
    message: `Request failed with status ${response.status}.`,
    status: response.status,
  };

  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;

    if (typeof record.detail === "string") {
      error.message = record.detail;
    }

    if (typeof record.message === "string") {
      error.message = record.message;
    }

    if (Array.isArray(record.detail)) {
      const fieldErrors: Record<string, string> = {};
      let firstMessage = "";

      for (const item of record.detail) {
        if (!item || typeof item !== "object") {
          continue;
        }

        const detail = item as Record<string, unknown>;
        const message = typeof detail.msg === "string" ? detail.msg : error.message;
        const loc = Array.isArray(detail.loc) ? detail.loc : [];
        const field = loc.length ? String(loc[loc.length - 1]) : "";

        if (!firstMessage && message) {
          firstMessage = message;
        }

        if (field && field !== "body") {
          fieldErrors[field] = message;
        }
      }

      if (Object.keys(fieldErrors).length) {
        error.field_errors = fieldErrors;
        error.message = "Please review the highlighted fields.";
      } else if (firstMessage) {
        error.message = firstMessage;
      }
    }
  }

  return error;
}

export function errorMessage(error: unknown) {
  if (error && typeof error === "object" && "message" in error) {
    const message = (error as { message?: unknown }).message;
    if (typeof message === "string") {
      return message;
    }
  }

  return "Something went wrong. Please try again.";
}

export function errorFieldErrors(error: unknown) {
  if (error && typeof error === "object" && "field_errors" in error) {
    const fieldErrors = (error as { field_errors?: unknown }).field_errors;
    if (fieldErrors && typeof fieldErrors === "object") {
      return fieldErrors as Record<string, string>;
    }
  }

  return {};
}
