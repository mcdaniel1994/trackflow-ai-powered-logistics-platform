"use client";

import Link from "next/link";
import { useLocale } from "@/components/layout/LocaleProvider";

export function PrivacyPage() {
  const { copy } = useLocale();
  const sections = copy.privacy.sections;

  return (
    <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:px-8 lg:py-20">
      <header className="mb-10">
        <h1 className="text-3xl font-black text-navy-deep sm:text-4xl">{copy.privacy.title}</h1>
        <p className="mt-3 text-sm font-semibold text-neutral-500">{copy.privacy.updated}</p>
      </header>
      <div className="space-y-8 rounded-lg border border-mist bg-white p-6 shadow-sm sm:p-8">
        <section aria-labelledby="about-heading">
          <h2 id="about-heading" className="text-xl font-black text-navy">
            {sections.about}
          </h2>
          <p className="mt-3 leading-7 text-neutral-700">{sections.aboutBody}</p>
        </section>
        <section aria-labelledby="data-heading">
          <h2 id="data-heading" className="text-xl font-black text-navy">
            {sections.data}
          </h2>
          <p className="mt-3 leading-7 text-neutral-700">
            <Link href="/application" className="font-black text-navy underline">
              {copy.application.title}
            </Link>{" "}
            {sections.dataBody}
          </p>
          <ul className="mt-3 list-disc space-y-2 pl-6 text-neutral-700">
            {sections.dataItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section aria-labelledby="cookies-heading">
          <h2 id="cookies-heading" className="text-xl font-black text-navy">
            {sections.cookies}
          </h2>
          <p className="mt-3 leading-7 text-neutral-700">{sections.cookiesBody}</p>
        </section>
        <section aria-labelledby="hosting-heading">
          <h2 id="hosting-heading" className="text-xl font-black text-navy">
            {sections.hosting}
          </h2>
          <p className="mt-3 leading-7 text-neutral-700">
            {sections.hostingBody}{" "}
            <a
              href="https://vercel.com/legal/privacy-policy"
              className="font-black text-navy underline"
              rel="noopener noreferrer"
              target="_blank"
            >
              Vercel Privacy Policy
            </a>
          </p>
        </section>
        <section aria-labelledby="privacy-contact-heading">
          <h2 id="privacy-contact-heading" className="text-xl font-black text-navy">
            {sections.contact}
          </h2>
          <p className="mt-3 leading-7 text-neutral-700">
            {sections.contactBody}{" "}
            <a className="font-black text-navy underline" href="mailto:comercial@trackflow.com">
              comercial@trackflow.com
            </a>
          </p>
        </section>
      </div>
    </div>
  );
}
