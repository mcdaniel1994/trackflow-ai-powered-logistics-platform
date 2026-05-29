import Image from "next/image";
import Link from "next/link";
import type { Translation } from "@/content/types";

type HeroCopy = Translation["home"]["hero"];

export function Hero({ copy }: { copy: HeroCopy }) {
  return (
    <section
      id="home"
      className="relative flex min-h-[76vh] items-center overflow-hidden"
      aria-labelledby="hero-heading"
    >
      <Image
        src="/images/trackflow-operations-hero.png"
        alt={copy.imageAlt}
        fill
        priority
        sizes="100vw"
        className="object-cover"
      />
      <div className="absolute inset-0 bg-gradient-to-r from-navy-deep/95 via-navy-deep/80 to-navy-deep/20" />
      <div className="absolute inset-y-0 left-0 w-full bg-gradient-to-b from-navy-deep/20 via-transparent to-navy-deep/30 lg:w-3/5" />
      <div className="relative mx-auto w-full max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="max-w-[21rem] text-white drop-shadow-[0_4px_22px_rgba(8,20,34,0.72)] hero-copy-shadow sm:max-w-[42rem]">
          <p className="mb-4 text-sm font-bold uppercase tracking-[0.18em] text-ivory">
            TrackFlow
          </p>
          <h1
            id="hero-heading"
            className="text-3xl font-black leading-[1.08] sm:text-5xl sm:leading-[1.04] lg:text-[3.5rem]"
          >
            {copy.headlineLead}{" "}
            <span className="text-coral">{copy.headlineHighlight}</span>
          </h1>
          <p className="mt-6 max-w-[38rem] text-base leading-8 text-ivory sm:text-lg">
            {copy.subheading}
          </p>
          <Link
            href="/application"
            className="mt-10 inline-flex rounded-md bg-coral px-8 py-4 text-base font-black text-white shadow-soft transition hover:bg-teal hover:text-navy-deep sm:text-lg"
          >
            {copy.cta}
          </Link>
        </div>
      </div>
    </section>
  );
}
