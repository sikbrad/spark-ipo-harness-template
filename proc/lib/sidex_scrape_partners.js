async page => {
  const base = 'https://www.sidex.or.kr/exhibition/partner_search.php';
  const all = [];

  async function scrapePage(pageNo) {
    const url =
      pageNo === 1
        ? base
        : `${base}?&findType=&findword=&page=${pageNo}`;
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
    return await page.evaluate(pageNoInPage => {
      return [...document.querySelectorAll('table tbody tr')].map(row => {
        const cells = [...row.querySelectorAll('td')].map(cell =>
          (cell.innerText || '').replace(/\s+/g, ' ').trim()
        );
        const link = row.querySelector('a[href*="partner_view"]');
        return {
          page: pageNoInPage,
          no: cells[0] || '',
          name_logo_alt: row.querySelector('img')?.getAttribute('alt') || '',
          name_and_description: cells[2] || '',
          booth: cells[3] || '',
          href: link ? new URL(link.getAttribute('href'), location.href).href : null,
          row_text: cells.join(' | '),
        };
      });
    }, pageNo);
  }

  for (let pageNo = 1; pageNo <= 26; pageNo++) {
    const rows = await scrapePage(pageNo);
    all.push(...rows);
    if (rows.length === 0) break;
  }

  return {
    source: base,
    scraped_at: new Date().toISOString(),
    count: all.length,
    exhibitors: all,
  };
}
