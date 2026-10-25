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
    generic_names = {
        '会議資料', '配付資料', '配布資料', '資料一覧', '配付資料一覧', '配布資料一覧', 
        '会議資料一覧', '提出資料 (HTML)', '配付資料 (HTML)', '提出資料', '会議資料ページ', 
        '議事次第・配付資料 (HTML)', '配付資料一覧ページ (HTML)', '議事次第・配付資料'
    }
    if clean_n in generic_names or '配付資料一覧ページ' in clean_n or '議事次第・配付資料' in clean_n:
        return True
    return False

class TestDrop80IntermediateMaterialGuard(unittest.TestCase):
    def setUp(self):
        data = load_data_json()
        self.councils = {c['id']: c for c in data.get('councils', [])}
        self.meetings = data.get('meetings', [])
        
    def test_guarded_councils_have_zero_intermediate_materials(self):
        """CR-209 / CR-211: 税制調査会系列全13会議体および内閣官房2会議体に中間HTML配付資料が混入していないこと"""
        guarded_councils = {
            # 税制調査会系列
            'cao-zeicho_digital_noukan_senmonka',
            'cao-zeicho_life_senmonka',
            'cao-zeicho_sozoku_zoyo_senmonka',
            'cao-zeicho_koku_han_kaigou',
            'cao-zeicho_rougo_shisan_senmonka',
            'cao-zei_cho',
            'cao-zeicho_noukan_senmonka',
            'cao-zeicho_ebpm_senmonka',
            'cao-zeicho_discussion3_hojin',
            'cao-zeicho_discussion1_kokusai',
            'cao-zeicho_kiso_shoiinkai',
            'cao-zeicho_renketsu_senmonka',
            'cao-zeicho_discussion2_mynumber',
            # 内閣官房
            'cas-kokusentoc',
            'cas-kagayakujosei'
        }
        
        violations = []
        for m in self.meetings:
            cid = m.get('councilId')
            if cid in guarded_councils:
                for mat in m.get('materials', []):
                    mname = mat.get('name', '')
                    murl = mat.get('url', '')
                    if is_intermediate_html_material(mname, murl):
                        violations.append(f"Meeting {m['id']} has intermediate material: '{mname}' -> {murl}")
        
        self.assertEqual(len(violations), 0, f"Intermediate HTML materials found: {violations}")

    def test_terminal_materials_present(self):
        """国家戦略特区諮問会議および女性が輝く社会づくり本部に末端PDF資料が登録されていること"""
        kokusentoc_m = [m for m in self.meetings if m.get('councilId') == 'cas-kokusentoc']
        self.assertGreaterEqual(len(kokusentoc_m), 60, "At least 60 meetings should exist for kokusentoc")
        for m in kokusentoc_m:
            mats = m.get('materials', [])
            self.assertGreater(len(mats), 0, f"Meeting {m['id']} should have terminal materials")

    def test_helper_detection_logic(self):
        """中間HTML判定ロジックが正しく判定すること"""
        self.assertTrue(is_intermediate_html_material('会議資料', 'https://www.cao.go.jp/zei-cho/gijiroku/digital-noukan/2025/7digital-noukan4kai.html'))
        self.assertTrue(is_intermediate_html_material('配付資料一覧ページ (HTML)', 'https://www.chisou.go.jp/tiiki/kokusentoc/dai69/shiryou.html'))
        self.assertTrue(is_intermediate_html_material('第16回 議事次第・配付資料 (HTML)', 'https://www.cas.go.jp/jp/seisaku/kagayakujosei/dai16/gijisidai.html'))
        self.assertFalse(is_intermediate_html_material('次第', 'https://www.cao.go.jp/zei-cho/content/7digital-noukan4kai.pdf'))
        self.assertFalse(is_intermediate_html_material('議事要旨', 'https://www.soumu.go.jp/main_sosiki/singi/gijiyoushi.html'))

if __name__ == '__main__':
    unittest.main()
