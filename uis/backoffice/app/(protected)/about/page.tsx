import type { Metadata } from "next";
import {
  ARCHITECTURE_NOTES,
  DISCLAIMERS,
  NOTABLE_LICENSES,
  TECH_STACK,
} from "@/content/about";

export const metadata: Metadata = {
  title: "About & Disclaimers - TrackFlow Backoffice",
  description:
    "What TrackFlow is, the technologies it is built with, open-source attribution, and the portfolio disclaimer.",
};

const CARD =
  "rounded-xl border border-mist bg-white p-6 dark:border-ink-600 dark:bg-ink-800";
const SECTION_TITLE =
  "text-lg font-black text-navy-deep dark:text-neutral-100";

export default function AboutPage() {
  return (
    <div className="space-y-6">
      <header className="border-b border-mist pb-6 dark:border-ink-600">
        <p className="text-xs font-black uppercase tracking-[0.18em] text-coral">About</p>
        <h1 className="mt-2 text-2xl font-black text-navy-deep sm:text-3xl dark:text-neutral-100">
          About &amp; disclaimers
        </h1>
        <p className="mt-3 max-w-3xl text-neutral-600 dark:text-neutral-300">
          TrackFlow is a portfolio project: a warehouse management and last-mile logistics
          platform built end to end to demonstrate full-stack, data, and AI engineering.
        </p>
      </header>

      {/* Disclaimer leads: a reader should learn this is not a real service before
          anything else on the page invites them to take it literally. */}
      <section aria-labelledby="disclaimers-heading" className={CARD}>
        <h2 id="disclaimers-heading" className={SECTION_TITLE}>
          Important disclaimers
        </h2>
        <ul className="mt-4 space-y-3">
          {DISCLAIMERS.map((item) => (
            <li
              key={item}
              className="flex gap-3 text-sm leading-relaxed text-neutral-600 dark:text-neutral-300"
            >
              <span aria-hidden="true" className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-coral" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="stack-heading" className={CARD}>
        <h2 id="stack-heading" className={SECTION_TITLE}>
          Technology
        </h2>
        <p className="mt-2 text-sm text-neutral-600 dark:text-neutral-300">
          Every layer of the platform was designed and built for this project.
        </p>
        <dl className="mt-5 space-y-5">
          {TECH_STACK.map((group) => (
            <div key={group.layer} className="sm:grid sm:grid-cols-[10rem_1fr] sm:gap-4">
              <dt className="text-sm font-black text-navy dark:text-sky">{group.layer}</dt>
              <dd className="mt-1 text-sm text-neutral-600 sm:mt-0 dark:text-neutral-300">
                <ul className="flex flex-wrap gap-x-2 gap-y-1">
                  {group.items.map((item, index) => (
                    <li key={item}>
                      {item}
                      {index < group.items.length - 1 ? (
                        <span aria-hidden="true" className="text-neutral-400">
                          {" "}
                          ·
                        </span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <section aria-labelledby="architecture-heading" className={CARD}>
        <h2 id="architecture-heading" className={SECTION_TITLE}>
          Architecture
        </h2>
        <ul className="mt-4 space-y-3">
          {ARCHITECTURE_NOTES.map((note) => (
            <li
              key={note}
              className="flex gap-3 text-sm leading-relaxed text-neutral-600 dark:text-neutral-300"
            >
              <span aria-hidden="true" className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-teal" />
              <span>{note}</span>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="licenses-heading" className={CARD}>
        <h2 id="licenses-heading" className={SECTION_TITLE}>
          Open-source licenses
        </h2>
        <p className="mt-2 max-w-3xl text-sm text-neutral-600 dark:text-neutral-300">
          TrackFlow is built on open-source software. The libraries below are the notable
          ones; the full dependency tree runs to roughly 650 packages, so this is a summary
          rather than a complete inventory. Each project is used unmodified under its own
          license, and the repository&rsquo;s <code>THIRD_PARTY_LICENSES.md</code> records the
          complete attribution position, including every copyleft dependency.
        </p>
        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[34rem] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-mist dark:border-ink-600">
                <th scope="col" className="py-2 pr-4 font-black text-navy-deep dark:text-neutral-100">
                  Project
                </th>
                <th scope="col" className="py-2 pr-4 font-black text-navy-deep dark:text-neutral-100">
                  License
                </th>
                <th scope="col" className="py-2 font-black text-navy-deep dark:text-neutral-100">
                  Used for
                </th>
              </tr>
            </thead>
            <tbody>
              {NOTABLE_LICENSES.map((row) => (
                <tr key={row.name} className="border-b border-mist/60 dark:border-ink-600/60">
                  <td className="py-2 pr-4 font-bold text-neutral-700 dark:text-neutral-200">
                    {row.name}
                  </td>
                  <td className="py-2 pr-4 text-neutral-600 dark:text-neutral-300">{row.license}</td>
                  <td className="py-2 text-neutral-600 dark:text-neutral-300">{row.usage}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
