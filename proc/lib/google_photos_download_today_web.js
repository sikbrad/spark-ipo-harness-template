async page => {
  const outDir =
    '/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04/output/google-photos/2026-05-29-bispro89';
  const targetDate = 'May 29, 2026';
  const maxScrollSteps = 100;

  function sanitizeFilename(name) {
    return String(name || '')
      .replace(/[\\/:*?"<>|]/g, '_')
      .replace(/\s+/g, '_')
      .replace(/^_+|_+$/g, '');
  }

  function extensionFrom(name) {
    const m = String(name || '').match(/(\.[^.]+)$/);
    return m ? m[1] : '.jpg';
  }

  function hasTimestamp(name) {
    const s = String(name || '');
    return (
      /2026[-_]?05[-_]?29.*\d{2}[-_]?\d{2}[-_]?\d{2}/.test(s) ||
      /20260529.*\d{6}/.test(s)
    );
  }

  function stampFromLabel(label) {
    const clean = String(label || '').replace(/[\u202f\u00a0]/g, ' ');
    const m = clean.match(/May 29, 2026, (\d{1,2}):(\d{2}):(\d{2}) (AM|PM)/);
    if (!m) return '20260529_000000';

    let hour = Number(m[1]);
    if (m[4] === 'PM' && hour !== 12) hour += 12;
    if (m[4] === 'AM' && hour === 12) hour = 0;

    return (
      '20260529_' +
      String(hour).padStart(2, '0') +
      m[2] +
      m[3]
    );
  }

  function uniqueName(base, used) {
    if (!used.has(base)) {
      used.add(base);
      return base;
    }
    const ext = extensionFrom(base);
    const stem = base.slice(0, base.length - ext.length);
    for (let i = 2; i < 1000; i++) {
      const candidate = stem + '_' + String(i).padStart(2, '0') + ext;
      if (!used.has(candidate)) {
        used.add(candidate);
        return candidate;
      }
    }
    throw new Error('Could not allocate unique filename for ' + base);
  }

  async function collectItems() {
    await page.goto('https://photos.google.com/?pli=1', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);

    const result = await page.evaluate(
      async ({ targetDate, maxScrollSteps }) => {
        const main = document.querySelector('[role=main]');
        const sleepInPage = ms => new Promise(resolve => setTimeout(resolve, ms));
        const seen = new Map();
        const snapshots = [];
        let noTargetScreens = 0;

        if (main) main.scrollTo(0, 0);
        else window.scrollTo(0, 0);
        await sleepInPage(600);

        for (let step = 0; step < maxScrollSteps; step++) {
          const nodes = [
            ...document.querySelectorAll(
              'a[aria-label^="Photo -"], a[aria-label^="Video -"]'
            ),
          ];
          let targetVisible = 0;
          let anyOlder = false;

          for (const node of nodes) {
            const label = node.getAttribute('aria-label') || '';
            const href = node.href || '';
            if (label.includes(targetDate)) {
              targetVisible++;
              if (!seen.has(href)) seen.set(href, { href, label });
            } else if (
              /May 2[0-8], 2026|May [0-9], 2026|April|March|February|January|2025/.test(
                label
              )
            ) {
              anyOlder = true;
            }
          }

          snapshots.push({
            step,
            scrollTop: main ? main.scrollTop : document.scrollingElement.scrollTop,
            targetVisible,
            anyOlder,
            total: seen.size,
          });

          if (step > 0 && targetVisible === 0) noTargetScreens++;
          else noTargetScreens = 0;
          if (seen.size > 0 && noTargetScreens >= 3) break;

          const amount = Math.max(
            500,
            ((main && main.clientHeight) || window.innerHeight) * 0.85
          );
          if (main) main.scrollBy(0, amount);
          else window.scrollBy(0, amount);
          await sleepInPage(450);
        }

        return {
          items: [...seen.values()],
          snapshots,
          finalScrollTop: main ? main.scrollTop : document.scrollingElement.scrollTop,
        };
      },
      { targetDate, maxScrollSteps }
    );

    return result;
  }

  const collection = await collectItems();
  const used = new Set();
  const downloads = [];

  for (let i = 0; i < collection.items.length; i++) {
    const item = collection.items[i];
    const stamp = stampFromLabel(item.label);

    await page.goto(item.href, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1400);

    let download;
    try {
      const downloadPromise = page.waitForEvent('download', { timeout: 30000 });
      await page.keyboard.press('Shift+D');
      download = await downloadPromise;
    } catch (error) {
      downloads.push({
        index: i + 1,
        href: item.href,
        label: item.label,
        stamp,
        ok: false,
        error: String(error && error.message ? error.message : error),
      });
      continue;
    }

    const suggested = download.suggestedFilename();
    const safeSuggested = sanitizeFilename(suggested);
    const baseName = hasTimestamp(safeSuggested)
      ? safeSuggested
      : stamp + '__' + (safeSuggested || 'google-photo' + extensionFrom(suggested));
    const filename = uniqueName(baseName, used);
    const dest = outDir + '/' + filename;

    try {
      await download.saveAs(dest);
      downloads.push({
        index: i + 1,
        href: item.href,
        label: item.label,
        stamp,
        ok: true,
        suggested,
        filename,
        dest,
      });
    } catch (error) {
      downloads.push({
        index: i + 1,
        href: item.href,
        label: item.label,
        stamp,
        ok: false,
        suggested,
        filename,
        dest,
        error: String(error && error.message ? error.message : error),
      });
    }

    await page.waitForTimeout(350);
  }

  return {
    account: 'bispro89@gmail.com',
    targetDate,
    collectedCount: collection.items.length,
    downloadedCount: downloads.filter(item => item.ok).length,
    failedCount: downloads.filter(item => !item.ok).length,
    collectionSnapshots: collection.snapshots,
    downloads,
  };
}
