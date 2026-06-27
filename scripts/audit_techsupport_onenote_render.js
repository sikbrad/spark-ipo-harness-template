#!/usr/bin/env node
/* eslint-disable no-console */

const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");
const puppeteer = require("puppeteer");

const ROOT = path.resolve(__dirname, "..");
const BASE = path.join(ROOT, "data", "techsupport", "onenote");
const RAW_REVIEW = path.join(BASE, "raw_review");
const VIEWER = path.join(BASE, "entities", "viewer");
const QA_DIR = path.join(BASE, "qa");
const AUDIT_PATH = path.join(QA_DIR, "full_render_audit.json");

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function readViewerPayload() {
  const text = fs.readFileSync(path.join(VIEWER, "data.js"), "utf8");
  const prefix = "window.TECHSUPPORT_ENTITIES_DATA = ";
  if (!text.startsWith(prefix)) {
    throw new Error("viewer data.js prefix changed");
  }
  return JSON.parse(text.slice(prefix.length).replace(/;\s*$/, ""));
}

async function pool(items, limit, worker) {
  const results = new Array(items.length);
  let next = 0;
  async function run() {
    while (next < items.length) {
      const index = next;
      next += 1;
      results[index] = await worker(items[index], index);
    }
  }
  await Promise.all(Array.from({ length: limit }, run));
  return results;
}

async function auditRawPage(browser, row) {
  const page = await browser.newPage();
  page.setDefaultNavigationTimeout(8000);
  page.setDefaultTimeout(8000);
  try {
    await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 1 });
    const target = path.join(BASE, row.html_path);
    await page.goto(pathToFileURL(target).href, { waitUntil: "domcontentloaded", timeout: 8000 });
    await new Promise((resolve) => setTimeout(resolve, 500));
    const rendered = await page.evaluate(() => {
      const images = Array.from(document.images).map((img) => ({
        src: img.getAttribute("src") || "",
        complete: img.complete,
        naturalWidth: img.naturalWidth,
        naturalHeight: img.naturalHeight,
        missingResource: img.getAttribute("data-missing-resource") === "true",
        nonPreviewable: img.getAttribute("data-non-previewable") === "true",
      }));
      const pending = images.filter((img) => img.src && !img.complete);
      const broken = images.filter((img) => img.src && img.complete && (img.naturalWidth <= 0 || img.naturalHeight <= 0));
      return {
        title: document.querySelector(".raw-header h1")?.textContent?.trim() || document.title,
        imageNodes: images.length,
        loadedImages: images.length - broken.length,
        brokenImages: broken.length,
        pendingImages: pending.length,
        placeholderImages: document.querySelectorAll(".onenote-missing-image").length,
        attachmentLinks: document.querySelectorAll(".onenote-attachment").length,
        bodyTextLength: document.body.innerText.length,
        brokenSources: broken.slice(0, 5).map((img) => img.src),
      };
    });
    return {
      page_key: row.page_key,
      title: row.title,
      status: row.status,
      expected_local_images: row.local_images,
      expected_source_missing_images: row.source_missing_images,
      expected_unavailable_images: row.unavailable_images,
      expected_missing_images: row.missing_images,
      expected_attachments: row.local_attachments,
      ...rendered,
      ok:
        rendered.brokenImages === 0 &&
        rendered.pendingImages === 0 &&
        rendered.imageNodes === row.local_images &&
        rendered.placeholderImages === row.source_missing_images + row.unavailable_images + row.missing_images,
    };
  } catch (error) {
    return {
      page_key: row.page_key,
      title: row.title,
      status: row.status,
      ok: false,
      error: `${error.name}: ${error.message}`,
    };
  } finally {
    await page.close().catch(() => undefined);
  }
}

async function auditViewer(browser, payload) {
  const page = await browser.newPage();
  try {
    await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 1 });
    await page.goto(pathToFileURL(path.join(VIEWER, "index.html")).href, { waitUntil: "load" });
    await page
      .waitForFunction(() => Boolean(window.TECHSUPPORT_ENTITIES_DATA?.entities?.length), { timeout: 5000 })
      .catch(() => undefined);
    return await page.evaluate((expectedEntities) => {
      const data = window.TECHSUPPORT_ENTITIES_DATA || { entities: [], excluded: [] };
      const iframe = document.querySelector(".source-frame");
      return {
        entities: data.entities.length,
        excluded: data.excluded.length,
        entitiesWithRawReview: data.entities.filter((item) => item.source?.raw_review_html).length,
        resultRows: document.querySelectorAll(".result-row").length,
        detailHasImagePreview: Boolean(document.querySelector(".guide-images")),
        defaultSourceIsRawReview: iframe ? iframe.getAttribute("src").includes("../../raw_review/pages/") : null,
        ok: data.entities.length === expectedEntities && data.entities.every((item) => item.source?.raw_review_html),
      };
    }, payload.entities.length);
  } finally {
    await page.close();
  }
}

async function main() {
  fs.mkdirSync(QA_DIR, { recursive: true });
  const startedAt = new Date();
  const rawSummary = readJson(path.join(RAW_REVIEW, "summary.json"));
  const payload = readViewerPayload();
  const viewerStatic = {
    entities: payload.entities.length,
    excluded: payload.excluded.length,
    entitiesWithRawReview: payload.entities.filter((item) => item.source?.raw_review_html).length,
    missingAttachmentAssets: payload.entities.flatMap((item) =>
      (item.assets?.attachments || []).filter((asset) => !asset.exists).map((asset) => ({ title: item.title, asset })),
    ),
    unavailableImageAssets: payload.entities.flatMap((item) =>
      (item.assets?.images || []).filter((asset) => !asset.exists).map((asset) => ({ title: item.title, asset })),
    ),
    nonPreviewableImageAssets: payload.entities.flatMap((item) =>
      (item.assets?.images || [])
        .filter((asset) => asset.href && !/\.(png|jpe?g|gif|webp|svg)$/i.test(asset.href))
        .map((asset) => ({ title: item.title, asset })),
    ),
  };

  const launchBrowser = () => puppeteer.launch({ headless: true, args: ["--allow-file-access-from-files"] });
  const rawRows = rawSummary.pages_detail;
  const rawPages = [];
  const batchSize = 120;
  for (let offset = 0; offset < rawRows.length; offset += batchSize) {
    const batch = rawRows.slice(offset, offset + batchSize);
    const browser = await launchBrowser();
    try {
      const batchResults = await pool(batch, 6, async (row) => auditRawPage(browser, row));
      rawPages.push(...batchResults);
      console.log(`audited ${rawPages.length}/${rawRows.length}`);
    } finally {
      await browser.close().catch(() => undefined);
    }
  }
  const browser = await launchBrowser();
  try {
    const viewerBrowser = await auditViewer(browser, payload);
    const failedRawPages = rawPages.filter((row) => !row.ok);
    const totals = rawPages.reduce(
      (acc, row) => {
        acc.imageNodes += row.imageNodes || 0;
        acc.loadedImages += row.loadedImages || 0;
        acc.brokenImages += row.brokenImages || 0;
        acc.pendingImages += row.pendingImages || 0;
        acc.placeholderImages += row.placeholderImages || 0;
        acc.attachmentLinks += row.attachmentLinks || 0;
        return acc;
      },
      { imageNodes: 0, loadedImages: 0, brokenImages: 0, pendingImages: 0, placeholderImages: 0, attachmentLinks: 0 },
    );
    const finishedAt = new Date();
    const audit = {
      started_at: startedAt.toISOString(),
      finished_at: finishedAt.toISOString(),
      elapsed_seconds: Math.round((finishedAt.getTime() - startedAt.getTime()) / 100) / 10,
      raw_review_summary: {
        pages: rawSummary.pages,
        ok_pages: rawSummary.ok_pages,
        missing_content_pages: rawSummary.missing_content_pages,
        local_images: rawSummary.local_images,
        missing_images: rawSummary.missing_images,
        source_missing_images: rawSummary.source_missing_images,
        unavailable_images: rawSummary.unavailable_images,
        local_attachments: rawSummary.local_attachments,
        missing_attachments: rawSummary.missing_attachments,
      },
      browser_totals: totals,
      viewer_static: {
        entities: viewerStatic.entities,
        excluded: viewerStatic.excluded,
        entitiesWithRawReview: viewerStatic.entitiesWithRawReview,
        missingAttachmentAssets: viewerStatic.missingAttachmentAssets.length,
        unavailableImageAssets: viewerStatic.unavailableImageAssets.length,
        nonPreviewableImageAssets: viewerStatic.nonPreviewableImageAssets.length,
      },
      viewer_browser: viewerBrowser,
      failed_raw_pages: failedRawPages,
      missing_attachment_asset_examples: viewerStatic.missingAttachmentAssets.slice(0, 20),
      unavailable_image_asset_examples: viewerStatic.unavailableImageAssets.slice(0, 20),
      non_previewable_image_asset_examples: viewerStatic.nonPreviewableImageAssets.slice(0, 20),
      ok:
        failedRawPages.length === 0 &&
        totals.brokenImages === 0 &&
        totals.pendingImages === 0 &&
        viewerStatic.missingAttachmentAssets.length === 0 &&
        viewerStatic.nonPreviewableImageAssets.length === 0 &&
        viewerBrowser.ok,
    };
    fs.writeFileSync(AUDIT_PATH, `${JSON.stringify(audit, null, 2)}\n`, "utf8");
    console.log(JSON.stringify({ ok: audit.ok, audit_path: AUDIT_PATH, failed_raw_pages: failedRawPages.length, ...totals }, null, 2));
  } finally {
    await browser.close();
  }
  if (!readJson(AUDIT_PATH).ok) process.exitCode = 1;
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
