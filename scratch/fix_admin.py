import os

path = 'admin/admin_dashboard.html'
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

old_str = """      const data = await res.json();
      window.COUNCILS = data.councils || [];
      window.MEETINGS = data.meetings || [];
    } catch(e) {
      console.error('Data loading error:', e);
      window.COUNCILS = [];
      window.MEETINGS = [];
    }"""

new_str = """      const data = await res.json();
      window.COUNCILS = data.councils || [];
      window.MEETINGS = data.meetings || [];
      window.MINISTRIES = data.ministries || {};
      window.CATEGORIES = data.categories || {};
      window.DOC_TYPES = data.docTypes || {};
      window.INITIAL_ALERT_KEYWORDS = data.initialAlertKeywords || [];
      window.LAST_CRAWL_TIME = data.lastCrawlTime || '';
    } catch(e) {
      console.error('Data loading error:', e);
      window.COUNCILS = [];
      window.MEETINGS = [];
      window.MINISTRIES = {};
      window.CATEGORIES = {};
      window.DOC_TYPES = {};
      window.INITIAL_ALERT_KEYWORDS = [];
      window.LAST_CRAWL_TIME = '';
    }"""

c = c.replace(old_str, new_str)

with open(path, 'w', encoding='utf-8') as f:
    f.write(c)

print("Done updating admin_dashboard.html")
