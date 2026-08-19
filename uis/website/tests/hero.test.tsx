import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Hero } from "@/components/sections/Hero";

const copy = {
  headlineLead: "Logistics that scales with your",
  headlineHighlight: "e-commerce",
  subheading: "Warehouse management, last-mile deliveries, and reverse logistics.",
  cta: "Request information",
  imageAlt: "Modern warehouse dispatch area with parcels moving to a delivery van",
};

describe("Hero background video", () => {
  it("renders an autoplaying, looping, muted, inline video with a poster", () => {
    const { container } = render(<Hero copy={copy} />);

    const video = container.querySelector("video.hero-video");
    expect(video).not.toBeNull();
    expect(video).toHaveAttribute("autoplay");
    expect(video).toHaveAttribute("loop");
    // React reflects `muted`/`playsInline` as DOM properties, not attributes.
    expect((video as HTMLVideoElement).muted).toBe(true);
    expect((video as HTMLVideoElement).playsInline).toBe(true);
    expect(video).toHaveAttribute("poster", "/images/trackflow-operations-hero.png");
    expect(video).toHaveAttribute("aria-hidden", "true");

    const source = video?.querySelector("source");
    expect(source).toHaveAttribute("src", "/images/trackflow_video.mp4");
    expect(source).toHaveAttribute("type", "video/mp4");
  });

  it("keeps a reduced-motion still fallback and both tint overlays", () => {
    const { container } = render(<Hero copy={copy} />);

    const fallback = container.querySelector("img.hero-video-fallback");
    expect(fallback).toHaveAttribute("src", "/images/trackflow-operations-hero.png");
    expect(fallback).toHaveAttribute("alt", copy.imageAlt);

    const overlays = container.querySelectorAll("div.absolute.bg-gradient-to-r, div.absolute.bg-gradient-to-b");
    expect(overlays.length).toBe(2);
  });
});
