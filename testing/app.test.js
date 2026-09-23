const test = require('node:test');
const assert = require('node:assert');
const {
  escapeHtml,
  sanitizeUrl,
  formatDate,
  getFiscalYear,
  getStoredJson,
  setStoredJson,
  meetingMatchesDocType,
  isMeetingInDateRange,
  capitalize,
  sortMeetings,
  sortCouncils,
  normalizeForSearch
} = require('../docs/app.js');

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

test('getStoredJson & setStoredJson storage helper functions', async (t) => {
  const originalLocalStorage = global.localStorage;
  const mockStore = {};
  global.localStorage = {
    getItem: (k) => mockStore[k] !== undefined ? mockStore[k] : null,
    setItem: (k, v) => { mockStore[k] = String(v); }
  };

  try {
    await t.test('returns parsed JSON when valid JSON is stored', () => {
      setStoredJson('test_key', ['a', 'b']);
      assert.deepStrictEqual(getStoredJson('test_key', []), ['a', 'b']);
    });

    await t.test('returns default value when key does not exist', () => {
      assert.deepStrictEqual(getStoredJson('nonexistent_key', { fallback: true }), { fallback: true });
    });

    await t.test('returns default value safely when stored string is corrupted/invalid JSON', () => {
      global.localStorage.setItem('corrupt_key', '{invalid: json;');
      assert.deepStrictEqual(getStoredJson('corrupt_key', ['default']), ['default']);
    });
  } finally {
    global.localStorage = originalLocalStorage;
  }
});

test('meetingMatchesDocType helper function', async (t) => {
  await t.test('matches ALL docTypeFilter unconditionally', () => {
    assert.strictEqual(meetingMatchesDocType({}, 'ALL'), true);
    assert.strictEqual(meetingMatchesDocType(null, 'ALL'), true);
  });

  await t.test('matches MINUTES only when hasMinutes is true', () => {
    assert.strictEqual(meetingMatchesDocType({ hasMinutes: true }, 'MINUTES'), true);
    assert.strictEqual(meetingMatchesDocType({ hasMinutes: false }, 'MINUTES'), false);
    assert.strictEqual(meetingMatchesDocType({}, 'MINUTES'), false);
  });

  await t.test('matches MATERIALS only when materials array has items', () => {
    assert.strictEqual(meetingMatchesDocType({ materials: [{ name: 'Doc1' }] }, 'MATERIALS'), true);
    assert.strictEqual(meetingMatchesDocType({ materials: [] }, 'MATERIALS'), false);
    assert.strictEqual(meetingMatchesDocType({}, 'MATERIALS'), false);
  });

  await t.test('matches REPORT only when tags include 答申 or 報告書', () => {
    assert.strictEqual(meetingMatchesDocType({ tags: ['答申'] }, 'REPORT'), true);
    assert.strictEqual(meetingMatchesDocType({ tags: ['報告書', '中間整理'] }, 'REPORT'), true);
    assert.strictEqual(meetingMatchesDocType({ tags: ['通常会合'] }, 'REPORT'), false);
    assert.strictEqual(meetingMatchesDocType({}, 'REPORT'), false);
  });
});

test('isMeetingInDateRange helper function', async (t) => {
  const baseRef = new Date('2026/09/16');

  await t.test('matches ALL filter unconditionally', () => {
    assert.strictEqual(isMeetingInDateRange({ date: '2026/09/10' }, 'ALL', baseRef), true);
    assert.strictEqual(isMeetingInDateRange(null, 'ALL', baseRef), true);
  });

  await t.test('rejects meetings with invalid or missing date', () => {
    assert.strictEqual(isMeetingInDateRange({ date: '-' }, '7D', baseRef), false);
    assert.strictEqual(isMeetingInDateRange({ date: '' }, '7D', baseRef), false);
    assert.strictEqual(isMeetingInDateRange({}, '7D', baseRef), false);
  });

  await t.test('filters 7D, 30D, and PAST_YEAR relative to refDate', () => {
    assert.strictEqual(isMeetingInDateRange({ date: '2026/09/12' }, '7D', baseRef), true);
    assert.strictEqual(isMeetingInDateRange({ date: '2026/09/01' }, '7D', baseRef), false);
    assert.strictEqual(isMeetingInDateRange({ date: '2026/09/01' }, '30D', baseRef), true);
    assert.strictEqual(isMeetingInDateRange({ date: '2026/08/01' }, '30D', baseRef), false);
    assert.strictEqual(isMeetingInDateRange({ date: '2025/10/01' }, 'PAST_YEAR', baseRef), true);
    assert.strictEqual(isMeetingInDateRange({ date: '2025/08/01' }, 'PAST_YEAR', baseRef), false);
  });

  await t.test('filters Japanese Fiscal Year (YEAR, PREV_YEAR)', () => {
    // 2026/09/16 -> FY2026
    assert.strictEqual(isMeetingInDateRange({ date: '2026/05/01' }, 'YEAR', baseRef), true);
    assert.strictEqual(isMeetingInDateRange({ date: '2025/05/01' }, 'YEAR', baseRef), false);
    assert.strictEqual(isMeetingInDateRange({ date: '2025/05/01' }, 'PREV_YEAR', baseRef), true);
    assert.strictEqual(isMeetingInDateRange({ date: '2026/05/01' }, 'PREV_YEAR', baseRef), false);
  });
});

test('capitalize utility function', async (t) => {
  await t.test('capitalizes the first letter of string', () => {
    assert.strictEqual(capitalize('hello'), 'Hello');
    assert.strictEqual(capitalize('digital'), 'Digital');
    assert.strictEqual(capitalize('A'), 'A');
  });

  await t.test('handles empty or non-string inputs', () => {
    assert.strictEqual(capitalize(''), '');
    assert.strictEqual(capitalize(null), '');
    assert.strictEqual(capitalize(undefined), '');
  });
});

test('sortMeetings pure function', async (t) => {
  const sampleMeetings = [
    { id: 'm1', date: '2026/09/10', councilId: 'c1', materials: [{ name: 'doc1' }] },
    { id: 'm2', date: '2026/09/15', councilId: 'c2', materials: [{ name: 'doc1' }, { name: 'doc2' }, { name: 'doc3' }] },
    { id: 'm3', date: '2026/09/01', councilId: 'c1', materials: [] }
  ];
  const meetingCounts = { c1: 5, c2: 2 };

  await t.test('sorts by NEWEST (date descending)', () => {
    const sorted = sortMeetings(sampleMeetings, 'NEWEST', meetingCounts);
    assert.deepStrictEqual(sorted.map(m => m.id), ['m2', 'm1', 'm3']);
  });

  await t.test('sorts by OLDEST (date ascending)', () => {
    const sorted = sortMeetings(sampleMeetings, 'OLDEST', meetingCounts);
    assert.deepStrictEqual(sorted.map(m => m.id), ['m3', 'm1', 'm2']);
  });

  await t.test('sorts by DOCS_DESC and DOCS_ASC', () => {
    const sortedDesc = sortMeetings(sampleMeetings, 'DOCS_DESC', meetingCounts);
    assert.deepStrictEqual(sortedDesc.map(m => m.id), ['m2', 'm1', 'm3']);
    const sortedAsc = sortMeetings(sampleMeetings, 'DOCS_ASC', meetingCounts);
    assert.deepStrictEqual(sortedAsc.map(m => m.id), ['m3', 'm1', 'm2']);
  });

  await t.test('sorts by MEETINGS_DESC and MEETINGS_ASC', () => {
    const sortedDesc = sortMeetings(sampleMeetings, 'MEETINGS_DESC', meetingCounts);
    assert.deepStrictEqual(sortedDesc.map(m => m.id), ['m1', 'm3', 'm2']);
    const sortedAsc = sortMeetings(sampleMeetings, 'MEETINGS_ASC', meetingCounts);
    assert.deepStrictEqual(sortedAsc.map(m => m.id), ['m2', 'm1', 'm3']);
  });

  await t.test('does not mutate the original array (pure function)', () => {
    const originalCopy = [...sampleMeetings];
    sortMeetings(sampleMeetings, 'NEWEST', meetingCounts);
    assert.deepStrictEqual(sampleMeetings, originalCopy);
  });
});

test('sortCouncils pure function', async (t) => {
  const sampleCouncils = [
    { id: 'c1', name: '会議体B', latestDate: '2026/08/15' },
    { id: 'c2', name: '会議体A', latestDate: '2026/09/01' },
    { id: 'c3', name: '会議体C', latestDate: '-' }
  ];
  const meetingsMap = new Map([
    ['c1', [{ materials: [{ name: '1' }] }]],
    ['c2', [{ materials: [{ name: '1' }, { name: '2' }, { name: '3' }] }]],
    ['c3', []]
  ]);
  const meetingCounts = { c1: 10, c2: 3, c3: 0 };

  await t.test('sorts by NEWEST (date descending, - at end, tie-break by name)', () => {
    const sorted = sortCouncils(sampleCouncils, 'NEWEST', { meetingsMap, counts: meetingCounts });
    assert.deepStrictEqual(sorted.map(c => c.id), ['c2', 'c1', 'c3']);
  });

  await t.test('sorts by OLDEST (date ascending, - at end)', () => {
    const sorted = sortCouncils(sampleCouncils, 'OLDEST', { meetingsMap, counts: meetingCounts });
    assert.deepStrictEqual(sorted.map(c => c.id), ['c1', 'c2', 'c3']);
  });

  await t.test('sorts by DOCS_DESC and DOCS_ASC', () => {
    const sortedDesc = sortCouncils(sampleCouncils, 'DOCS_DESC', { meetingsMap, counts: meetingCounts });
    assert.deepStrictEqual(sortedDesc.map(c => c.id), ['c2', 'c1', 'c3']);
    const sortedAsc = sortCouncils(sampleCouncils, 'DOCS_ASC', { meetingsMap, counts: meetingCounts });
    assert.deepStrictEqual(sortedAsc.map(c => c.id), ['c3', 'c1', 'c2']);
  });

  await t.test('sorts by MEETINGS_DESC and MEETINGS_ASC', () => {
    const sortedDesc = sortCouncils(sampleCouncils, 'MEETINGS_DESC', { meetingsMap, counts: meetingCounts });
    assert.deepStrictEqual(sortedDesc.map(c => c.id), ['c1', 'c2', 'c3']);
    const sortedAsc = sortCouncils(sampleCouncils, 'MEETINGS_ASC', { meetingsMap, counts: meetingCounts });
    assert.deepStrictEqual(sortedAsc.map(c => c.id), ['c3', 'c2', 'c1']);
  });

  await t.test('does not mutate the original array (pure function)', () => {
    const originalCopy = [...sampleCouncils];
    sortCouncils(sampleCouncils, 'NEWEST', { meetingsMap, counts: meetingCounts });
    assert.deepStrictEqual(sampleCouncils, originalCopy);
  });
});

test('normalizeForSearch utility function (NFKC & Kangxi radicals / fullwidth absorption)', async (t) => {
  await t.test('normalizes fullwidth alphanumeric to ASCII lowercase', () => {
    assert.strictEqual(normalizeForSearch('ＡＩ推進'), 'ai推進');
    assert.strictEqual(normalizeForSearch('ＷＧ'), 'wg');
    assert.strictEqual(normalizeForSearch('第１回'), '第1回');
  });

  await t.test('normalizes Kangxi Radicals to standard CJK ideographs', () => {
    // ⼈ (U+2F08) -> 人 (U+4EBA), ⽂ (U+2F42) -> 文 (U+6587)
    assert.strictEqual(normalizeForSearch('⼈⼯知能'), '人工知能');
    assert.strictEqual(normalizeForSearch('⽂化審議会'), '文化審議会');
    assert.strictEqual(normalizeForSearch('１２⽉２７⽇'), '12月27日');
  });

  await t.test('handles empty or non-string inputs safely', () => {
    assert.strictEqual(normalizeForSearch(''), '');
    assert.strictEqual(normalizeForSearch(null), '');
    assert.strictEqual(normalizeForSearch(undefined), '');
  });
});



