(function () {
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const controls = Array.from(document.querySelectorAll("button, a"));
  const next = controls.find((control) => {
    const label = clean(control.getAttribute("aria-label") || control.innerText);
    return /^(next|view next page)$/i.test(label) || /next/i.test(label);
  });

  if (!next) {
    return "no-next";
  }

  const disabled =
    next.disabled ||
    next.getAttribute("aria-disabled") === "true" ||
    next.classList.contains("artdeco-button--disabled") ||
    next.closest("[disabled]");

  if (disabled) {
    return "disabled";
  }

  next.scrollIntoView({ block: "center", inline: "center" });
  next.click();
  return "clicked";
})();
