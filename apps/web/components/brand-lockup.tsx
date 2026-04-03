"use client";

import { useEffect, useState } from "react";

export function BrandLockup({ compact = false }: { compact?: boolean }) {
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    if (typeof document === "undefined") return;
    const sync = () => {
      const attr = document.documentElement.getAttribute("data-theme");
      setTheme(attr === "light" ? "light" : "dark");
    };
    sync();
    const observer = new MutationObserver(sync);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  const src = compact
    ? (theme === "light" ? "/brand/macmarket-icon-light.svg" : "/brand/macmarket-icon-dark.svg")
    : (theme === "light" ? "/brand/macmarket-lockup-light.svg" : "/brand/macmarket-lockup-dark.svg");

  return <img src={src} alt="MacMarket Trader" style={{ width: compact ? 36 : 170, height: "auto" }} />;
}
