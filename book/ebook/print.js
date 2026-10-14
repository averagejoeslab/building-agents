// print.js IN.html OUT.pdf NUMBERED START: print a page to PDF with Chromium; NUMBERED adds a page-number footer.
const { chromium } = require('/opt/node-tools/node_modules/playwright');
(async () => {
  const [inp, out, numbered] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + inp, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  const footer = `<div style="width:100%;font-family:Inter,sans-serif;font-size:7.5pt;color:#8a857c;text-align:center;letter-spacing:.08em">
    <span class="pageNumber"></span></div>`;
  await page.pdf({
    path: out, width: '6in', height: '9in', printBackground: true, preferCSSPageSize: true,
    displayHeaderFooter: numbered === '1', headerTemplate: '<div></div>', footerTemplate: footer,
  });
  await browser.close();
})();
