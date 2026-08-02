const test = require('node:test');
const assert = require('node:assert');
const { capitalize } = require('./app.js');

test('capitalize utility function', async (t) => {
  await t.test('should capitalize the first letter of a typical string', () => {
    assert.strictEqual(capitalize('hello'), 'Hello');
    assert.strictEqual(capitalize('world'), 'World');
    assert.strictEqual(capitalize('javascript'), 'Javascript');
  });

  await t.test('should not change already capitalized strings', () => {
    assert.strictEqual(capitalize('Hello'), 'Hello');
    assert.strictEqual(capitalize('WORLD'), 'WORLD');
  });

  await t.test('should handle single character strings', () => {
    assert.strictEqual(capitalize('a'), 'A');
    assert.strictEqual(capitalize('Z'), 'Z');
  });

  await t.test('should handle empty strings', () => {
    assert.strictEqual(capitalize(''), '');
  });

  await t.test('should return empty string for non-string inputs', () => {
    assert.strictEqual(capitalize(null), '');
    assert.strictEqual(capitalize(undefined), '');
    assert.strictEqual(capitalize(123), '');
    assert.strictEqual(capitalize({}), '');
    assert.strictEqual(capitalize([]), '');
    assert.strictEqual(capitalize(true), '');
  });
});
