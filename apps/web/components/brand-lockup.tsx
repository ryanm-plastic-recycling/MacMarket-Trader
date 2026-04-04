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
    ? (theme === "light" ? "/brand/square_console_ticks_icon_light.png" : "/brand/square_console_ticks_icon_dark.png")
    : (theme === "light" ? "/brand/square_console_ticks_lockup_light.png" : "/brand/square_console_ticks_lockup_dark.png");

  return (
    <img
      src={src}
      alt="MacMarket Trader"
      className={compact ? "op-brand-lockup op-brand-lockup-compact" : "op-brand-lockup"}
    />
  );
}
