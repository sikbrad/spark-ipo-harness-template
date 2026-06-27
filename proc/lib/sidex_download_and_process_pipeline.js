#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { chromium } = require('/Users/gq/.nvm/versions/node/v22.21.1/lib/node_modules/@playwright/cli/node_modules/playwright-core');

const cwd = '/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04';
const itemsPath = path.join(cwd, 'output/google-photos/2026-05-29-bispro89/noon-items.json');
const originalsDir = path.join(cwd, 'output/sidex-2026/originals');
const photosDir = path.join(cwd, 'output/sidex-2026/photos');
const manifestPath = path.join(cwd, 'output/sidex-2026/sidex-photo-processing-manifest.json');
const profileDir = '/Users/gq/Library/Caches/ms-playwright/daemon/83e26cdd240f9c2e/ud-google-bispro-chrome';
const processConcurrency = 4;

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
  if (!fs.existsSync(manifestPath) || fs.statSync(manifestPath).size === 0) {
    return {
      schema_version: 1,
      started_at: new Date().toISOString(),
      source_items: itemsPath,
      total_items: 0,
      completed: [],
      failed: [],
    };
  }
  return JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
}

function completedMap(manifest) {
  return new Map(
    (manifest.completed || [])
      .filter(item => item.href && item.filename)
      .map(item => [item.href, item])
  );
}

function refreshCounts(manifest) {
  const uniqueCompleted = new Set((manifest.completed || []).map(item => item.href).filter(Boolean));
  manifest.completed_count = uniqueCompleted.size;
  manifest.failed_count = (manifest.failed || []).length;
  manifest.updated_at = new Date().toISOString();
}

function writeManifest(manifest) {
  refreshCounts(manifest);
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
}

function processPhoto(record, manifest) {
  return new Promise(resolve => {
    const args = [
      'proc/lib/sidex_process_photo.py',
      '--input',
      record.original_file,
      '--output-dir',
      photosDir,
      '--source-href',
      record.href,
      '--source-label',
      record.label,
      '--google-stamp',
      record.stamp,
    ];
    const child = spawn('python3', args, { cwd });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', chunk => {
      stdout += chunk.toString();
    });
    child.stderr.on('data', chunk => {
      stderr += chunk.toString();
    });
    child.on('close', code => {
      record.process_stdout = stdout.trim();
      record.process_stderr = stderr.trim();
      record.process_status = code;
      record.completed_at = new Date().toISOString();
      if (code === 0) {
        if (!completedMap(manifest).has(record.href)) manifest.completed.push(record);
      } else {
        manifest.failed.push({
          ...record,
          error: `sidex_process_photo.py exited ${code}`,
          failed_at: new Date().toISOString(),
        });
      }
      writeManifest(manifest);
      resolve(record);
    });
  });
}

function existingOriginalForStamp(stamp) {
  const files = fs.existsSync(originalsDir) ? fs.readdirSync(originalsDir) : [];
  return files.find(name => name.startsWith(stamp) && /\.(jpe?g|png|heic|webp|gif|mp4|mov)$/i.test(name));
}

async function main() {
  fs.mkdirSync(originalsDir, { recursive: true });
  fs.mkdirSync(photosDir, { recursive: true });

  const source = JSON.parse(fs.readFileSync(itemsPath, 'utf8'));
  const items = source.items || [];
  const manifest = readManifest();
  manifest.total_items = items.length;
  manifest.source_count = source.count;
  manifest.pipeline = 'sidex_download_and_process_pipeline';

  const used = new Set(fs.readdirSync(originalsDir).filter(name => /^20260529/.test(name)));
  let completedByHref = completedMap(manifest);
  const active = new Set();

  const context = await chromium.launchPersistentContext(profileDir, {
    channel: 'chrome',
    headless: false,
    acceptDownloads: true,
    viewport: { width: 1280, height: 720 },
  });
  const page = context.pages()[0] || await context.newPage();
  page.setDefaultTimeout(60000);

  async function enqueue(record) {
    while (active.size >= processConcurrency) {
      await Promise.race(active);
    }
    const promise = processPhoto(record, manifest).then(done => {
      active.delete(promise);
      console.log(`[${manifest.completed_count || 0}/${items.length}] processed ${done.filename}`);
      return done;
    });
    active.add(promise);
  }

  try {
    for (let i = 0; i < items.length; i++) {
      completedByHref = completedMap(manifest);
      const item = items[i];
      const existing = completedByHref.get(item.href);
      if (existing) {
        const sidecar = path.join(photosDir, `${path.parse(existing.filename).name}_text.json`);
        if (fs.existsSync(path.join(photosDir, existing.filename)) && fs.existsSync(sidecar)) continue;
      }

      let filename = existingOriginalForStamp(item.stamp);
      let originalPath = filename ? path.join(originalsDir, filename) : null;
      const record = {
        index: i + 1,
        total: items.length,
        href: item.href,
        label: item.label,
        stamp: item.stamp,
        started_at: new Date().toISOString(),
      };

      if (!originalPath) {
        try {
          await page.goto(item.href, { waitUntil: 'domcontentloaded', timeout: 60000 });
          await page.waitForTimeout(1000);
          const downloadPromise = page.waitForEvent('download', { timeout: 90000 });
          await page.keyboard.press('Shift+D');
          const download = await downloadPromise;
          const suggested = download.suggestedFilename();
          const safeSuggested = safeName(suggested);
          const base = hasTimestamp(safeSuggested)
            ? safeSuggested
            : `${item.stamp}__${safeSuggested || `google-photo${extOf(suggested)}`}`;
          filename = uniqueName(base, used);
          originalPath = path.join(originalsDir, filename);
          await download.saveAs(originalPath);
          record.suggested = suggested;
        } catch (error) {
          manifest.failed.push({
            ...record,
            error: String(error && error.stack ? error.stack : error),
            failed_at: new Date().toISOString(),
          });
          writeManifest(manifest);
          console.log(`[${manifest.completed_count || 0}/${items.length}] download failed item ${i + 1}: ${item.stamp}`);
          continue;
        }
      }

      record.filename = filename;
      record.original_file = originalPath;
      await enqueue(record);
    }
  } finally {
    await context.close();
  }

  await Promise.all(active);
  manifest.finished_at = new Date().toISOString();
  writeManifest(manifest);
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
