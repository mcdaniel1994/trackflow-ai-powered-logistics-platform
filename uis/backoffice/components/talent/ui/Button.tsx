// Button primitive. Four variants cover everything in the app:
//   primary   navy -> coral hover     (submits, "Register candidate")
//   secondary white with navy text    (back links, cancels)
//   danger    red outlined            (delete actions)
//   ghost     transparent             (low-emphasis links inside dense UI)
//
// `buttonClassName` is exported separately so we can give a Next.js <Link>
// the same look without wrapping it in a <button>. See `app/page.tsx` for that.
//
// `type = "button"` default is deliberate — without it, buttons inside <form>
// elements default to type="submit" and accidentally submit forms when clicked.

import type { ButtonHTMLAttributes } from "react";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";

const baseClasses =
  "inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60";

const variantClasses: Record<ButtonVariant, string> = {
  primary: "bg-navy text-white hover:bg-coral",
  secondary: "border border-neutral-300 bg-white text-navy hover:bg-mist",
  danger: "border border-red-200 bg-white text-red-700 hover:bg-red-50",
  ghost: "text-navy hover:bg-mist",
};

export function buttonClassName(variant: ButtonVariant = "primary", className = "") {
  return `${baseClasses} ${variantClasses[variant]} ${className}`.trim();
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
};

export function Button({ variant = "primary", className = "", type = "button", ...props }: ButtonProps) {
  return <button type={type} className={buttonClassName(variant, className)} {...props} />;
}
