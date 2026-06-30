(function () {
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const visibleCards = Array.from(
    document.querySelectorAll("[data-jk], .job_seen_beacon, td.resultContent, div.cardOutline")
  ).filter((card) => {
    const box = card.getBoundingClientRect();
    return box.width > 0 && box.height > 0;
  });

  if (visibleCards.length === 0) {
    return "no-jobs";
  }

  const controls = Array.from(
    document.querySelectorAll('a, button, a[data-testid="pagination-page-next"], a[rel="next"]')
  );
  const next = controls.find((control) => {
    const label = clean(
      control.getAttribute("aria-label") ||
        control.getAttribute("title") ||
        control.innerText
    );
    return /^(next|next page)$/i.test(label) || /next/i.test(label);
  });

  if (!next) {
    return "no-next";
  }

  const disabled =
    next.disabled ||
    next.getAttribute("aria-disabled") === "true" ||
    next.getAttribute("disabled") !== null ||
    next.closest("[disabled]");

  if (disabled) {
    return "disabled";
  }

  next.scrollIntoView({ block: "center", inline: "center" });
  next.click();
  return "clicked";
})();
