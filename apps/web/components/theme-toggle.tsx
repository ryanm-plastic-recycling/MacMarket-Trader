"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "macmarket-theme";

export function ThemeToggle() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");

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
  }

  return <button onClick={toggleTheme} className="op-theme-toggle">{theme === "dark" ? "🌙 Dark" : "☀️ Light"}</button>;
}
