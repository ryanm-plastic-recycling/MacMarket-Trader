"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "macmarket-theme";
const COOKIE_KEY = "macmarket-theme";

export function ThemeToggle() {
  const [theme, setTheme] = useState<"dark" | "light">(
    typeof document !== "undefined" && document.documentElement.dataset.theme === "light" ? "light" : "dark",
  );

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    const resolved = stored === "light" ? "light" : "dark";
    setTheme(resolved);
    document.documentElement.dataset.theme = resolved;
  }, []);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.dataset.theme = next;
    window.localStorage.setItem(STORAGE_KEY, next);
    document.cookie = `${COOKIE_KEY}=${next}; path=/; max-age=31536000; samesite=lax`;
  }

  return <button onClick={toggleTheme} className="op-theme-toggle">{theme === "dark" ? "🌙 Dark" : "☀️ Light"}</button>;
}
