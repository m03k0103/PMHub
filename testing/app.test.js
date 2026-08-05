const test = require('node:test');
const assert = require('node:assert');
const { escapeHtml, sanitizeUrl, formatDate } = require('../docs/app.js');

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
});
