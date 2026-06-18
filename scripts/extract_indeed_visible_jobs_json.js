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

  const normalizeIndeedUrl = (rawUrl, jobKey) => {
    if (jobKey) {
      return new URL(`/viewjob?jk=${encodeURIComponent(jobKey)}`, location.origin).href;
    }
    if (!rawUrl) {
      return "";
    }
    try {
      const parsed = new URL(rawUrl, location.origin);
      const jk = parsed.searchParams.get("jk");
      if (jk) {
        return new URL(`/viewjob?jk=${encodeURIComponent(jk)}`, location.origin).href;
      }
      return parsed.href;
    } catch (_error) {
      return "";
    }
  };

  const pageText = clean(document.body && document.body.innerText).toLowerCase();
  const blocked = [
    "additional verification required",
    "verify you are human",
    "captcha",
    "cloudflare",
  ].some((phrase) => pageText.includes(phrase));

  const visibleCards = Array.from(
    document.querySelectorAll("[data-jk], .job_seen_beacon, td.resultContent, div.cardOutline")
  ).filter((card) => {
    const box = card.getBoundingClientRect();
    return box.width > 0 && box.height > 0;
  });

  const rowsById = new Map();
  for (const card of visibleCards) {
    const link = card.querySelector(
      'a[href*="/viewjob"], a[href*="jk="], h2.jobTitle a, a[data-jk]'
    );
    let linkJobKey = "";
    try {
      linkJobKey = link ? new URL(link.href, location.origin).searchParams.get("jk") || "" : "";
    } catch (_error) {
      linkJobKey = "";
    }

    const nestedJobNode = card.querySelector("[data-jk]");
    const jobKey =
      card.getAttribute("data-jk") ||
      (nestedJobNode && nestedJobNode.getAttribute("data-jk")) ||
      linkJobKey;
    const url = normalizeIndeedUrl(link && link.getAttribute("href"), jobKey);
    const fallbackLines = Array.from(card.innerText.split("\n")).map(clean).filter(Boolean);
    const title =
      text(card, [
        '[data-testid="job-title"]',
        "h2.jobTitle a",
        "h2.jobTitle",
        'a[data-jk]',
        'a[href*="/viewjob"]',
      ]) || fallbackLines[0] || "";
    const company =
      text(card, [
        '[data-testid="company-name"]',
        ".companyName",
        '[data-testid="companyName"]',
      ]) || fallbackLines[1] || "";
    const jobLocation =
      text(card, [
        '[data-testid="text-location"]',
        '[data-testid="job-location"]',
        ".companyLocation",
      ]) || fallbackLines[2] || "";

    if (!title || !company || !url) {
      continue;
    }

    const description = clean(card.innerText);
    const sourceId = `indeed-${jobKey || hash(`${title}|${company}|${url}`)}`;
    rowsById.set(sourceId, {
      source_id: sourceId,
      title,
      company,
      location: jobLocation,
      url,
      description,
      posted_at: "last-24h",
      remote: /\b(remote|home office)\b/i.test(`${title} ${jobLocation} ${description}`)
        ? "true"
        : "",
    });
  }

  return JSON.stringify({
    url: location.href,
    title: document.title,
    blocked,
    rows: Array.from(rowsById.values()),
  });
})();
