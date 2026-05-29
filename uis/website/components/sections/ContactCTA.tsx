import Link from "next/link";
import type { Translation } from "@/content/types";

type ContactCopy = Translation["home"]["contact"];

export function ContactCTA({ copy }: { copy: ContactCopy }) {
  return (
    <section id="contact" className="bg-navy-deep py-20 text-white" aria-labelledby="contact-heading">
      <div className="mx-auto max-w-7xl px-4 text-center sm:px-6 lg:px-8">
        <h2 id="contact-heading" className="text-3xl font-black sm:text-4xl">
          {copy.title}
        </h2>
        <p className="mx-auto mt-4 max-w-2xl text-lg leading-8 text-ivory">{copy.subtitle}</p>
        <div className="mt-12 flex flex-col items-center justify-center gap-8 sm:flex-row">
          <address className="not-italic">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-mist">{copy.emailLabel}</p>
            <a className="mt-1 block font-black text-teal" href="mailto:comercial@trackflow.com">
              comercial@trackflow.com
            </a>
          </address>
          <address className="not-italic">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-mist">
              {copy.losAngelesLabel}
            </p>
            <a className="mt-1 block font-black text-white" href="tel:+12135550147">
              +1 213 555 0147
            </a>
          </address>
          <address className="not-italic">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-mist">
              {copy.zaragozaLabel}
            </p>
            <a className="mt-1 block font-black text-white" href="tel:+34976123456">
              +34 976 123 456
            </a>
          </address>
        </div>
        <Link
          href="/application"
          className="mt-12 inline-flex rounded-md bg-coral px-8 py-4 text-lg font-black text-white transition hover:bg-teal hover:text-navy-deep"
        >
          {copy.cta}
        </Link>
      </div>
    </section>
  );
}
