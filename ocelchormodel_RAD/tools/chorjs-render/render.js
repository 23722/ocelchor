#!/usr/bin/env node
/* Headless chor-js renderer.
 *
 * Usage:  node render.js <in.bpmn> [more.bpmn ...]
 *
 * For each input, renders with the real chor-js (the compiled demo bundle,
 * identical to bpt-lab.org/chor-js-demo) in headless Chrome and writes next
 * to it:
 *   <in>.chorjs.svg          — the rendered SVG
 *   <in>.chorjs.report.json  — { importWarnings, defined, rendered, missing }
 *
 * The report makes render regressions machine-checkable: `missing` lists
 * semantic elements that chor-js failed to draw.
 */

const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer-core');

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PAGE = 'file://' + path.join(__dirname, 'render.html');

async function main() {
  const inputs = process.argv.slice(2);
  if (!inputs.length) {
    console.error('usage: node render.js <in.bpmn> [more.bpmn ...]');
    process.exit(1);
  }

  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--force-device-scale-factor=1'],
  });

  try {
    const page = await browser.newPage();
    page.on('pageerror', (e) => console.error('  [pageerror]', String(e).slice(0, 200)));
    await page.goto(PAGE, { waitUntil: 'load' });
    await page.waitForFunction('!!window.harnessReady', { timeout: 20000 });

    for (const input of inputs) {
      const xml = fs.readFileSync(input, 'utf8');
      const r = await page.evaluate((xml) => window.renderChoreo(xml), xml);
      const result = { importWarnings: r.warnings, error: r.error, rendered: r.rendered, svg: r.svg };

      // defined semantic flow elements (from the XML, namespace-agnostic)
      const defined = [...xml.matchAll(
        /<[\w]+:(choreographyTask|subChoreography|startEvent|endEvent|exclusiveGateway|parallelGateway|sequenceFlow)\s[^>]*id="([^"]+)"/g,
      )].map((m) => m[2]);
      const renderedSet = new Set(result.rendered);
      const missing = defined.filter((id) => !renderedSet.has(id));

      const base = input.replace(/\.bpmn$/, '');
      if (result.svg) fs.writeFileSync(base + '.chorjs.svg', result.svg);
      fs.writeFileSync(base + '.chorjs.report.json', JSON.stringify({
        input,
        error: result.error,
        importWarnings: result.importWarnings,
        defined: defined.length,
        rendered: result.rendered.length,
        missing,
      }, null, 2));

      const status = result.error
        ? `IMPORT ERROR: ${result.error.slice(0, 120)}`
        : `${defined.length - missing.length}/${defined.length} defined elements rendered`
          + (missing.length ? `  MISSING ${missing.length}` : '')
          + (result.importWarnings.length ? `  (${result.importWarnings.length} warnings)` : '');
      console.log(`${path.basename(path.dirname(input))}: ${status}`);
    }
  } finally {
    await browser.close();
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
