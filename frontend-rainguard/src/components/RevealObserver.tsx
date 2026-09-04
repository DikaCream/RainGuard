import { useEffect } from "react";
import { useLocation } from "react-router-dom";

/**
 * Watches every `[data-reveal]` element and adds `.revealed` (fade-up) once it
 * scrolls into view. Re-scans on route change for lazy-loaded pages. A
 * fallback timer reveals anything missed, so content can never stay hidden.
 */
export default function RevealObserver() {
  const { pathname } = useLocation();

  useEffect(() => {
    let fallback: ReturnType<typeof setTimeout> | undefined;
    const els = Array.from(
      document.querySelectorAll<HTMLElement>("[data-reveal]"),
    );
    if (els.length === 0) return;

    const io = new IntersectionObserver(
      (entries) => {
        for (const en of entries) {
          if (en.isIntersecting) {
            en.target.classList.add("revealed");
            io.unobserve(en.target);
          }
        }
      },
      { threshold: 0.1, rootMargin: "0px 0px -6% 0px" },
    );
    els.forEach((el) => io.observe(el));

    // Safety net: reveal everything shortly after mount / route change.
    fallback = setTimeout(() => {
      els.forEach((el) => el.classList.add("revealed"));
    }, 1800);

    return () => {
      io.disconnect();
      if (fallback) clearTimeout(fallback);
    };
  }, [pathname]);

  return null;
}