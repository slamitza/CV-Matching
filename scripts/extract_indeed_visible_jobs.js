(function () {
  const columns = [
    "source_id",
    "title",
    "company",
    "location",
    "url",
    "description",
    "posted_at",
    "remote",
  ];

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

  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();

  const csvCell = (value) => {
    const stringValue = String(value || "");
    return /[",\n\r]/.test(stringValue)
      ? `"${stringValue.replace(/"/g, '""')}"`
      : stringValue;
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
    const parsed = new URL(rawUrl, location.origin);
    const jk = parsed.searchParams.get("jk");
    if (jk) {
      return new URL(`/viewjob?jk=${encodeURIComponent(jk)}`, location.origin).href;
    }
    return parsed.href;
  };

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
    const jobKey =
      card.getAttribute("data-jk") ||
      (card.querySelector("[data-jk]") && card.querySelector("[data-jk]").getAttribute("data-jk")) ||
      (link ? new URL(link.href, location.origin).searchParams.get("jk") : "");
    const url = normalizeIndeedUrl(link && link.getAttribute("href"), jobKey);
    const title = text(card, [
      '[data-testid="job-title"]',
      "h2.jobTitle a",
      "h2.jobTitle",
      'a[data-jk]',
      'a[href*="/viewjob"]',
    ]);
    const company = text(card, [
      '[data-testid="company-name"]',
      ".companyName",
      '[data-testid="companyName"]',
    ]);
    const jobLocation = text(card, [
      '[data-testid="text-location"]',
      '[data-testid="job-location"]',
      ".companyLocation",
    ]);

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

  const rows = Array.from(rowsById.values());
  if (!rows.length) {
    alert("No visible Indeed job cards were found on this page.");
    return;
  }

  const csv = [
    columns.join(","),
    ...rows.map((row) => columns.map((column) => csvCell(row[column])).join(",")),
  ].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const date = new Date().toISOString().slice(0, 10);
  link.href = url;
  link.download = `indeed-visible-jobs-${date}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  alert(`Saved ${rows.length} visible Indeed jobs to CSV.`);
})();
