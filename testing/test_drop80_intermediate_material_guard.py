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

GUARDED_INTERMEDIATE_COUNCILS = {
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
            'cas-kagayakujosei',
            # 財務省 (Drop 84)
            'mof-2717',
            'mof-zaiseiseido_bunkakai',
            'mof-1135',
            'mof-1136',
            'mof-1134',
            'mof-1133',
            'mof-seisaku_hyouka',
            'mof-1132',
            'mof-1731',
            'mof-1161',
            'mof-bop',
            'mof-jishin_benkyoukai',
            'mof-1153',
            'mof-fdi',
            'mof-shinkahei_arikata',
            # 金融庁・厚生労働省 (Drop 85)
            'fsa-kinyu_trouble',
            'mhlw-nenkin_shikin_unyou_bunkakai',
            'mhlw-jidou_gyakutai_shinken_senmon',
            'mhlw-911',
            'mhlw-943',
            'mhlw-971',
            'mhlw-1039',
            'mhlw-845',
            'mhlw-898',
            'mhlw-kousei_influ',
            # 食品安全委員会 (Drop 86: 全23会議体)
            'fsc-bakuro_wg',
            'fsc-biseibutu_virus',
            'fsc-bpa_wg',
            'fsc-doubutu',
            'fsc-eiyotenkabutu_wg',
            'fsc-hisiryou',
            'fsc-honkaigi',
            'fsc-hyoukagijyutukikaku_wg',
            'fsc-idensi',
            'fsc-kabi_shizen',
            'fsc-kiguyouki',
            'fsc-kikaku_tou',
            'fsc-nouyaku_dai1',
            'fsc-nouyaku_dai2',
            'fsc-nouyaku_dai3',
            'fsc-nouyaku_dai4',
            'fsc-nouyaku_dai5',
            'fsc-osen_tou',
            'fsc-pfas_wg',
            'fsc-prion',
            'fsc-sinkaihatu',
            'fsc-tenkabutu',
            'fsc-yakuzaitaiseikin_wg',
            # 経済産業省 (Drop 86: 33会議体)
            'meti-1664',
            'meti-1666',
            'meti-1673',
            'meti-1675',
            'meti-1676',
            'meti-1677',
            'meti-1678',
            'meti-1679',
            'meti-1680',
            'meti-1681',
            'meti-1682',
            'meti-1684',
            'meti-1692',
            'meti-1694',
            'meti-1698',
            'meti-1702',
            'meti-1703',
            'meti-1705',
            'meti-1708',
            'meti-1710',
            'meti-1714',
            'meti-1716',
            'meti-1718',
            'meti-1725',
            'meti-1728',
            'meti-ax_skill_wg',
            'meti-denryoku_gas_kanshi',
            'meti-kagaku_busshitsu',
            'meti-keiryou_gyousei',
            'meti-sankoushin',
            'meti-shinsangyo_kozo',
            'meti-shouhi_keizai',
            'meti-suiso_daidoumyaku',
            # 資源エネルギー庁 (Drop 86: 41会議体)
            'anre-1748',
            'anre-1749',
            'anre-1750',
            'anre-1751',
            'anre-1752',
            'anre-1753',
            'anre-1754',
            'anre-1755',
            'anre-1756',
            'anre-1757',
            'anre-1758',
            'anre-1759',
            'anre-1760',
            'anre-1762',
            'anre-1763',
            'anre-1764',
            'anre-1765',
            'anre-1766',
            'anre-1768',
            'anre-1769',
            'anre-1771',
            'anre-1772',
            'anre-1773',
            'anre-1774',
            'anre-1775',
            'anre-1776',
            'anre-1777',
            'anre-1779',
            'anre-1780',
            'anre-1781',
            'anre-1783',
            'anre-1785',
            'anre-1787',
            'anre-1789',
            'anre-1790',
            'anre-1791',
            'anre-1792',
            'anre-1793',
            'anre-1794',
            'anre-1795',
            'anre-1796',
            # 中小企業庁 (Drop 86: 6会議体)
            'smea-1307',
            'smea-1308',
            'smea-1310',
            'smea-1311',
            'smea-1620',
            'smea-keiei_shien_bunkakai',
            # 農林水産省・林野庁 (Drop 87: 10会議体)
            'maff-659',
            'maff-656',
            'maff-704',
            'maff-687',
            'maff-nougyogyou_hoken',
            'maff-shokuryou_sangyou_bukai',
            'maff-shokuryo_nogyo',
            'maff-nougyou_sizai_shingikai',
            'maff-sizai_noyaku_bunkakai',
            'rinya-1284',
            # 国土交通省 (Drop 87: 7会議体)
            'mlit-meeting',
            'mlit-infra_management_wg',
            'mlit-energy_anzenhosho_wg',
            'mlit-amami_shinkou',
            'mlit-dokuritsu_gyosei_hyoka',
            'mlit-kokudo_shingikai',
            'mlit-tochi_kantei',
            # 原子力規制委員会 (Drop 88: 11会議体)
            'nra-ro_anzen_shinsa',
            'nra-1205',
            'nra-1203',
            'nra-1204',
            'nra-1206',
            'nra-me_suishoutai',
            'nra-1209',
            'nra-1213',
            'nra-1212',
            'nra-1211',
            'nra-teireikai',
            # 総務省・文化庁・文部科学省 (Drop 89: 26会議体)
            'aca-187',
            'aca-188',
            'aca-bunka_shingikai_sokai',
            'aca-bunkazai_hogojoyaku',
            'aca-bunkazai_sekaitokubetsu',
            'aca-kokugo_bunkakai',
            'aca-kokugo_gairai',
            'aca-kokugo_gengo',
            'aca-kokugo_kadai',
            'aca-kokugo_nihongo',
            'aca-kokugo_nihongo_wg_h29',
            'aca-kokugo_shido_wg_h24',
            'aca-kokugo_shuro_nihongo_wg',
            'aca-needs_working_team_sagyou',
            'mext-714',
            'mext-chukyo',
            'mext-chuo_kyoiku',
            'mext-gijyutu',
            'mext-kokuritsu_daigaku_hyouka',
            'mext-kokuritsu_kenkyuu_shingi',
            'mic-dokuritsu_gyousei_hyouka',
            'mic-joho_tsusin',
            'mic-onkyu_shinsa02',
            'mic-seisaku_kaigi',
            'mic-toukei_iinkai',
            'mic-toukei_singikai',
            # 内閣官房・内閣府・デジタル庁・他残余全省庁 (Drop 90: 59会議体)
            'cao-232',
            'cao-258',
            'cao-259',
            'cao-260',
            'cao-278',
            'cao-contents_kyougikai',
            'cao-cstp',
            'cao-genshiryoku_kisei_ikenkoukan',
            'cao-pfi_suishin',
            'cao-space_anpo',
            'cas-296',
            'cas-347',
            'cas-351',
            'cas-atarashii_shihon_kaigi',
            'cas-chiikimirai',
            'cas-chuobou',
            'cas-digital_gyozaikaikaku',
            'cas-genshiryoku_kakuryo_kaigi',
            'cas-hanzai',
            'cas-jinko_senryaku',
            'cas-kokka_jouhou',
            'cas-kumahigai_taisaku',
            'cas-nousui',
            'cas-ondanka',
            'cas-shingijutsu_kouka_hyouka',
            'cas-titeki2',
            'digital-atena_kanri_wt',
            'digital-datalinkage_wt',
            'digital-kikan_system_touitsu',
            'digital-kyoutsuu_kinou_gijutsu',
            'digital-kyoutsuu_kinou_kadai',
            'digital-shinsei_kanri_wt',
            'digital-shitei_toshi_kadai',
            'fdma-chiiki_bousai_shien',
            'fsa-keizaikachi_solvency',
            'fsa-kigyou_kikaku_bukai',
            'fsa-kinyu_chukai',
            'fsa-kinyu_shingi',
            'fsa-monitoring',
            'fsa-suisai_ryoritsu',
            'jsa-611',
            'jsa-646',
            'jsa-sports_guideline',
            'jsa-sports_mirai_kaihatsu',
            'mhlw-1009',
            'mhlw-2862',
            'mhlw-2876',
            'mhlw-2878',
            'mhlw-937',
            'mhlw-gpif_unei_kento',
            'mhlw-hosho_fukushi',
            'mhlw-jcho_houjin_seido_kento',
            'mhlw-shakai_hosho',
            'mhlw-shakai_hosho_kaigo_kyuufu',
            'mhlw-unyou_iinkai_junbi_kaigou',
            'mlit-shakai_shingikai',
            'mofa-gaimu_jinji',
            'moj-fuhoukoui_hosei',
            'ra-fukko_suishin_kaigi',
        }

class TestDrop80IntermediateMaterialGuard(unittest.TestCase):
    def setUp(self):
        data = load_data_json()
        self.councils = {c['id']: c for c in data.get('councils', [])}
        self.meetings = data.get('meetings', [])
        
    def test_guarded_councils_have_zero_intermediate_materials(self):
        """CR-209 / CR-211 / CR-212: 中間HTML配付資料ガード対象会議体に中間HTMLが混入していないこと"""
        guarded_councils = GUARDED_INTERMEDIATE_COUNCILS
        
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
