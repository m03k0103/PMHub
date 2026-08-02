const path = require('path');

function runTests() {
  console.log("--------------------------------------------------");
  console.log(" [テスト 3/3] public/app.js Security Utility Test (escapeHtml & sanitizeUrl)");
  console.log("--------------------------------------------------");

  // Mock global objects necessary to load app.js in Node environment
  global.document = { addEventListener: () => {} };

  const appJsPath = path.join(__dirname, '..', 'public', 'app.js');
  let escapeHtml, sanitizeUrl;

  try {
    const app = require(appJsPath);
    escapeHtml = app.escapeHtml;
    sanitizeUrl = app.sanitizeUrl;
  } catch (e) {
    console.error(`  [FAIL] Could not require app.js: ${e.message}`);
    process.exit(1);
  }

  if (typeof escapeHtml !== 'function' || typeof sanitizeUrl !== 'function') {
    console.error("  [FAIL] escapeHtml or sanitizeUrl is not exported from app.js");
    process.exit(1);
  }

  let failed = 0;
  let passed = 0;
  function assertEqual(name, actual, expected) {
    if (actual !== expected) {
      console.error(`  [FAIL] ${name}\n    Expected: ${expected}\n    Actual:   ${actual}`);
      failed++;
    } else {
      passed++;
    }
  }

  // escapeHtml Tests
  assertEqual('Null input', escapeHtml(null), '');
  assertEqual('Undefined input', escapeHtml(undefined), '');
  assertEqual('Empty string', escapeHtml(''), '');
  assertEqual('No special characters', escapeHtml('hello world'), 'hello world');
  assertEqual('Escapes &', escapeHtml('bread & butter'), 'bread &amp; butter');
  assertEqual('Escapes < and >', escapeHtml('<div>'), '&lt;div&gt;');
  assertEqual('Escapes "', escapeHtml('he said "hello"'), 'he said &quot;hello&quot;');
  assertEqual("Escapes '", escapeHtml("it's a test"), "it&#039;s a test");
  assertEqual('Escapes multiple instances', escapeHtml('<script>alert("XSS & hack")</script>'), '&lt;script&gt;alert(&quot;XSS &amp; hack&quot;)&lt;/script&gt;');

  // sanitizeUrl Tests
  assertEqual('Allows safe https URL', sanitizeUrl('https://example.com/file.pdf'), 'https://example.com/file.pdf');
  assertEqual('Allows safe http URL', sanitizeUrl('http://example.com/page.html'), 'http://example.com/page.html');
  assertEqual('Allows relative path', sanitizeUrl('/path/to/resource'), '/path/to/resource');
  assertEqual('Blocks javascript: scheme', sanitizeUrl('javascript:alert(1)'), '#');
  assertEqual('Blocks JAVASCRIPT: scheme (uppercase)', sanitizeUrl('JAVASCRIPT:alert(1)'), '#');
  assertEqual('Blocks javascript: with control char', sanitizeUrl('java\0script:alert(1)'), '#');
  assertEqual('Blocks data: scheme', sanitizeUrl('data:text/html;base64,PHNjcmlwdD4='), '#');
  assertEqual('Blocks vbscript: scheme', sanitizeUrl('vbscript:msgbox(1)'), '#');
  assertEqual('Returns # for null', sanitizeUrl(null), '#');
  assertEqual('Returns # for empty string', sanitizeUrl(''), '#');

  if (failed > 0) {
    console.error(`\n  => ❌ ${failed} test(s) failed (${passed} passed).`);
    process.exit(1);
  } else {
    console.log(`  => ✅ All ${passed} security utility tests passed.`);
    process.exit(0);
  }
}

runTests();
