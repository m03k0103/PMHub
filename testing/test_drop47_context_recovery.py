#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_drop47_context_recovery.py: Drop 47 ジェネリック配付資料名スマートコンテキスト復元の単体・整合性テスト (CR-110〜CR-113)

検証観点:
1. is_generic_material_name() の判定精度（ジェネリック語句の網羅的検知と正常資料名の非検知）
2. recover_material_context() のコンテキスト復元精度（先行テキスト、テーブル行見出し、親ブロック要素等）
3. docs/data.json 内の全配付資料における「PDF」「資料」等ジェネリック資料名の残存ゼロ検証
"""

import os
import sys
import json
import unittest
from bs4 import BeautifulSoup

# テスト対象モジュールのインポートパス設定
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ADMIN_DIR = os.path.join(REPO_ROOT, 'admin')
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if ADMIN_DIR not in sys.path:
    sys.path.insert(0, ADMIN_DIR)

from admin.crawler import is_generic_material_name, recover_material_context, normalize_text


class TestDrop47ContextRecovery(unittest.TestCase):
    """Drop 47 スマートコンテキスト復元単体テスト"""

    def test_generic_material_name_detection(self):
        """ジェネリック資料名の判定ロジック検証 (CR-110)"""
        # ジェネリック判定されるべき語句
        generics = [
            'PDF', 'pdf', '資料', 'ダウンロード', '配付資料', '配布資料',
            '別紙', '別添', '添付', '添付資料', '一覧', '詳細',
            '[ PDF ]', '(PDF)', '［PDF形式：120KB］', '（資料）', '【配付資料】'
        ]
        for g in generics:
            self.assertTrue(is_generic_material_name(g), f"'{g}' はジェネリックと判定されるべき")

        # 正常な具体的資料名（Falseと判定されるべき語句）
        legit_names = [
            '議事次第',
            '資料1 今後の進め方について',
            '参考資料2 委員名簿',
            '社会保障審議会年金部会報告書（案）',
            '第1回検討会配付資料 (01.pdf)',
            '議事録'
        ]
        for name in legit_names:
            self.assertFalse(is_generic_material_name(name), f"'{name}' はジェネリックではないと判定されるべき")

    def test_recover_mhlw_td_inline_pattern(self):
        """厚労省型: 親td内の直前テキストからの資料名スマート復元 (CR-110)"""
        html = """
        <td>
            （１）今後の勤労者財産形成促進制度について（中間報告）（案）について
            ( <a href="dl/s0412-2a.pdf">PDF</a> :318KB)
        </td>
        """
        soup = BeautifulSoup(html, 'html.parser')
        a_tag = soup.find('a')
        recovered = recover_material_context(a_tag, initial_name="PDF")
        self.assertIn("今後の勤労者財産形成促進制度について", recovered)
        self.assertFalse(is_generic_material_name(recovered))

    def test_recover_mof_table_row_pattern(self):
        """財務省型: 同一tr内の先行th/td見出しセルからの資料名復元 (CR-110)"""
        html = """
        <table>
            <tr>
                <th scope="row">財政健全化に向けた建議（案）</th>
                <td>[ <a href="./01.pdf">PDF(PDF:2068KB)</a> ]</td>
            </tr>
        </table>
        """
        soup = BeautifulSoup(html, 'html.parser')
        a_tag = soup.find('a')
        recovered = recover_material_context(a_tag, initial_name="PDF")
        self.assertEqual(recovered, normalize_text("財政健全化に向けた建議（案）"))

    def test_recover_list_item_pattern(self):
        """リスト項目型: li要素内のテキストからの資料名復元 (CR-110)"""
        html = """
        <ul>
            <li>
                議題1：デジタル行財政改革の推進状況について
                <a href="mat01.pdf">資料［PDF形式：450KB］</a>
            </li>
        </ul>
        """
        soup = BeautifulSoup(html, 'html.parser')
        a_tag = soup.find('a')
        recovered = recover_material_context(a_tag, initial_name="資料")
        self.assertIn("デジタル行財政改革の推進状況について", recovered)

    def test_recover_gijiroku_filename_pattern(self):
        """ファイル名に gijiroku を含む場合の「議事録」フォールバック自動命名検証"""
        html = """
        <div>
            <a href="https://www.cao.go.jp/consumer/content/260806_gijiroku.pdf">PDF形式:152KB</a>
        </div>
        """
        soup = BeautifulSoup(html, 'html.parser')
        a_tag = soup.find('a')
        recovered = recover_material_context(a_tag, initial_name="PDF形式:152KB")
        self.assertEqual(recovered, "議事録")

    def test_data_json_generic_materials_zero(self):
        """docs/data.json 内の全配付資料におけるジェネリック資料名残存ゼロ検証 (CR-111)"""
        data_path = os.path.join(REPO_ROOT, 'docs', 'data.json')
        if not os.path.exists(data_path):
            self.skipTest("docs/data.json が存在しません")

        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        generic_materials = []
        for m in data.get('meetings', []):
            for mat in m.get('materials', []):
                name = mat.get('name', '').strip()
                if is_generic_material_name(name):
                    generic_materials.append({
                        'meetingId': m.get('id'),
                        'materialName': name,
                        'url': mat.get('url')
                    })

        self.assertEqual(
            len(generic_materials), 0,
            f"docs/data.json 内にジェネリック資料名が {len(generic_materials)} 件残存しています: {generic_materials[:5]}"
        )


def run_tests():
    """テスト実行エントリーポイント"""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestDrop47ContextRecovery)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
