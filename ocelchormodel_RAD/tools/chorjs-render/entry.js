// Minimal chor-js render API for the headless harness.
import Viewer from 'chor-js/lib/Viewer';

const viewer = new Viewer({ container: '#canvas' });

window.renderChoreo = async function (xml) {
  const out = { warnings: [], error: null, rendered: [], svg: null };
  try {
    const res = await viewer.importXML(xml);
    out.warnings = (res.warnings || []).map((w) => String((w && w.message) || w));
  } catch (e) {
    out.error = String((e && e.message) || e);
    if (e && e.warnings) out.warnings = e.warnings.map((w) => String((w && w.message) || w));
    return out;
  }
  out.rendered = viewer.get('elementRegistry').getAll().map((el) => el.id);
  const { svg } = await viewer.saveSVG();
  out.svg = svg;
  return out;
};
window.harnessReady = true;
