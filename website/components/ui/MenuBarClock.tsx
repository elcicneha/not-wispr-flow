"use client";

import { useEffect, useState } from "react";

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function format(d: Date): string {
  const day = DAYS[d.getDay()];
  const date = d.getDate();
  const month = MONTHS[d.getMonth()];
  let hours = d.getHours();
  const minutes = String(d.getMinutes()).padStart(2, "0");
  const ampm = hours >= 12 ? "PM" : "AM";
  hours = hours % 12 || 12;
  return `${day} ${date} ${month}, ${hours}:${minutes} ${ampm}`;
}

export default function MenuBarClock() {
  // Render a static placeholder on SSR; real time after hydration.
  // suppressHydrationWarning prevents the SSR/client text mismatch warning.
  const [now, setNow] = useState<string>("Sat 9 May, 10:36 PM");

  useEffect(() => {
    const update = () => setNow(format(new Date()));
    update();

    // Sync to next minute boundary, then tick every 60s
    let interval: ReturnType<typeof setInterval> | undefined;
    const msUntilNextMinute = (60 - new Date().getSeconds()) * 1000;
    const timeout = setTimeout(() => {
      update();
      interval = setInterval(update, 60_000);
    }, msUntilNextMinute);

    return () => {
      clearTimeout(timeout);
      if (interval) clearInterval(interval);
    };
  }, []);

  return (
    <span
      style={{ fontVariantNumeric: "tabular-nums" }}
      suppressHydrationWarning
    >
      {now}
    </span>
  );
}
