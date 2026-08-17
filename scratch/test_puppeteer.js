const puppeteer = require('puppeteer');

(async () => {
  try {
    const browser = await puppeteer.launch({ headless: true });
    const page = await browser.newPage();
    
    page.on('console', msg => console.log('PAGE LOG:', msg.text()));
    page.on('pageerror', error => console.log('PAGE ERROR:', error.message));
    page.on('response', response => {
      if (!response.ok()) {
        console.log('HTTP ERR:', response.status(), response.url());
      }
    });

    console.log('Navigating...');
    await page.goto('http://localhost:8000/admin/admin_dashboard.html#councils', { waitUntil: 'networkidle2' });
    
    // Wait a bit just in case
    await new Promise(r => setTimeout(r, 2000));
    
    const councilCount = await page.evaluate(() => {
      return document.querySelectorAll('#councilList .council-card').length;
    });
    console.log('Council Cards Rendered:', councilCount);
    
    const isEmpty = await page.evaluate(() => {
      return !!document.querySelector('#councilList .empty-state');
    });
    console.log('Is Empty State?:', isEmpty);

    const activeTab = await page.evaluate(() => {
      const active = document.querySelector('.tab-content.active');
      return active ? active.id : null;
    });
    console.log('Active Tab:', activeTab);

    const errorLogs = await page.evaluate(() => {
      return window.COUNCILS ? window.COUNCILS.length : 'window.COUNCILS is undefined';
    });
    console.log('window.COUNCILS length:', errorLogs);

    await browser.close();
  } catch(e) {
    console.error('Puppeteer Script Error:', e);
  }
})();
