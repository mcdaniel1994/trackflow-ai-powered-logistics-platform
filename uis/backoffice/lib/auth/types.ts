export type UserRole = "admin" | "user";
export type UserStatus = "active" | "suspended" | "disabled";

export type AuthUser = {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  status: UserStatus;
  must_change_password: boolean;
  created_at: string;
  last_login_at: string | null;
};

export type CreatedUser = AuthUser & {
  temporary_password: string;
  setup_email_sent: boolean;
};

export type AuthAPIError = {
  message: string;
  status?: number;
  field_errors?: Record<string, string>;
};
