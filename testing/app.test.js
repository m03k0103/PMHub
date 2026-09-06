const test = require('node:test');
const assert = require('node:assert');
const { escapeHtml, sanitizeUrl, formatDate, getFiscalYear } = require('../docs/app.js');

test('sanitizeUrl utility function (Security / XSS prevention)', async (t) => {
  await t.test('allows safe http and https URLs', () => {
    assert.strictEqual(sanitizeUrl('https://example.com/doc.pdf'), 'https://example.com/doc.pdf');
    assert.strictEqual(sanitizeUrl('http://example.com/index.html'), 'http://example.com/index.html');
  });

  await t.test('allows safe relative paths, query strings, and anchors', () => {
    assert.strictEqual(sanitizeUrl('/path/to/resource'), '/path/to/resource');
    assert.strictEqual(sanitizeUrl('./relative/doc.pdf'), './relative/doc.pdf');
    assert.strictEqual(sanitizeUrl('?search=test'), '?search=test');
    assert.strictEqual(sanitizeUrl('#section1'), '#section1');
  });

  await t.test('blocks javascript: URLs and variations', () => {
    assert.strictEqual(sanitizeUrl('javascript:alert(1)'), '#');
    assert.strictEqual(sanitizeUrl('JAVASCRIPT:alert(1)'), '#');
    assert.strictEqual(sanitizeUrl('  javascript:alert(1)  '), '#');
  });

  await t.test('blocks control character obfuscation in javascript: URLs', () => {
    assert.strictEqual(sanitizeUrl('java\0script:alert(1)'), '#');
    assert.strictEqual(sanitizeUrl('java\x01script:alert(1)'), '#');
  });

  await t.test('blocks data: and vbscript: URLs', () => {
    assert.strictEqual(sanitizeUrl('data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg=='), '#');
    assert.strictEqual(sanitizeUrl('vbscript:msgbox(1)'), '#');
  });

  await t.test('returns # for null, undefined, or empty values', () => {
    assert.strictEqual(sanitizeUrl(null), '#');
    assert.strictEqual(sanitizeUrl(undefined), '#');
    assert.strictEqual(sanitizeUrl(''), '#');
  });
});

test('escapeHtml utility function', async (t) => {
  await t.test('escapes HTML special characters', () => {
    assert.strictEqual(escapeHtml('<script>alert("xss & test")</script>'), '&lt;script&gt;alert(&quot;xss &amp; test&quot;)&lt;/script&gt;');
    assert.strictEqual(escapeHtml("it's a test"), "it&#039;s a test");
  });

  await t.test('handles empty or non-string inputs', () => {
    assert.strictEqual(escapeHtml(''), '');
    assert.strictEqual(escapeHtml(null), '');
    assert.strictEqual(escapeHtml(undefined), '');
  });
});

test('formatDate utility function', async (t) => {
  await t.test('replaces dashes with slashes', () => {
    assert.strictEqual(formatDate('2026-08-02'), '2026/08/02');
  });

  await t.test('handles empty inputs', () => {
    assert.strictEqual(formatDate(''), '');
    assert.strictEqual(formatDate(null), '');
  });

  await t.test('formats 2099 dummy date as 開催日不明（要確認）', () => {
    assert.strictEqual(formatDate('2099/01/01'), '開催日不明（要確認）');
    assert.strictEqual(formatDate('2099-01-01'), '開催日不明（要確認）');
  });
});

test('getFiscalYear utility function (Japanese Fiscal Year: Apr - Mar)', async (t) => {
  await t.test('calculates fiscal year correctly from string dates', () => {
    assert.strictEqual(getFiscalYear('2026/04/01'), 2026);
    assert.strictEqual(getFiscalYear('2026-08-30'), 2026);
    assert.strictEqual(getFiscalYear('2026/12/31'), 2026);
    assert.strictEqual(getFiscalYear('2027-01-15'), 2026);
    assert.strictEqual(getFiscalYear('2027/03/31'), 2026);
    assert.strictEqual(getFiscalYear('2025/04/01'), 2025);
    assert.strictEqual(getFiscalYear('2026/03/31'), 2025);
  });

  await t.test('calculates fiscal year correctly from Date objects', () => {
    assert.strictEqual(getFiscalYear(new Date(2026, 3, 1)), 2026); // Apr 1, 2026
    assert.strictEqual(getFiscalYear(new Date(2027, 2, 31)), 2026); // Mar 31, 2027
    assert.strictEqual(getFiscalYear(new Date(2026, 2, 31)), 2025); // Mar 31, 2026
  });

  await t.test('handles invalid or empty inputs', () => {
    assert.strictEqual(getFiscalYear(''), null);
    assert.strictEqual(getFiscalYear(null), null);
    assert.strictEqual(getFiscalYear(undefined), null);
    assert.strictEqual(getFiscalYear('invalid-date'), null);
  });
});

