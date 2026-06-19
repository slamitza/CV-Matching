(function () {
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();

  const text = (root, selectors) => {
    for (const selector of selectors) {
      const node = root.querySelector(selector);
      const value = clean(node && node.innerText);
      if (value) {
        return value;
      }
    }
    return "";
  };

  const hash = (value) => {
    let result = 5381;
    for (let index = 0; index < value.length; index += 1) {
      result = ((result << 5) + result) ^ value.charCodeAt(index);
    }
    return (result >>> 0).toString(16);
  };

  const linkedInJobId = (rawUrl) => {
    if (!rawUrl) {
      return "";
    }
    const match = String(rawUrl).match(/\/jobs\/view\/(\d+)/);
    return match ? match[1] : "";
  };

  const normalizeLinkedInUrl = (rawUrl, jobId) => {
    if (jobId) {
      return `https://www.linkedin.com/jobs/view/${jobId}/`;
    }
    if (!rawUrl) {
      return "";
    }
    try {
      return new URL(rawUrl, location.origin).href;
    } catch (_error) {
      return "";
    }
  };

  const pageText = clean(document.body && document.body.innerText).toLowerCase();
  const blocked = [
    "security verification",
    "unusual activity",
    "verify your identity",
    "two-step verification",
    "checkpoint",
    "sign in",
  ].some((phrase) => pageText.includes(phrase));

  const visibleCards = Array.from(
    document.querySelectorAll(".job-card-container, li.jobs-search-results__list-item, [data-job-id]")
  ).filter((card) => {
    const box = card.getBoundingClientRect();
    return box.width > 0 && box.height > 0;
  });

  const rowsById = new Map();
  for (const card of visibleCards) {
    const link = card.querySelector('a[href*="/jobs/view/"]');
    const rawUrl = link && link.getAttribute("href");
    const nestedJobNode = card.querySelector("[data-job-id]");
    const jobId =
      card.getAttribute("data-job-id") ||
      (nestedJobNode && nestedJobNode.getAttribute("data-job-id")) ||
      linkedInJobId(rawUrl);
    const url = normalizeLinkedInUrl(rawUrl, jobId);
    const fallbackLines = Array.from(card.innerText.split("\n")).map(clean).filter(Boolean);
    const title =
      text(card, [
        ".job-card-list__title--link",
        ".job-card-list__title",
        ".job-card-container__link",
        'a[href*="/jobs/view/"]',
      ]) || fallbackLines[0] || "";
    const company =
      text(card, [
        ".artdeco-entity-lockup__subtitle",
        ".job-card-container__primary-description",
      ]) || fallbackLines[1] || "";
    const jobLocation =
      text(card, [
        ".artdeco-entity-lockup__caption",
        ".job-card-container__metadata-item",
      ]) || fallbackLines[2] || "";

    if (!title || !company || !url) {
      continue;
    }

    const description = clean(card.innerText);
    const sourceId = `linkedin-${jobId || hash(`${title}|${company}|${url}`)}`;
    rowsById.set(sourceId, {
      source_id: sourceId,
      title,
      company,
      location: jobLocation,
      url,
      description,
      posted_at: "last-24h",
      remote: /\bremote\b/i.test(`${title} ${jobLocation} ${description}`) ? "true" : "",
    });
  }

  return JSON.stringify({
    url: location.href,
    title: document.title,
    blocked,
    rows: Array.from(rowsById.values()),
  });
})();
