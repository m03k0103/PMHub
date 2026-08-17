const jsdom = require('jsdom');
const { JSDOM } = jsdom;

const virtualConsole = new jsdom.VirtualConsole();
virtualConsole.on('error', (e) => {
  console.error('[JSDOM Console Error]', e);
});
virtualConsole.on('warn', (w) => {
  console.warn('[JSDOM Console Warn]', w);
});
virtualConsole.on('log', (l) => {
  console.log('[JSDOM Console Log]', l);
});
virtualConsole.on('jsdomError', (err) => {
  console.error('[JSDOM Unhandled Error]', err);
});

JSDOM.fromURL("http://localhost:8000/admin/admin_dashboard.html#councils", {
  runScripts: "dangerously",
  resources: "usable",
  virtualConsole
}).then(dom => {
  setTimeout(() => {
    console.log('--- TEST FINISHED ---');
    const counts = dom.window.document.getElementById('statApproved');
    console.log('statApproved:', counts ? counts.textContent : 'NULL');
    
    const listEl = dom.window.document.getElementById('councilList');
    if (listEl) {
      console.log('councilList HTML length:', listEl.innerHTML.length);
      console.log('councilList empty state?', listEl.innerHTML.includes('empty-state'));
    }
    process.exit(0);
  }, 2000);
}).catch(err => {
  console.error('Failed to load page:', err);
});
