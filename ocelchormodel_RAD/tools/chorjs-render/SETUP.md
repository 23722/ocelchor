# chor-js render harness — setup

Headless renderer that opens each discovered/converted BPMN choreography
model in the real, unmodified [chor-js](https://github.com/bptlab/chor-js)
(the same code as the [chor-js demo](https://bpt-lab.org/chor-js-demo/)) and
writes, next to each input model:

- `<model>.chorjs.svg` — the rendered diagram (gitignored; large,
  regenerable)
- `<model>.chorjs.report.json` — `{error, importWarnings, defined,
  rendered, missing}` (tracked; the render-regression evidence)

Only the thin driver files are tracked (`render.js`, `entry.js`,
`render.html`, `package.json`, `package-lock.json`, this file). The
third-party chor-js bundle and `node_modules/` are **not** in the repo and
must be set up once, explicitly, per clone:

## 1. Install the driver dependency

```bash
cd ocelchormodel_RAD/tools/chorjs-render
npm ci          # installs puppeteer-core (no bundled browser)
```

`render.js` drives an existing Chrome install; it expects

```
/Applications/Google Chrome.app/Contents/MacOS/Google Chrome
```

(edit the `CHROME` constant at the top of `render.js` for other
platforms/paths).

## 2. Build the chor-js bundle

`render.html` loads `chorjs-bundle.js`, a browser bundle of chor-js's
`Viewer` built from `entry.js`:

```bash
npm install chor-js parcel-bundler   # chor-js pulls in bpmn-js et al.
npx parcel build entry.js --out-file chorjs-bundle.js --no-source-maps
```

Any bundler works — the only contract is that loading `render.html` defines
`window.renderChoreo(xml)` (see `entry.js`).

## 3. Run

```bash
node render.js <model.bpmn> [more.bpmn ...]
```

**Run large sweeps in small batches and re-render failures in isolation:**
a genuine import failure contaminates subsequent imports in the same
harness session (spurious "Before setting a new visitor not all objects in
deferred have been visited" errors). A model's verdict only counts when
produced in a session where no earlier input failed — re-run each failed
input in its own `node render.js <one.bpmn>` invocation to get its true
report.
