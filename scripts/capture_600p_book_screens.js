const fs = require("fs");
const path = require("path");
const { chromium } = require("/Users/gq/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");

(async () => {
  const out = "data/vibecoding-book/ax-company-ipo-600p-2026-05-31/browser-screens";
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1000, height: 1400 }, deviceScaleFactor: 1 });
  const file = "file://" + path.resolve("data/vibecoding-book/ax-company-ipo-600p-2026-05-31/ax-vibecoding-company-ipo-book.html");
  await page.goto(file, { waitUntil: "load" });
  await page.locator("section.cover").screenshot({ path: path.join(out, "cover.png") });
  await page.locator("section.toc-page").screenshot({ path: path.join(out, "toc.png") });
  await page.locator("section.chapter-page").first().screenshot({ path: path.join(out, "chapter1.png") });
  await page.locator("section.chapter-page").nth(11).screenshot({ path: path.join(out, "chapter12.png") });
  await page.locator("section.chapter-page").nth(23).screenshot({ path: path.join(out, "chapter24.png") });
  await page.locator("section.back-cover").screenshot({ path: path.join(out, "back-cover.png") });
  const info = await page.evaluate(() => ({
    title: document.title,
    pages: document.querySelectorAll("section.page").length,
    chapters: document.querySelectorAll("section.chapter-page").length,
    figures: document.querySelectorAll("figure.book-figure img").length,
    rawMarkdownMarkers: Array.from(document.querySelectorAll("section")).some((el) => /(^|\n)#\s/.test(el.innerText)),
    h1First: document.querySelector("section.chapter-page h1")?.innerText || "",
    back: document.querySelector("section.back-cover h1")?.innerText || "",
  }));
  await browser.close();
  console.log(JSON.stringify(info, null, 2));
})();
