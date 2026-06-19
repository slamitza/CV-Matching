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

  const csvCell = (value) => {
    const stringValue = String(value || "");
    return /[",\n\r]/.test(stringValue)
      ? `"${stringValue.replace(/"/g, '""')}"`
      : stringValue;
  };

  const jsonResult = JSON.parse(
    (function () {
      const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
      const text = (root, selectors) => {
        for (const selector of selectors) {
          const node = root.querySelector(selector);
          const value = clean(node && node.innerText);
          if (value) return value;
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
      const jobIdFromUrl = (rawUrl) => {
        const match = String(rawUrl || "").match(/\/jobs\/view\/(\d+)/);
        return match ? match[1] : "";
      };
      const normalizeUrl = (rawUrl, jobId) => {
        if (jobId) return `https://www.linkedin.com/jobs/view/${jobId}/`;
        try {
          return rawUrl ? new URL(rawUrl, location.origin).href : "";
        } catch (_error) {
          return "";
        }
      };
      const cards = Array.from(
        document.querySelectorAll(".job-card-container, li.jobs-search-results__list-item, [data-job-id]")
      ).filter((card) => {
        const box = card.getBoundingClientRect();
        return box.width > 0 && box.height > 0;
      });
      const rowsById = new Map();
      for (const card of cards) {
        const link = card.querySelector('a[href*="/jobs/view/"]');
        const rawUrl = link && link.getAttribute("href");
        const nestedJobNode = card.querySelector("[data-job-id]");
        const jobId =
          card.getAttribute("data-job-id") ||
          (nestedJobNode && nestedJobNode.getAttribute("data-job-id")) ||
          jobIdFromUrl(rawUrl);
        const url = normalizeUrl(rawUrl, jobId);
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
        if (!title || !company || !url) continue;
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
      return JSON.stringify({ rows: Array.from(rowsById.values()) });
    })()
  );

  const rows = jsonResult.rows || [];
  if (!rows.length) {
    alert("No visible LinkedIn job cards were found on this page.");
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
  link.download = `linkedin-visible-jobs-${date}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  alert(`Saved ${rows.length} visible LinkedIn jobs to CSV.`);
})();
