async page => {
  const targetDate = 'May 29, 2026';
  const minSeconds = 12 * 60 * 60;
  const maxScrollSteps = 160;

  function secondsFromLabel(label) {
    const clean = String(label || '').replace(/[\u202f\u00a0]/g, ' ');
    const m = clean.match(/May 29, 2026, (\d{1,2}):(\d{2}):(\d{2}) (AM|PM)/);
    if (!m) return null;
    let hour = Number(m[1]);
    if (m[4] === 'PM' && hour !== 12) hour += 12;
    if (m[4] === 'AM' && hour === 12) hour = 0;
    return hour * 3600 + Number(m[2]) * 60 + Number(m[3]);
  }

  function stampFromLabel(label) {
    const seconds = secondsFromLabel(label);
    if (seconds == null) return null;
    const hour = Math.floor(seconds / 3600);
    const minute = Math.floor((seconds % 3600) / 60);
    const second = seconds % 60;
    return (
      '20260529_' +
      String(hour).padStart(2, '0') +
      String(minute).padStart(2, '0') +
      String(second).padStart(2, '0')
    );
  }

  await page.goto('https://photos.google.com/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);

  return await page.evaluate(
    async ({ targetDate, minSeconds, maxScrollSteps }) => {
      function secondsFromLabelInPage(label) {
        const clean = String(label || '').replace(/[\u202f\u00a0]/g, ' ');
        const m = clean.match(/May 29, 2026, (\d{1,2}):(\d{2}):(\d{2}) (AM|PM)/);
        if (!m) return null;
        let hour = Number(m[1]);
        if (m[4] === 'PM' && hour !== 12) hour += 12;
        if (m[4] === 'AM' && hour === 12) hour = 0;
        return hour * 3600 + Number(m[2]) * 60 + Number(m[3]);
      }

      function stampFromLabelInPage(label) {
        const seconds = secondsFromLabelInPage(label);
        if (seconds == null) return null;
        const hour = Math.floor(seconds / 3600);
        const minute = Math.floor((seconds % 3600) / 60);
        const second = seconds % 60;
        return (
          '20260529_' +
          String(hour).padStart(2, '0') +
          String(minute).padStart(2, '0') +
          String(second).padStart(2, '0')
        );
      }

      const main = document.querySelector('[role=main]');
      const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
      const seen = new Map();
      const snapshots = [];
      let noTargetScreens = 0;
      let sawBeforeNoon = false;

      if (main) main.scrollTo(0, 0);
      else window.scrollTo(0, 0);
      await sleep(700);

      for (let step = 0; step < maxScrollSteps; step++) {
        const nodes = [
          ...document.querySelectorAll(
            'a[aria-label^="Photo -"], a[aria-label^="Video -"]'
          ),
        ];
        let visibleTarget = 0;
        let visibleToday = 0;
        let visibleBeforeNoon = 0;

        for (const node of nodes) {
          const label = node.getAttribute('aria-label') || '';
          const href = node.href || '';
          if (!href || !label.includes(targetDate)) continue;
          visibleToday++;
          const seconds = secondsFromLabelInPage(label);
          if (seconds == null) continue;
          if (seconds < minSeconds) {
            visibleBeforeNoon++;
            sawBeforeNoon = true;
            continue;
          }
          visibleTarget++;
          if (!seen.has(href)) {
            seen.set(href, {
              href,
              label,
              stamp: stampFromLabelInPage(label),
              secondsFromMidnight: seconds,
            });
          }
        }

        snapshots.push({
          step,
          scrollTop: main ? main.scrollTop : document.scrollingElement.scrollTop,
          visibleToday,
          visibleTarget,
          visibleBeforeNoon,
          total: seen.size,
        });

        if (step > 0 && visibleTarget === 0) noTargetScreens++;
        else noTargetScreens = 0;
        if (seen.size > 0 && (noTargetScreens >= 4 || sawBeforeNoon)) break;

        const amount = Math.max(
          500,
          ((main && main.clientHeight) || window.innerHeight) * 0.85
        );
        if (main) main.scrollBy(0, amount);
        else window.scrollBy(0, amount);
        await sleep(450);
      }

      const items = [...seen.values()].sort(
        (a, b) => a.secondsFromMidnight - b.secondsFromMidnight
      );
      return {
        account: 'bispro89@gmail.com',
        targetDate,
        minTime: '12:00:00',
        count: items.length,
        items,
        snapshots,
      };
    },
    { targetDate, minSeconds, maxScrollSteps }
  );
}
