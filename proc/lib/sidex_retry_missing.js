#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const { chromium } = require('/Users/gq/.nvm/versions/node/v22.21.1/lib/node_modules/@playwright/cli/node_modules/playwright-core');

const cwd = '/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04';
const itemsPath = path.join(cwd, 'output/google-photos/2026-05-29-bispro89/noon-items.json');
const originalsDir = path.join(cwd, 'output/sidex-2026/originals');
const photosDir = path.join(cwd, 'output/sidex-2026/photos');
const manifestPath = path.join(cwd, 'output/sidex-2026/sidex-photo-processing-manifest.json');
const profileDir = '/Users/gq/Library/Caches/ms-playwright/daemon/83e26cdd240f9c2e/ud-google-bispro-chrome';

function safeName(name) {
  return String(name || '')
    .replace(/[\\/:*?"<>|]/g, '_')
    .replace(/\s+/g, '_')
    .replace(/^_+|_+$/g, '');
}

function extOf(name) {
  const m = String(name || '').match(/(\.[^.]+)$/);
  return m ? m[1] : '.jpg';
}

function hasTimestamp(name) {
  const s = String(name || '');
  return /2026[-_]?05[-_]?29.*\d{6}/.test(s) || /20260529.*\d{6}/.test(s);
}

function uniqueName(base, used) {
  if (!used.has(base)) {
    used.add(base);
    return base;
  }
  const ext = extOf(base);
  const stem = base.slice(0, base.length - ext.length);
  for (let i = 2; i < 1000; i++) {
    const candidate = `${stem}_${String(i).padStart(2, '0')}${ext}`;
    if (!used.has(candidate)) {
      used.add(candidate);
      return candidate;
    }
  }
  throw new Error(`Could not allocate unique filename for ${base}`);
}

function readManifest() {
  return JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
}

function writeManifest(manifest) {
  const uniqueCompleted = new Set((manifest.completed || []).map(item => item.href).filter(Boolean));
  manifest.completed_count = uniqueCompleted.size;
  manifest.failed_count = (manifest.failed || []).length;
  manifest.updated_at = new Date().toISOString();
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
}

async function downloadWithFallback(page) {
  try {
    const downloadPromise = page.waitForEvent('download', { timeout: 45000 });
    await page.keyboard.press('Shift+D');
    return await downloadPromise;
  } catch (firstError) {
    await page.keyboard.press('Escape').catch(() => {});
    const downloadPromise = page.waitForEvent('download', { timeout: 60000 });
    await page.getByRole('button', { name: 'More options' }).click();
    await page.getByRole('menuitem', { name: /Download/ }).click();
    return await downloadPromise;
  }
}

async function main() {
  const source = JSON.parse(fs.readFileSync(itemsPath, 'utf8'));
  const manifest = readManifest();
  const completed = new Set((manifest.completed || []).map(item => item.href).filter(Boolean));
  const missing = source.items
    .map((item, index) => ({ ...item, index: index + 1, total: source.items.length }))
    .filter(item => !completed.has(item.href));
  const used = new Set(fs.readdirSync(originalsDir).filter(name => /^20260529/.test(name)));

  const context = await chromium.launchPersistentContext(profileDir, {
    channel: 'chrome',
    headless: false,
    acceptDownloads: true,
    viewport: { width: 1280, height: 720 },
  });
  const page = context.pages()[0] || await context.newPage();
  page.setDefaultTimeout(60000);

  try {
    for (const item of missing) {
      const record = {
        index: item.index,
        total: item.total,
        href: item.href,
        label: item.label,
        stamp: item.stamp,
        retry_started_at: new Date().toISOString(),
      };
      try {
        await page.goto(item.href, { waitUntil: 'domcontentloaded', timeout: 60000 });
        await page.waitForTimeout(1500);
        const download = await downloadWithFallback(page);
        const suggested = download.suggestedFilename();
        const safeSuggested = safeName(suggested);
        const base = hasTimestamp(safeSuggested)
          ? safeSuggested
          : `${item.stamp}__${safeSuggested || `google-photo${extOf(suggested)}`}`;
        const filename = uniqueName(base, used);
        const originalPath = path.join(originalsDir, filename);
        await download.saveAs(originalPath);

        const proc = spawnSync(
          'python3',
          [
            'proc/lib/sidex_process_photo.py',
            '--input',
            originalPath,
            '--output-dir',
            photosDir,
            '--source-href',
            item.href,
            '--source-label',
            item.label,
            '--google-stamp',
            item.stamp,
          ],
          { cwd, encoding: 'utf8' }
        );

        record.suggested = suggested;
        record.filename = filename;
        record.original_file = originalPath;
        record.process_stdout = proc.stdout.trim();
        record.process_stderr = proc.stderr.trim();
        record.process_status = proc.status;
        record.completed_at = new Date().toISOString();
        if (proc.status === 0) {
          manifest.completed.push(record);
          console.log(`retry ok item ${item.index}: ${filename}`);
        } else {
          record.error = `sidex_process_photo.py exited ${proc.status}`;
          record.failed_at = new Date().toISOString();
          manifest.failed.push(record);
          console.log(`retry processing failed item ${item.index}: ${record.error}`);
        }
      } catch (error) {
        record.error = String(error && error.stack ? error.stack : error);
        record.failed_at = new Date().toISOString();
        manifest.failed.push(record);
        console.log(`retry download failed item ${item.index}: ${record.error}`);
      }
      writeManifest(manifest);
    }
  } finally {
    await context.close();
  }
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
