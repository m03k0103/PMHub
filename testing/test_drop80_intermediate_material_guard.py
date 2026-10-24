import unittest
import json
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from admin.utils import load_data_json

def is_intermediate_html_material(name, url):
    """
    Check if a material is an intermediate HTML container rather than a terminal document.
    """
    if not url:
        return False
    u = url.lower()
    if u.endswith('.pdf') or '.pdf?' in u or '.pdf#' in u:
        return False
    if not (u.endswith('.html') or u.endswith('.htm') or '/' in u):
        return False
    
    clean_n = name.strip()
    generic_names = {'会議資料', '配付資料', '配布資料', '資料一覧', '配付資料一覧', '配布資料一覧', '会議資料一覧', '提出資料 (HTML)', '配付資料 (HTML)'}
    if clean_n in generic_names:
        return True
    return False

class TestDrop80IntermediateMaterialGuard(unittest.TestCase):
    def setUp(self):
        data = load_data_json()
        self.councils = {c['id']: c for c in data.get('councils', [])}
        self.meetings = data.get('meetings', [])
        
    def test_zeicho_councils_have_zero_intermediate_materials(self):
        """CR-209: 税制調査会系列 6会議体に中間HTML配付資料が混入していないこと"""
        target_councils = {
            'cao-zeicho_digital_noukan_senmonka',
            'cao-zeicho_life_senmonka',
            'cao-zeicho_sozoku_zoyo_senmonka',
            'cao-zeicho_koku_han_kaigou',
            'cao-zeicho_rougo_shisan_senmonka',
            'cao-zei_cho'
        }
        
        violations = []
        for m in self.meetings:
            cid = m.get('councilId')
            if cid in target_councils:
                for mat in m.get('materials', []):
                    mname = mat.get('name', '')
                    murl = mat.get('url', '')
                    if is_intermediate_html_material(mname, murl):
                        violations.append(f"Meeting {m['id']} has intermediate material: '{mname}' -> {murl}")
        
        self.assertEqual(len(violations), 0, f"Intermediate HTML materials found: {violations}")

    def test_digital_noukan_terminal_materials_present(self):
        """第1回〜第4回 デジタル化専門家会合に末端PDF資料が登録されていること"""
        digital_meetings = [m for m in self.meetings if m.get('councilId') == 'cao-zeicho_digital_noukan_senmonka']
        self.assertGreaterEqual(len(digital_meetings), 5, "At least 5 meetings should exist for digital noukan")
        
        for m in digital_meetings:
            mid = m['id']
            mats = m.get('materials', [])
            self.assertGreater(len(mats), 0, f"Meeting {mid} should have terminal materials")
            # All materials in digital noukan should be PDFs (次第, 説明資料, 議事録, 記者会見録)
            for mat in mats:
                self.assertTrue(mat['url'].lower().endswith('.pdf'), f"Material should be PDF: {mat['name']} -> {mat['url']}")
                # Size string like (PDF形式:98KB) should be removed
                self.assertNotIn('(PDF形式', mat['name'], f"Size label not cleaned in {mat['name']}")

    def test_helper_detection_logic(self):
        """中間HTML判定ロジックが正しく判定すること"""
        self.assertTrue(is_intermediate_html_material('会議資料', 'https://www.cao.go.jp/zei-cho/gijiroku/digital-noukan/2025/7digital-noukan4kai.html'))
        self.assertTrue(is_intermediate_html_material('配付資料一覧', 'https://www.chisou.go.jp/tiiki/kokusentoc/dai69/shiryou.html'))
        self.assertFalse(is_intermediate_html_material('次第', 'https://www.cao.go.jp/zei-cho/content/7digital-noukan4kai.pdf'))
        self.assertFalse(is_intermediate_html_material('議事要旨', 'https://www.soumu.go.jp/main_sosiki/singi/gijiyoushi.html'))

if __name__ == '__main__':
    unittest.main()
