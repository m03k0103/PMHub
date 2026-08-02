const path = require('path');

function runTests() {
  console.log("--------------------------------------------------");
  console.log(" [テスト 3/3] public/app.js escapeHtml Utility Test");
  console.log("--------------------------------------------------");

  // Mock global objects necessary to load app.js in Node environment
  global.document = { addEventListener: () => {} };

  const appJsPath = path.join(__dirname, '..', 'public', 'app.js');
  let escapeHtml;

  try {
    const app = require(appJsPath);
    escapeHtml = app.escapeHtml;
  } catch (e) {
    console.error(`  [FAIL] Could not require app.js: ${e.message}`);
    process.exit(1);
  }

  if (typeof escapeHtml !== 'function') {
    console.error("  [FAIL] escapeHtml is not exported from app.js as a function");
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

  // Tests
  assertEqual('Null input', escapeHtml(null), '');
  assertEqual('Undefined input', escapeHtml(undefined), '');
  assertEqual('Empty string', escapeHtml(''), '');
  assertEqual('No special characters', escapeHtml('hello world'), 'hello world');
  assertEqual('Escapes &', escapeHtml('bread & butter'), 'bread &amp; butter');
  assertEqual('Escapes < and >', escapeHtml('<div>'), '&lt;div&gt;');
  assertEqual('Escapes "', escapeHtml('he said "hello"'), 'he said &quot;hello&quot;');
  assertEqual("Escapes '", escapeHtml("it's a test"), "it&#039;s a test");
  assertEqual('Escapes multiple instances', escapeHtml('<script>alert("XSS & hack")</script>'), '&lt;script&gt;alert(&quot;XSS &amp; hack&quot;)&lt;/script&gt;');

  if (failed > 0) {
    console.error(`\n  => ❌ ${failed} test(s) failed (${passed} passed).`);
    process.exit(1);
  } else {
    console.log(`  => ✅ All ${passed} escapeHtml tests passed.`);
    process.exit(0);
  }
}

runTests();
