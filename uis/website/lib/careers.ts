export const CAREER_ROLES = {
  executive_assistant: {
    en: "Executive Assistant — Zaragoza",
    es: "Asistente ejecutivo — Zaragoza",
  },
  warehouse_associate: {
    en: "Warehouse Associate — Los Angeles",
    es: "Operario de almacén — Los Ángeles",
  },
  customer_support: {
    en: "Customer Support Specialist — Zaragoza",
    es: "Especialista en atención al cliente — Zaragoza",
  },
  general: { en: "General application", es: "Candidatura general" },
} as const;
export type CareerRole = keyof typeof CAREER_ROLES;
export interface DemoApplication {
  full_name: string;
  email: string;
  role: CareerRole;
  experience_years: number;
  demo_acknowledged: true;
}
export function isCareerRole(value: unknown): value is CareerRole {
  return typeof value === "string" && Object.hasOwn(CAREER_ROLES, value);
}
export function applicationErrors(
  value: Record<string, unknown>,
): Record<string, string> {
  const errors: Record<string, string> = {};
  if (
    Object.keys(value).some(
      (key) =>
        ![
          "full_name",
          "email",
          "role",
          "experience_years",
          "demo_acknowledged",
        ].includes(key),
    )
  )
    errors.form = "invalid_fields";
  if (
    typeof value.full_name !== "string" ||
    !value.full_name.trim() ||
    value.full_name.trim().length > 100
  )
    errors.full_name = "fictional_name";
  if (
    typeof value.email !== "string" ||
    value.email.length > 254 ||
    !/^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@example\.com$/i.test(value.email.trim())
  )
    errors.email = "demo_email";
  if (!isCareerRole(value.role)) errors.role = "choose_role";
  if (
    typeof value.experience_years !== "number" ||
    !Number.isInteger(value.experience_years) ||
    value.experience_years < 0 ||
    value.experience_years > 60
  )
    errors.experience_years = "experience";
  if (value.demo_acknowledged !== true)
    errors.demo_acknowledged = "acknowledgement";
  return errors;
}
