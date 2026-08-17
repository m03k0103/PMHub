const fs = require('fs');
const jsdom = require('jsdom');
const { JSDOM } = jsdom;

const html = fs.readFileSync('admin/admin_dashboard.html', 'utf8');
const dataJson = fs.readFileSync('docs/data.json', 'utf8');

const virtualConsole = new jsdom.VirtualConsole();
virtualConsole.on('error', (e) => {
  console.error('[JSDOM Error]', e);
});
virtualConsole.on('warn', (w) => {
  console.warn('[JSDOM Warn]', w);
});
virtualConsole.on('log', (l) => {
  console.log('[JSDOM Log]', l);
});
virtualConsole.on('jsdomError', (err) => {
  console.error('[JSDOM Unhandled Error]', err);
});

const dom = new JSDOM(html, {
  url: 'http://localhost:8000/admin/admin_dashboard.html#councils',
  runScripts: 'dangerously',
  resources: 'usable',
  virtualConsole
});

dom.window.fetch = async (url) => {
  console.log('[Mock Fetch]', url);
  if (url.includes('data.json')) {
    return {
      ok: true,
      json: async () => JSON.parse(dataJson)
    };
  }
  return { ok: false };
};

setTimeout(() => {
  console.log('--- TEST FINISHED ---');
  const counts = dom.window.document.getElementById('statApproved');
  console.log('statApproved:', counts ? counts.textContent : 'NULL');
  process.exit(0);
}, 2000);
