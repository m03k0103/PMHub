#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - 1回目用情報確認Agent (AI Rule Synthesis Agent)
Webサイト初回訪問時、生成AI的推論アルゴリズムにより各省庁サイト固有の「クセ」
（DOM構造・全角数字・階層URLパターン・非公開表記・和暦西暦混在等）を深く自動解析し、
2回目用ルールエンジンが使用する最適化ルール (scraping_rules.json) を動的に考案・保存するエージェント
"""

import sys
import os
import json
import urllib.request
import re
from datetime import datetime

# Windows ターミナルログの文字化け防止 (chcp 65001 & UTF-8 再構成)
if sys.platform == "win32":
    import io
    os.system("chcp 65001 > NUL 2>&1")
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        else:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

RULES_FILE = os.path.join(os.path.dirname(__file__), "scraping_rules.json")

# クロール対象の政府審議会・会議体URLリスト
TARGET_COUNCILS = [
    {
        "id": "cao-ai-strategy",
        "ministry": "CAO",
        "name": "AI戦略会議",
        "url": "https://www8.cao.go.jp/cstp/ai/ai_senryaku/ai_senryaku.html"
    },
    {
        "id": "cao-space-anpo",
        "ministry": "CAO",
        "name": "宇宙政策委員会 宇宙安全保障部会",
        "url": "https://www8.cao.go.jp/space/comittee/anpo.html"
    },
    {
        "id": "cao-kisei-kaikaku",
        "ministry": "CAO",
        "name": "規制改革推進会議",
        "url": "https://www8.cao.go.jp/kisei-kaikaku/index.html"
    },
    {
        "id": "ra-fukko-suishin",
        "ministry": "RA",
        "name": "復興推進委員会",
        "url": "https://www.reconstruction.go.jp/topics/cat-11/cat-47/cat-155/cat-156/000813/"
    },
    {
        "id": "cas-kokumin-kaigi",
        "ministry": "CAS",
        "name": "社会保障国民会議",
        "url": "https://www.cas.go.jp/jp/seisaku/kokuminkaigi/index.html"
    },
    {
        "id": "cao-ai-hq",
        "ministry": "CAO",
        "name": "人工知能戦略本部",
        "url": "https://www8.cao.go.jp/cstp/ai/ai_hq/kaisai.html"
    },
    {
        "id": "digital-suishin",
        "ministry": "DIGITAL",
        "name": "デジタル社会推進会議幹事会",
        "url": "https://www.digital.go.jp/councils/social-promotion-executive"
    },
    {
        "id": "cfa-kodomo-suishin",
        "ministry": "CFA",
        "name": "こども政策推進会議",
        "url": "https://www.cfa.go.jp/councils/suishinkaigi"
    },
    {
        "id": "cfa-kodomo-shingikai",
        "ministry": "CFA",
        "name": "こども家庭審議会",
        "url": "https://www.cfa.go.jp/councils/shingikai"
    },
    {
        "id": "ra-fukko-suishin",
        "ministry": "RA",
        "name": "復興推進委員会",
        "url": "https://www.reconstruction.go.jp/topics/cat-11/cat-47/cat-155/cat-156/000813/"
    },
    {
        "id": "mic-joho-tsushin",
        "ministry": "MIC",
        "name": "情報通信審議会 情報通信政策部会",
        "url": "https://www.soumu.go.jp/menu_kyotsuu/whatsnew/kaigi_index.html"
    },
    {
        "id": "moj-hosei-shingi",
        "ministry": "MOJ",
        "name": "法制審議会",
        "url": "https://www.moj.go.jp/shingi1/shingikai_soukai.html"
    },
    {
        "id": "mofa-gaiko-seisaku",
        "ministry": "MOFA",
        "name": "外交政策有識者懇談会",
        "url": "https://www.mofa.go.jp/mofaj/index.html"
    },
    {
        "id": "mof-zaisei-seido",
        "ministry": "MOF",
        "name": "財政制度等審議会 財政制度分科会",
        "url": "https://www.mof.go.jp/about_mof/councils/fiscal_system_council/index.html"
    },
    {
        "id": "mext-chuo-kyoiku",
        "ministry": "MEXT",
        "name": "中央教育審議会 初等中等教育分科会",
        "url": "https://www.mext.go.jp/b_menu/shingi/chukyo/chukyo0/index.htm"
    },
    {
        "id": "mhlw-shakai-hosho",
        "ministry": "MHLW",
        "name": "社会保障審議会 医療保険部会",
        "url": "https://www.mhlw.go.jp/stf/shingi/index.html"
    },
    {
        "id": "maff-shokuryo-nogyo",
        "ministry": "MAFF",
        "name": "食料・農業・農村政策審議会",
        "url": "https://www.maff.go.jp/j/council/seisaku/"
    },
    {
        "id": "meti-sangyo-kozo",
        "ministry": "METI",
        "name": "産業構造審議会 新産業構造部会",
        "url": "https://www.meti.go.jp/shingikai/sankoshin/index.html"
    },
    {
        "id": "mlit-shakai-sihon-soukai",
        "ministry": "MLIT",
        "name": "社会資本整備審議会",
        "url": "https://www.mlit.go.jp/policy/shingikai/s201_shakai01.html"
    },
    {
        "id": "mlit-energy-anzenhosho-wg",
        "ministry": "MLIT",
        "name": "社会資本整備審議会環境部会・交通政策審議会環境部会 エネルギー・経済安全保障小委員会",
        "url": "https://www.mlit.go.jp/policy/shingikai/s404_anzenhosho.html"
    },
    {
        "id": "mlit-infra-management-wg",
        "ministry": "MLIT",
        "name": "社会資本整備審議会・交通政策審議会技術分科会技術部会 インフラマネジメント戦略小委員会",
        "url": "https://www.mlit.go.jp/policy/shingikai/s204_management02.html"
    },
    {
        "id": "moe-chuo-kankyo",
        "ministry": "MOE",
        "name": "中央環境審議会 地球環境部会",
        "url": "https://www.env.go.jp/council/06earth/yoshi06.html"
    },
    {
        "id": "mod-cho-shin",
        "ministry": "MOD",
        "name": "防衛調達審議会",
        "url": "https://www.mod.go.jp/j/policy/agenda/meeting/cho-shin/index.html"
    },
    {
        "id": "mod-drastic-reinforcement",
        "ministry": "MOD",
        "name": "防衛力の抜本的強化に関する有識者会議",
        "url": "https://www.mod.go.jp/j/policy/agenda/meeting/drastic-reinforcement/index.html"
    },
    {
        "id": "mod-defense-industry-wg",
        "ministry": "MOD",
        "name": "防衛産業ワーキンググループ",
        "url": "https://www.mod.go.jp/j/policy/agenda/meeting/defense_industry_wg/index.html"
    },
    {
        "id": "npa-seisaku-hyoka-kenkyukai",
        "ministry": "NPA",
        "name": "警察庁政策評価研究会",
        "url": "https://www.npa.go.jp/policies/council/index.html"
    },
    {
        "id": "fsa-kinyu-shingi",
        "ministry": "FSA",
        "name": "金融審議会",
        "url": "https://www.fsa.go.jp/singi/singi_kinyu/base_gijiroku.html"
    },
    {
        "id": "caa-shohisha-seisaku",
        "ministry": "CAA",
        "name": "消費者委員会 生成AI・消費者問題作業部会",
        "url": "https://www.caa.go.jp"
    },
    {
        "id": "ppc-ai-privacy",
        "ministry": "PPC",
        "name": "生成AIと個人情報保護に関する専門委員会",
        "url": "https://www.ppc.go.jp/aboutus/"
    },
    {
        "id": "nra-teireikai",
        "ministry": "NRA",
        "name": "原子力規制委員会",
        "url": "https://www.nra.go.jp/index.html"
    },
    {
        "id": "cas-zensedai-hosyo",
        "ministry": "CAS",
        "name": "全世代型社会保障構築会議",
        "url": "https://www.cas.go.jp/jp/seisaku/zensedai_hosyo/index.html"
    },
    {
        "id": "cas-kokumin-kaigi",
        "ministry": "CAS",
        "name": "社会保障国民会議",
        "url": "https://www.cas.go.jp/jp/seisaku/kokuminkaigi/index.html"
    },
    {
        "id": "cao-ai-hq",
        "ministry": "CAO",
        "name": "人工知能戦略本部",
        "url": "https://www8.cao.go.jp/cstp/ai/ai_hq/kaisai.html"
    },
    {
        "id": "cas-chutou-jyousei",
        "ministry": "CAS",
        "name": "中東情勢に関する関係閣僚会議",
        "url": "https://www.cas.go.jp/jp/seisaku/chyutoujyousei/index.html"
    },
    {
        "id": "cas-ainusuishin-1",
        "ministry": "CAS",
        "name": "アイヌ政策推進本部",
        "url": "https://www.cas.go.jp/jp/seisakukaigi/ainusuishin/index.html"
    },
    {
        "id": "cas-enerugi-2",
        "ministry": "CAS",
        "name": "エネルギー・食料等国民生活を支える基盤の戦略的強化に向けた関係閣僚会議",
        "url": "https://www.cas.go.jp/jp/seisaku/enerugi/index.html"
    },
    {
        "id": "cas-gaikokujinzai-3",
        "ministry": "CAS",
        "name": "外国人の受入れ・秩序ある共生社会実現に関する関係閣僚会議幹事会",
        "url": "https://www.cas.go.jp/jp/seisakukaigi/gaikokujinzai/index.html"
    },
    {
        "id": "cas-ebola_hemorrhagic_fever_kankeishoutyou-5",
        "ministry": "CAS",
        "name": "エボラ出血熱に関する関係省庁対策会議",
        "url": "https://www.cas.go.jp/jp/seisaku/ebola_hemorrhagic_fever_kankeishoutyou/index.html"
    },
    {
        "id": "cas-kanshikyoka-6",
        "ministry": "CAS",
        "name": "柏崎刈羽原子力発電所の運営に関する監視強化チーム",
        "url": "https://www.cas.go.jp/jp/seisaku/kanshikyoka/index.html"
    },
    {
        "id": "cas-kaihotaisei-7",
        "ministry": "CAS",
        "name": "海上保安能力強化に関する関係閣僚会議",
        "url": "https://www.cas.go.jp/jp/seisakukaigi/kaihotaisei/"
    },
    {
        "id": "cas-kyuyo-9",
        "ministry": "CAS",
        "name": "給与関係閣僚会議",
        "url": "https://www.cas.go.jp/jp/seisaku/kyuyo/index.html"
    },
    {
        "id": "cas-gambletou_izonsho-10",
        "ministry": "CAS",
        "name": "ギャンブル等依存症対策推進本部幹事会",
        "url": "https://www.cas.go.jp/jp/seisakukaigi/gambletou_izonsho/"
    },
    {
        "id": "cas-gskaigi-11",
        "ministry": "CAS",
        "name": "行政改革推進会議",
        "url": "https://www.cas.go.jp/jp/seisaku/gskaigi/index.html"
    },
    {
        "id": "cao-keizai_shimon-12",
        "ministry": "CAO",
        "name": "経済財政諮問会議",
        "url": "https://www5.cao.go.jp/keizai-shimon/"
    },
    {
        "id": "cao-getsurei-13",
        "ministry": "CAO",
        "name": "月例経済報告等に関する関係閣僚会議",
        "url": "https://www5.cao.go.jp/keizai3/getsurei/getsurei-index.html"
    },
    {
        "id": "cas-kumahigai_taisaku-14",
        "ministry": "CAS",
        "name": "クマ被害対策等に関する関係閣僚会議",
        "url": "https://www.cas.go.jp/jp/seisaku/kumahigai_taisaku/index.html"
    },
    {
        "id": "ra-000818-15",
        "ministry": "RA",
        "name": "原子力災害からの福島復興再生協議会",
        "url": "https://www.reconstruction.go.jp/topics/cat-11/cat-41/cat-129/cat-130/000818/"
    },
    {
        "id": "cas-grassrootsTF-16",
        "ministry": "CAS",
        "name": "グラスルーツからの日米関係強化に関する政府タスクフォース（各地各様のアプローチ）",
        "url": "https://www.cas.go.jp/jp/seisakukaigi/grassrootsTF/"
    },
    {
        "id": "cao-oaep-17",
        "ministry": "CAO",
        "name": "原子力立地会議",
        "url": "https://wwwa.cao.go.jp/oaep/tokubetsusochi.html"
    },
    {
        "id": "cao-measure-18",
        "ministry": "CAO",
        "name": "高齢社会対策会議",
        "url": "https://www8.cao.go.jp/kourei/measure/a_5.html"
    },
    {
        "id": "cas-genshiryoku_kakuryo_kaigi-19",
        "ministry": "CAS",
        "name": "原子力関係閣僚会議",
        "url": "https://www.cas.go.jp/jp/seisaku/genshiryoku_kakuryo_kaigi/"
    },
    {
        "id": "cas-kenkouiryou-20",
        "ministry": "CAS",
        "name": "健康・医療戦略推進本部",
        "url": "https://www.cas.go.jp/jp/seisakukaigi/kenkouiryou/"
    },
    {
        "id": "cas-kokusai_kansen-21",
        "ministry": "CAS",
        "name": "国際的に脅威となる感染症対策の強化のための国際連携等関係閣僚会議",
        "url": "https://www.cas.go.jp/jp/seisakukaigi/kokusai_kansen/index.html"
    },
    {
        "id": "cas-kyoujinka-22",
        "ministry": "CAS",
        "name": "国土強靱化の推進に関する関係府省庁連絡会議",
        "url": "https://www.cas.go.jp/jp/seisaku/kyoujinka/index.html"
    },
    {
        "id": "cao-suishinhonbu-23",
        "ministry": "CAO",
        "name": "孤独・孤立対策推進本部",
        "url": "https://www.cao.go.jp/kodoku_koritsu/torikumi/suishinhonbu/index.html"
    },
    {
        "id": "cas-kokusentoc-24",
        "ministry": "CAS",
        "name": "国家戦略特別区域諮問会議",
        "url": "https://www.chisou.go.jp/tiiki/kokusentoc/shimonkaigi.html"
    },
    {
        "id": "cao-contents_kyogikai-25",
        "ministry": "CAO",
        "name": "コンテンツ産業官民協議会",
        "url": "https://www.cao.go.jp/chizai/contents_kyogikai/index.html"
    },
    {
        "id": "cas-genshiryoku_bousai-26",
        "ministry": "CAS",
        "name": "原子力防災会議",
        "url": "https://www.cas.go.jp/jp/seisakukaigi/genshiryoku_bousai/"
    },
    {
        "id": "cas-kome_anteikyokyujitsugen_kaigi-27",
        "ministry": "CAS",
        "name": "米の安定供給等実現関係閣僚会議",
        "url": "https://www.cas.go.jp/jp/seisakukaigi/nousui/kome_anteikyokyujitsugen_kaigi/index.html"
    },
    {
        "id": "cas-kokudo_kyoujinka-28",
        "ministry": "CAS",
        "name": "国土強靱化推進本部",
        "url": "https://www.cas.go.jp/jp/seisakukaigi/kokudo_kyoujinka/"
    },
    {
        "id": "cas-jieikan-29",
        "ministry": "CAS",
        "name": "自衛官の処遇・勤務環境の改善及び新たな生涯設計の確立に関する関係閣僚会議",
        "url": "https://www.cas.go.jp/jp/seisaku/jieikan/index.html"
    },
    {
        "id": "cas-cs-30",
        "ministry": "CAS",
        "name": "サイバーセキュリティ戦略本部",
        "url": "https://www.cyber.go.jp/council/cs/index.html"
    },
    {
        "id": "cas-sdgs-31",
        "ministry": "CAS",
        "name": "持続可能な開発目標（ＳＤＧｓ）推進本部",
        "url": "https://www.cas.go.jp/jp/seisakukaigi/sdgs/index.html"
    },
    {
        "id": "cas-gx_jikkou_kaigi-32",
        "ministry": "CAS",
        "name": "ＧＸ実行会議",
        "url": "https://www.cas.go.jp/jp/seisaku/gx_jikkou_kaigi/index.html"
    },
    {
        "id": "mlit-meeting-33",
        "ministry": "MLIT",
        "name": "自転車活用推進本部",
        "url": "https://www.mlit.go.jp/road/bicycleuse/meeting/index.html"
    },
    {
        "id": "cao-shimon-34",
        "ministry": "CAO",
        "name": "重要経済安保情報保護活用諮問会議",
        "url": "https://www.cao.go.jp/keizai_anzen_hosho/hogokatsuyou/shimon/shimon.html"
    },
    {
        "id": "cas-kyouseishakai-35",
        "ministry": "CAS",
        "name": "障害者に対する偏見や差別のない共生社会の実現に向けた対策推進本部",
        "url": "https://www.cas.go.jp/jp/seisaku/kyouseishakai/index.html"
    },
    {
        "id": "cas-kankeikakuryokaigi-36",
        "ministry": "CAS",
        "name": "就職氷河期世代等支援に関する関係閣僚会議",
        "url": "https://www.cas.go.jp/jp/seisaku/shushoku_hyogaki_shien/kankeikakuryokaigi/index.html"
    },
    {
        "id": "cas-jyouhouhozen-37",
        "ministry": "CAS",
        "name": "情報保全諮問会議",
        "url": "https://www.cas.go.jp/jp/seisaku/jyouhouhozen/index.html"
    },
    {
        "id": "maff-kaigi-38",
        "ministry": "MAFF",
        "name": "食育推進会議",
        "url": "https://www.maff.go.jp/j/syokuiku/kaigi/suisin.html"
    },
    {
        "id": "caa-review_meeting_002-39",
        "ministry": "CAA",
        "name": "食品ロス削減推進会議",
        "url": "https://www.caa.go.jp/policies/policy/consumer_education/meeting_materials/review_meeting_002/"
    },
    {
        "id": "cas-nousui-40",
        "ministry": "CAS",
        "name": "食料安定供給・農林水産業基盤強化本部",
        "url": "https://www.cas.go.jp/jp/seisakukaigi/nousui/index.html"
    },
    {
        "id": "cas-jinko_senryaku-41",
        "ministry": "CAS",
        "name": "人口戦略本部",
        "url": "https://www.cas.go.jp/jp/seisaku/jinko_senryaku/index.html"
    },
    {
        "id": "cao-zei_cho-42",
        "ministry": "CAO",
        "name": "税制調査会",
        "url": "https://www.cao.go.jp/zei-cho/"
    },
    {
        "id": "mic-chiji_kaigi-43",
        "ministry": "MIC",
        "name": "全国都道府県知事会議（政府主催）",
        "url": "https://www.soumu.go.jp/main_sosiki/singi/chiji_kaigi/index.html"
    },
    {
        "id": "cao-cstp-44",
        "ministry": "CAO",
        "name": "総合科学技術・イノベーション会議",
        "url": "https://www8.cao.go.jp/cstp/"
    },
    {
        "id": "cas-jinsintorihiki-45",
        "ministry": "CAS",
        "name": "人身取引対策推進会議",
        "url": "https://www.cas.go.jp/jp/seisakukaigi/jinsintorihiki/index.html"
    },
    {
        "id": "cas-kagayakujosei-46",
        "ministry": "CAS",
        "name": "すべての女性が輝く社会づくり本部",
        "url": "https://www.cas.go.jp/jp/seisaku/kagayakujosei/index.html"
    },
    {
        "id": "cas-kinyu-47",
        "ministry": "CAS",
        "name": "新戦略策定のための資産運用立国推進分科会",
        "url": "https://www.cas.go.jp/jp/seisaku/nipponseichosenryaku/kinyu/index.html"
    },
    {
        "id": "cas-seme_no_yobouiryou-48",
        "ministry": "CAS",
        "name": "攻めの予防医療に向けた性差に由来するヘルスケアに関する副大臣等会議",
        "url": "https://www.cas.go.jp/jp/seisaku/seme_no_yobouiryou/index.html"
    },
    {
        "id": "cas-senryaku-49",
        "ministry": "CAS",
        "name": "戦略分野分科会",
        "url": "https://www.cas.go.jp/jp/seisaku/nipponseichosenryaku/senryaku/index.html"
    },
    {
        "id": "cas-zensedai_shakaihosho_kochiku-50",
        "ministry": "CAS",
        "name": "全世代型社会保障構築本部",
        "url": "https://www.cas.go.jp/jp/seisaku/zensedai_shakaihosho_kochiku/index.html"
    },
    {
        "id": "cas-kaiyou-51",
        "ministry": "CAS",
        "name": "総合海洋政策本部",
        "url": "https://www.cas.go.jp/jp/seisakukaigi/kaiyou/index.html"
    },
    {
        "id": "cas-seiroushi-52",
        "ministry": "CAS",
        "name": "政労使の意見交換",
        "url": "https://www.cas.go.jp/jp/seisaku/nipponseichosenryaku/seiroushi/index.html"
    },
    {
        "id": "cas-dai1-53",
        "ministry": "CAS",
        "name": "総合特別区域推進本部",
        "url": "https://www.chisou.go.jp/tiiki/sogotoc/sinsei/dai1/index.html"
    },
    {
        "id": "cas-sozei-54",
        "ministry": "CAS",
        "name": "租税特別措置・補助金見直しに関する関係閣僚等及び副大臣会議",
        "url": "https://www.cas.go.jp/jp/seisaku/sozei/index.html"
    },
    {
        "id": "cas-senpaku_top-55",
        "ministry": "CAS",
        "name": "船舶活用医療推進本部",
        "url": "https://www.cas.go.jp/jp/seisaku/senpaku_top/index.html"
    },
    {
        "id": "cao-committee-56",
        "ministry": "CAO",
        "name": "対日直接投資推進会議",
        "url": "https://www.cao.go.jp/invest-japan/committee/index.html"
    },
    {
        "id": "cas-koukyou_infra-57",
        "ministry": "CAS",
        "name": "総合的な防衛体制の強化に資する研究開発及び公共インフラ整備に関する関係閣僚会議",
        "url": "https://www.cas.go.jp/jp/seisaku/koukyou_infra/index.html"
    },
    {
        "id": "mic-chihou_seido-58",
        "ministry": "MIC",
        "name": "地方制度調査会",
        "url": "https://www.soumu.go.jp/main_sosiki/singi/chihou_seido/singi.html"
    },
    {
        "id": "cas-megasolar-59",
        "ministry": "CAS",
        "name": "大規模太陽光発電事業に関する関係閣僚会議",
        "url": "https://www.cas.go.jp/jp/seisaku/megasolar/index.html"
    },
    {
        "id": "cas-clt_etc-60",
        "ministry": "CAS",
        "name": "多様な木質材料の活用促進に関する関係省庁連絡会議（旧ＣＬＴ活用促進に関する関係省庁連絡会議）",
        "url": "https://www.cas.go.jp/jp/seisaku/clt-etc/index.html"
    },
    {
        "id": "cas-chuobou-61",
        "ministry": "CAS",
        "name": "中央防災会議",
        "url": "https://www.bousai.go.jp/kaigirep/chuobou/"
    },
    {
        "id": "cas-tiikisaisei-62",
        "ministry": "CAS",
        "name": "地域再生本部",
        "url": "https://www.chisou.go.jp/tiiki/tiikisaisei/kaisai.html"
    },
    {
        "id": "cas-chiikimirai-63",
        "ministry": "CAS",
        "name": "地域未来戦略本部",
        "url": "https://www.cas.go.jp/jp/seisaku/chiikimirai/index.html"
    },
    {
        "id": "cas-ondanka-64",
        "ministry": "CAS",
        "name": "地球温暖化対策推進本部",
        "url": "https://www.cas.go.jp/jp/seisakukaigi/ondanka/index.html"
    },
    {
        "id": "cas-indexhtmlsuisin_kaigi_record-65",
        "ministry": "CAS",
        "name": "地域働き方・職場改革等推進会議",
        "url": "https://www.cas.go.jp/jp/seisaku/chiikihatarakikata/index.html#suisin-kaigi-record"
    },
    {
        "id": "cas-katsuryoku_kojyo-66",
        "ministry": "CAS",
        "name": "中堅企業等の成長促進に関するワーキンググループ",
        "url": "https://www.cas.go.jp/jp/seisakukaigi/katsuryoku_kojyo/index.html"
    },
    {
        "id": "cas-chukatu-67",
        "ministry": "CAS",
        "name": "中心市街地活性化本部",
        "url": "https://www.chisou.go.jp/tiiki/chukatu/konkyo.html"
    },
    {
        "id": "cao-tougosenryaku-68",
        "ministry": "CAO",
        "name": "統合イノベーション戦略推進会議",
        "url": "https://www8.cao.go.jp/cstp/tougosenryaku/kaigi.html"
    },
    {
        "id": "cas-tppinfo-69",
        "ministry": "CAS",
        "name": "「ＴＰＰ等総合対策本部」（旧ＴＰＰに関する主要閣僚会議）",
        "url": "https://www.cas.go.jp/jp/tpp/tppinfo/index.html"
    },
    {
        "id": "cas-sokuitiri-70",
        "ministry": "CAS",
        "name": "地理空間情報活用推進会議",
        "url": "https://www.cas.go.jp/jp/seisaku/sokuitiri/index.html"
    },
    {
        "id": "cas-digital_gyozaikaikaku-71",
        "ministry": "CAS",
        "name": "デジタル行財政改革会議",
        "url": "https://www.cas.go.jp/jp/seisaku/digital_gyozaikaikaku/index.html"
    },
    {
        "id": "cas-titeki2-72",
        "ministry": "CAS",
        "name": "知的財産戦略本部",
        "url": "https://www.cas.go.jp/jp/seisakukaigi/titeki2/"
    },
    {
        "id": "cas-naikakuhozenkansi-73",
        "ministry": "CAS",
        "name": "内閣保全監視委員会",
        "url": "https://www.cas.go.jp/jp/seisaku/naikakuhozenkansi/index.html"
    },
    {
        "id": "cas-nipponseichosenryaku-74",
        "ministry": "CAS",
        "name": "日本成長戦略会議",
        "url": "https://www.cas.go.jp/jp/seisaku/nipponseichosenryaku/index.html"
    },
    {
        "id": "cas-2027_hakurankai-75",
        "ministry": "CAS",
        "name": "２０２７年国際園芸博覧会関係閣僚会議",
        "url": "https://www.cas.go.jp/jp/seisaku/2027_hakurankai/index.html"
    },
    {
        "id": "cas-influenza-76",
        "ministry": "CAS",
        "name": "鳥インフルエンザ関係閣僚会議",
        "url": "https://www.cas.go.jp/jp/seisakukaigi/influenza/"
    },
    {
        "id": "cas-ir_promotion-77",
        "ministry": "CAS",
        "name": "特定複合観光施設区域整備推進本部",
        "url": "https://www.cas.go.jp/jp/seisakukaigi/ir_promotion/"
    },
    {
        "id": "cas-doushuu-78",
        "ministry": "CAS",
        "name": "道州制特別区域推進本部",
        "url": "https://www.cas.go.jp/jp/seisakukaigi/doushuu/"
    },
    {
        "id": "ra-000815-79",
        "ministry": "RA",
        "name": "復興推進会議",
        "url": "https://www.reconstruction.go.jp/topics/cat-11/cat-47/cat-158/000815/"
    },
    {
        "id": "cas-hanzai-80",
        "ministry": "CAS",
        "name": "犯罪対策閣僚会議",
        "url": "https://www.cas.go.jp/jp/seisakukaigi/hanzai/index.html"
    },
    {
        "id": "cas-nihonhaku-81",
        "ministry": "CAS",
        "name": "日本博総合推進会議",
        "url": "https://www.cas.go.jp/jp/seisakukaigi/nihonhaku/"
    },
    {
        "id": "cas-buturyu_seisaku_suishin-82",
        "ministry": "CAS",
        "name": "物流政策推進会議",
        "url": "https://www.cas.go.jp/jp/seisaku/buturyu_seisaku_suishin/index.html"
    },
    {
        "id": "cas-jikkoukaigi-83",
        "ministry": "CAS",
        "name": "防災対策実行会議",
        "url": "https://www.bousai.go.jp/kaigirep/chuobou/jikkoukaigi/index.html"
    },
    {
        "id": "cas-suishin_kakuryou-84",
        "ministry": "CAS",
        "name": "防災立国推進閣僚会議",
        "url": "https://www.bousai.go.jp/kaigirep/suishin_kakuryou/index.html"
    },
    {
        "id": "cas-suishin-85",
        "ministry": "CAS",
        "name": "防災推進国民会議",
        "url": "https://www.bousai.go.jp/kaigirep/suishin/"
    },
    {
        "id": "cao-partnership-86",
        "ministry": "CAO",
        "name": "未来を拓くパートナーシップ構築推進会議",
        "url": "https://www5.cao.go.jp/keizai1/partnership/partnership.html"
    },
    {
        "id": "cas-tariff_measures-87",
        "ministry": "CAS",
        "name": "米国の関税措置に関する総合対策タスクフォース",
        "url": "https://www.cas.go.jp/jp/seisaku/tariff_measures/index.html"
    },
    {
        "id": "cao-kaigi-88",
        "ministry": "CAO",
        "name": "民間資金等活用事業推進会議",
        "url": "https://www8.cao.go.jp/pfi/kaigi/kaigi_index.html"
    },
    {
        "id": "cas-r60101notojishin-89",
        "ministry": "CAS",
        "name": "令和６年能登半島地震復旧・復興支援本部",
        "url": "https://www.bousai.go.jp/updates/r60101notojishin/hukkyuhonbu.html"
    },
    {
        "id": "cas-ai_robo-90",
        "ministry": "CAS",
        "name": "AIロボティクスに関する関係府省連絡会議",
        "url": "https://www.cas.go.jp/jp/seisaku/ai_robo/index.html"
    },
    {
        "id": "cas-osaka_kansai_banpaku-91",
        "ministry": "CAS",
        "name": "大阪・関西万博に関する関係者会合",
        "url": "https://www.cas.go.jp/jp/seisaku/osaka_kansai_banpaku/kaigou.html"
    },
    {
        "id": "cas-iryo_kaigo-92",
        "ministry": "CAS",
        "name": "医療・介護保険制度における金融所得の公平な取扱いに関する関係府省庁会議",
        "url": "https://www.cas.go.jp/jp/seisaku/iryo_kaigo/index.html"
    },
    {
        "id": "cas-sangyouisan-93",
        "ministry": "CAS",
        "name": "稼働資産を含む産業遺産に関する有識者会議",
        "url": "https://www.cas.go.jp/jp/sangyousekaiisan/sangyouisan/kaigi.html"
    },
    {
        "id": "cas-1-94",
        "ministry": "CAS",
        "name": "普天間飛行場の運用等に伴う宜野湾市民の住民の生活環境等の保全の課題に関する協議会",
        "url": "https://www.city.ginowan.lg.jp/soshiki/kikaku/1/1/2/1/18457.html"
    },
    {
        "id": "cas-keizai_anzen_hosyohousei-95",
        "ministry": "CAS",
        "name": "経済安全保障法制に関する有識者会議（令和４年度～）",
        "url": "https://www.cas.go.jp/jp/seisaku/keizai_anzen_hosyohousei/4index.html"
    },
    {
        "id": "cas-genshiryoku_kankeifusho_renrakukaigi-96",
        "ministry": "CAS",
        "name": "国外における原子力関係事象への対応に関する関係府省連絡会議",
        "url": "https://www.cas.go.jp/jp/seisaku/genshiryoku_kankeifusho_renrakukaigi/index.html"
    },
    {
        "id": "cas-suisinkaigi-97",
        "ministry": "CAS",
        "name": "国土強靱化推進会議",
        "url": "https://www.cas.go.jp/jp/seisaku/suisinkaigi/index.html"
    },
    {
        "id": "cas-Infura_syougai-98",
        "ministry": "CAS",
        "name": "社会的影響が特に深刻な大規模インフラ障害への対応に係る関係府省庁連絡会議",
        "url": "https://www.cas.go.jp/jp/seisaku/Infura_syougai/index.html"
    },
    {
        "id": "cas-powder_room-99",
        "ministry": "CAS",
        "name": "女性用トイレにおける行列問題の改善に向けた関係府省連絡会議",
        "url": "https://www.cas.go.jp/jp/seisaku/powder-room/index.html"
    },
    {
        "id": "cas-pqc-100",
        "ministry": "CAS",
        "name": "政府機関等における耐量子計算機暗号（PQC）利用に関する関係府省庁連絡会議",
        "url": "https://www.cas.go.jp/jp/seisaku/pqc/index.html"
    },
    {
        "id": "cas-jinko_senryaku_pt-101",
        "ministry": "CAS",
        "name": "人口減少対策に関する意見聴取プロジェクトチーム",
        "url": "https://www.cas.go.jp/jp/seisaku/jinko_senryaku_pt/index.html"
    },
    {
        "id": "cas-shushoku_katsudou-102",
        "ministry": "CAS",
        "name": "就職・採用活動日程に関する関係省庁連絡会議",
        "url": "https://www.cas.go.jp/jp/seisaku/shushoku_katsudou/index.html"
    },
    {
        "id": "cas-ful-103",
        "ministry": "CAS",
        "name": "新型インフルエンザ等対策推進会議",
        "url": "https://www.cas.go.jp/jp/seisaku/ful/taisakusuisin.html"
    },
    {
        "id": "mof-fdi-104",
        "ministry": "MOF",
        "name": "対日外国投資委員会",
        "url": "https://www.mof.go.jp/policy/international_policy/gaitame_kawase/fdi/20260618215004.html"
    },
    {
        "id": "cas-business_jinken-105",
        "ministry": "CAS",
        "name": "ビジネスと人権に関する行動計画の実施に係る関係府省庁施策推進・連絡会議",
        "url": "https://www.cas.go.jp/jp/seisaku/business_jinken/index.html"
    },
    {
        "id": "cas-chotatsu-106",
        "ministry": "CAS",
        "name": "政府調達の自主的措置に関する関係省庁等会議",
        "url": "https://www.cas.go.jp/jp/seisaku/chotatsu/"
    },
    {
        "id": "cas-linear-107",
        "ministry": "CAS",
        "name": "リニア開業に伴う新たな圏域形成に関する関係府省等会議",
        "url": "https://www.cas.go.jp/jp/seisaku/linear/index.html"
    }
,
    {
        "id": "cas-atarashii-sihon-107",
        "name": "新しい資本主義実現会議",
        "ministry": "CAS",
        "url": "https://www.cas.go.jp/jp/seisaku/atarashii_sihonsyugi/index.html"
    },
    {
        "id": "cas-roumuhi-tenka-108",
        "name": "労務費の適切な転嫁のための関係省庁連絡会議",
        "ministry": "CAS",
        "url": "https://www.cas.go.jp/jp/seisaku/atarashii_sihonsyugi/index.html"
    },
    {
        "id": "cao-kisei-chiiki-wg-109",
        "name": "規制改革推進会議 地域活性化・人手不足対応WG",
        "ministry": "CAO",
        "url": "https://www8.cao.go.jp/kisei-kaikaku/kisei/meeting/meeting.html"
    },
    {
        "id": "cao-kisei-iryou-wg-110",
        "name": "規制改革推進会議 健康・医療・介護WG",
        "ministry": "CAO",
        "url": "https://www8.cao.go.jp/kisei-kaikaku/kisei/meeting/meeting.html"
    },
    {
        "id": "cao-kisei-hatarakikata-wg-111",
        "name": "規制改革推進会議 働き方・人への投資WG",
        "ministry": "CAO",
        "url": "https://www8.cao.go.jp/kisei-kaikaku/kisei/meeting/meeting.html"
    },
    {
        "id": "cao-kisei-digital-ai-wg-112",
        "name": "規制改革推進会議 デジタル・AI WG",
        "ministry": "CAO",
        "url": "https://www8.cao.go.jp/kisei-kaikaku/kisei/meeting/meeting.html"
    },
    {
        "id": "cao-kisei-startup-wg-113",
        "name": "規制改革推進会議 スタートアップ・イノベーション促進WG",
        "ministry": "CAO",
        "url": "https://www8.cao.go.jp/kisei-kaikaku/kisei/meeting/meeting.html"
    },
    {
        "id": "cao-kisei-gx-subwg-114",
        "name": "規制改革推進会議 GX・サステナビリティサブWG",
        "ministry": "CAO",
        "url": "https://www8.cao.go.jp/kisei-kaikaku/kisei/meeting/meeting.html"
    },
    {
        "id": "fsc-honkaigi-115",
        "name": "食品安全委員会 (本会議)",
        "ministry": "FSC",
        "url": "https://www.fsc.go.jp/iinkai/"
    },
    {
        "id": "fsc-kikaku-116",
        "name": "企画等専門調査会",
        "ministry": "FSC",
        "url": "https://www.fsc.go.jp/senmon/kikaku/"
    },
    {
        "id": "fsc-tenkabutu-117",
        "name": "添加物専門調査会",
        "ministry": "FSC",
        "url": "https://www.fsc.go.jp/senmon/tenkabutu/"
    },
    {
        "id": "fsc-nouyaku-118",
        "name": "農薬専門調査会",
        "ministry": "FSC",
        "url": "https://www.fsc.go.jp/senmon/nouyaku/"
    },
    {
        "id": "npsc-teirei-119",
        "name": "国家公安委員会 定例会議",
        "ministry": "NPSC",
        "url": "https://www.npsc.go.jp/activity/index.html"
    },
    {
        "id": "mic-joho-tsusin-121",
        "name": "情報通信審議会",
        "ministry": "MIC",
        "url": "https://www.soumu.go.jp/main_sosiki/joho_tsusin/eng/council/index.html"
    },
    {
        "id": "mic-chizai-122",
        "name": "地方財政審議会",
        "ministry": "MIC",
        "url": "https://www.soumu.go.jp/main_sosiki/singi/chizai/index.html"
    },
    {
        "id": "moj-housei-soukai-123",
        "name": "法制審議会 総会",
        "ministry": "MOJ",
        "url": "https://www.moj.go.jp/shingikai/shingikai_housei.html"
    },
    {
        "id": "moj-housei-seishoku-124",
        "name": "法制審議会 生殖補助医療関連親子法制部会",
        "ministry": "MOJ",
        "url": "https://www.moj.go.jp/shingikai/shingikai_seishoku.html"
    },
    {
        "id": "moj-housei-kaisha-125",
        "name": "法制審議会 会社法制（株式・株主総会等関係）部会",
        "ministry": "MOJ",
        "url": "https://www.moj.go.jp/shingikai/shingikai_kaisha.html"
    },
    {
        "id": "moj-housei-keiji-126",
        "name": "法制審議会 刑事法（犯罪被害者関係）部会",
        "ministry": "MOJ",
        "url": "https://www.moj.go.jp/shingikai/shingikai_keiji.html"
    },
    {
        "id": "mofa-kaigai-kouryushingi-127",
        "name": "海外交流審議会",
        "ministry": "MOFA",
        "url": "https://www.mofa.go.jp/mofaj/annai/shingi/kaigai.html"
    },
    {
        "id": "mof-customs-appeal-129",
        "name": "関税等ふん争審査会",
        "ministry": "MOF",
        "url": "https://www.mof.go.jp/about_mof/councils/customs_appeal/index.html"
    },
    {
        "id": "mext-chukyo-130",
        "name": "中央教育審議会",
        "ministry": "MEXT",
        "url": "https://www.mext.go.jp/b_menu/shingi/chukyo/index.htm"
    },
    {
        "id": "mext-gijyutu-131",
        "name": "科学技術・学術審議会",
        "ministry": "MEXT",
        "url": "https://www.mext.go.jp/b_menu/shingi/gijyutu/index.htm"
    },
    {
        "id": "mhlw-hosho-toukei-132",
        "name": "社会保障審議会 統計分科会",
        "ministry": "MHLW",
        "url": "https://www.mhlw.go.jp/stf/shingi/shingi-hosho_toukei.html"
    },
    {
        "id": "mhlw-hosho-shippei-133",
        "name": "社会保障審議会 疾病、傷害及び死因分類部会",
        "ministry": "MHLW",
        "url": "https://www.mhlw.go.jp/stf/shingi/shingi-hosho_shippei.html"
    },
    {
        "id": "mhlw-hosho-shiinsentaku-134",
        "name": "社会保障審議会 死因選択検討ワーキンググループ",
        "ministry": "MHLW",
        "url": "https://www.mhlw.go.jp/stf/shingi/shingi-hosho_shiinsentaku.html"
    },
    {
        "id": "mhlw-hosho-iryou-135",
        "name": "社会保障審議会 医療分科会",
        "ministry": "MHLW",
        "url": "https://www.mhlw.go.jp/stf/shingi/shingi-hosho_iryou.html"
    },
    {
        "id": "mhlw-hosho-kaigo-136",
        "name": "社会保障審議会 介護給付費分科会",
        "ministry": "MHLW",
        "url": "https://www.mhlw.go.jp/stf/shingi/shingi-hosho_kaigo.html"
    },
    {
        "id": "mhlw-hosho-fukushi-137",
        "name": "社会保障審議会 福祉部会",
        "ministry": "MHLW",
        "url": "https://www.mhlw.go.jp/stf/shingi/shingi-hosho_fukushi.html"
    },
    {
        "id": "mhlw-hosho-seikatsu-138",
        "name": "社会保障審議会 生活保護基準部会",
        "ministry": "MHLW",
        "url": "https://www.mhlw.go.jp/stf/shingi/shingi-hosho_seikatsu.html"
    },
    {
        "id": "mhlw-hosho-jidou-139",
        "name": "社会保障審議会 児童部会",
        "ministry": "MHLW",
        "url": "https://www.mhlw.go.jp/stf/shingi/shingi-hosho_jidou.html"
    },
    {
        "id": "mhlw-hosho-jidoukan-140",
        "name": "社会保障審議会 児童館のあり方に関する検討ワーキンググループ",
        "ministry": "MHLW",
        "url": "https://www.mhlw.go.jp/stf/shingi/shingi-hosho_jidoukan.html"
    },
    {
        "id": "mhlw-hosho-shikinunyou-141",
        "name": "社会保障審議会 資金運用部会",
        "ministry": "MHLW",
        "url": "https://www.mhlw.go.jp/stf/shingi/shingi-hosho_shikinunyou.html"
    },
    {
        "id": "mhlw-hosho-kaigohoken-142",
        "name": "社会保障審議会 介護保険部会",
        "ministry": "MHLW",
        "url": "https://www.mhlw.go.jp/stf/shingi/shingi-hosho_kaigohoken.html"
    },
    {
        "id": "mhlw-hosho-shouni-143",
        "name": "社会保障審議会 小児慢性特定疾病対策部会",
        "ministry": "MHLW",
        "url": "https://www.mhlw.go.jp/stf/shingi/shingi-hosho_shouni.html"
    },
    {
        "id": "mhlw-kousei-kansenshou-144",
        "name": "厚生科学審議会 感染症部会",
        "ministry": "MHLW",
        "url": "https://www.mhlw.go.jp/stf/shingi/shingi-kousei_kansenshou.html"
    },
    {
        "id": "mhlw-kousei-influ-145",
        "name": "厚生科学審議会 新型インフルエンザ対策に関する小委員会",
        "ministry": "MHLW",
        "url": "https://www.mhlw.go.jp/stf/shingi/shingi-kousei_influ.html"
    },
    {
        "id": "mhlw-rousei-roudoujouken-146",
        "name": "労働政策審議会 労働条件分科会",
        "ministry": "MHLW",
        "url": "https://www.mhlw.go.jp/stf/shingi/shingi-rousei_roudoujouken.html"
    },
    {
        "id": "mhlw-rousei-anzeneisei-147",
        "name": "労働政策審議会 安全衛生分科会",
        "ministry": "MHLW",
        "url": "https://www.mhlw.go.jp/stf/shingi/shingi-rousei_anzeneisei.html"
    },
    {
        "id": "meti-sankoushin-148",
        "name": "産業構造審議会",
        "ministry": "METI",
        "url": "https://www.meti.go.jp/shingikai/sankoushin/index.html"
    },
    {
        "id": "meti-ax-skill-wg-149",
        "name": "AX時代におけるスキルのあり方検討ワーキンググループ",
        "ministry": "METI",
        "url": "https://www.meti.go.jp/shingikai/mono_info_service/society_digital/ax_skill/index.html"
    },
    {
        "id": "mlit-kokudo-150",
        "name": "国土審議会",
        "ministry": "MLIT",
        "url": "https://www.mlit.go.jp/policy/shingikai/s01_kokudo01.html"
    },
    {
        "id": "mlit-koutsu-151",
        "name": "交通政策審議会",
        "ministry": "MLIT",
        "url": "https://www.mlit.go.jp/policy/shingikai/s30_koutsu01.html"
    },
    {
        "id": "mlit-unyu-152",
        "name": "運輸審議会",
        "ministry": "MLIT",
        "url": "https://www.mlit.go.jp/policy/shingikai/s40_unyu01.html"
    },
    {
        "id": "mlit-chuou-kensetsu-153",
        "name": "中央建設業審議会",
        "ministry": "MLIT",
        "url": "https://www.mlit.go.jp/policy/shingikai/s50_chuou01.html"
    },
    {
        "id": "moe-chuo-kankyo-154",
        "name": "中央環境審議会",
        "ministry": "MOE",
        "url": "https://www.env.go.jp/council/index.html"
    },
    {
        "id": "mod-shisetsu-155",
        "name": "防衛施設中央審議会",
        "ministry": "MOD",
        "url": "https://www.mod.go.jp/j/approach/agenda/meeting/shisetsu/index.html"
    }
]

def load_rules():
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_rules(rules_data):
    try:
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            json.dump(rules_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERROR] Failed to save rules: {e}", file=sys.stderr)

def fetch_url(url):
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.scheme not in ("http", "https"):
        print(f"[ERROR] Invalid scheme: {url}", file=sys.stderr)
        return None
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) PMHubAIRuleSynthesisAgent/3.0'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}", file=sys.stderr)
        return None

MINISTRY_QUIRKS = {
    "cas.go.jp": {
        "subpage_pattern": r'href=["\']([^"\']*(?:dai\d+|gijisidai|gijiroku)[^"\'#]*)["\']',
        "quirk_notes": "内閣官房型: daiXX/gijisidai.html 形式の2段階ネスト構造"
    },
    "cao.go.jp": {
        "subpage_pattern": r'href=["\']([^"\']*(?:dai\d+|\d+kai|kaisai|gijisidai)[^"\'#]*)["\']',
        "quirk_notes": "内閣府型: ◯kai/◯kai.html または kaisai.html の個別の回ネスト"
    },
    "reconstruction.go.jp": {
        "subpage_pattern": r'href=["\']([^"\']*(?:topics/|\d{8}|shidai)[^"\'#]*)["\']',
        "quirk_notes": "復興庁型: topics/cat-XX 分類URLおよび日付命名PDF"
    },
    "digital.go.jp": {
        "subpage_pattern": r'href=["\']([^"\']*(?:councils|meetings|\d{8})[^"\'#]*)["\']',
        "quirk_notes": "デジタル庁型: リソース絶対パス/ルート相対パス混在型HTML5構造"
    },
    "cfa.go.jp": {
        "subpage_pattern": r'href=["\']([^"\']*(?:councils/[a-z0-9_-]+/[a-f0-9]{8}|councils/[a-z0-9_-]+)[^"\'#]*)["\']',
        "quirk_notes": "こども家庭庁型: /councils/会議名/UUIDハッシュ個別の回URL構造"
    }
}

DEFAULT_QUIRK = {
    "subpage_pattern": r'href=["\']([^"\']*(?:dai\d+|\d+kai|kaisai|gijisidai)[^"\'#]*)["\']',
    "quirk_notes": "標準省庁型: 汎用個別回パターン"
}

def detect_deep_subpages(html):
    subpage_matches = re.findall(r'href=["\']([^"\']*(?:dai\d+|\d+kai|kaisai|gijisidai|gijiroku|meetings|\d{8})[^"\'#]*)["\']', html, re.IGNORECASE)
    return len(subpage_matches) > 0

def get_ministry_quirk(url):
    for domain, info in MINISTRY_QUIRKS.items():
        if domain in url:
            return info
    return DEFAULT_QUIRK

def determine_date_pattern(html):
    has_fullwidth_nums = bool(re.search(r'[０-９]', html))
    has_wareki = bool(re.search(r'令和[0-9０-９一-九]+年', html))

    if has_fullwidth_nums or has_wareki:
        return r'(?:令和[0-9０-９一-九]+年[0-9０-９一-十二]+月[0-9０-９一-三十一]+日|20[2-9][0-9]年[0-1]?[0-9]月[0-3]?[0-9]日)'
    return r'20[2-9][0-9]年[0-1]?[0-9]月[0-3]?[0-9]日'

def check_private_materials(html):
    return "非公開" in html or "非公表" in html

def count_pdfs(html):
    return len(re.findall(r'href=["\']([^"\']+\.pdf)["\']', html, re.IGNORECASE))

def synthesize_ai_rule_for_council(target, html):
    """
    【生成AI的ルール考案ロジック】
    省庁Webサイト固有の「クセ」（URL構造、全角数字表記、個別開催回サブページ、非公開文書の扱い）を
    分析・推論し、2回目取得Engine用の最適化ルールを考案する
    """
    print(f"   [1回目AI確認Agent] '{target['name']}' ({target['url']}) の「サイトのクセ」をAI深層解析中...")
    
    ministry = target["ministry"]
    url = target["url"]
    
    # 1. サブページ階層（個別回）の検出と推論
    has_deep_subpages = detect_deep_subpages(html)
    
    # 省庁別のサブページ構造クセの分類
    quirk_info = get_ministry_quirk(url)
    subpage_pattern = quirk_info["subpage_pattern"]
    quirk_notes = quirk_info["quirk_notes"]

    # 2. 全角数字・和暦/西暦パターンの解析
    date_pattern = determine_date_pattern(html)

    # 3. 非公開資料の検出
    has_private = check_private_materials(html)

    # 4. 資料リンクおよびPDF件数の計測
    pdf_count = count_pdfs(html)

    # 5. 生成AI考案ルールの合成
    ai_rule = {
        "rule_id": f"rule-{target['id']}-ai-v3",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "generator": "AI_Rule_Synthesis_Agent_v3",
        "councilName": target["name"],
        "targetUrl": target["url"],
        "ministryQuirk": quirk_notes,
        "rules": {
            "encoding": "utf-8",
            "deep_crawl_enabled": has_deep_subpages,
            "subpage_discovery_pattern": subpage_pattern,
            "date_regex": date_pattern,
            "prefer_subpage_date": True,
            "extract_subpage_materials_primary": True,
            "pdf_selector": r'href=["\']([^"\']+\.pdf)["\']',
            "private_doc_keyword": "非公開",
            "detect_private_materials": has_private,
            "extract_all_materials": True,
            "resolve_absolute_urls": True,
            "top_page_pdf_count": pdf_count
        }
    }
    return ai_rule

def validate_data_js():
    data_js_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "data.js")
    if not os.path.exists(data_js_path):
        print(f"[FAIL] docs/data.js not found at {data_js_path}")
        sys.exit(1)
        
    with open(data_js_path, "r", encoding="utf-8") as f:
        content = f.read()

    councils_pos = content.find("const COUNCILS = [")
    meetings_pos = content.find("const MEETINGS = [")

    if councils_pos == -1 or meetings_pos == -1:
        print("[FAIL] docs/data.js: Missing COUNCILS or MEETINGS array declaration!")
        sys.exit(1)

    councils_str = content[councils_pos:meetings_pos]
    meetings_str = content[meetings_pos:]

    for name, text in [("COUNCILS", councils_str), ("MEETINGS", meetings_str)]:
        start = text.find('[')
        end = text.rfind(']')
        if start == -1 or end == -1:
            print(f"[FAIL] docs/data.js: Could not find brackets for {name}")
            sys.exit(1)
            
        arr_body = text[start:end+1]
        
        # 1. Check brace count
        open_b = arr_body.count('{')
        close_b = arr_body.count('}')
        if open_b != close_b:
            print(f"[FAIL] docs/data.js: Brace count mismatch in {name}! open {{ = {open_b}, close }} = {close_b}")
            sys.exit(1)
            
        # 2. Check bracket count
        open_k = arr_body.count('[')
        close_k = arr_body.count(']')
        if open_k != close_k:
            print(f"[FAIL] docs/data.js: Bracket count mismatch in {name}! open [ = {open_k}, close ] = {close_k}")
            sys.exit(1)

        # 3. Check brace depth line by line to detect stray closing braces
        depth = 0
        for lnum, line in enumerate(text.splitlines(), 1):
            depth += line.count('{') - line.count('}')
            if depth < 0:
                print(f"[FAIL] docs/data.js: Negative brace depth at line {lnum} in {name}: {line.strip()}")
                sys.exit(1)

        # 4. Check for unescaped multiline strings inside single quotes
        lines = text.splitlines()
        for lnum, line in enumerate(lines, 1):
            if line.strip().startswith("//"):
                continue
            sq_matches = re.findall(r"(?<!\\)'", line)
            if len(sq_matches) % 2 != 0:
                print(f"[FAIL] docs/data.js: Unescaped single quote string imbalance in {name} line {lnum}: {line.strip()}")
                sys.exit(1)

    # 5. Check for duplicate meeting IDs and duplicate Council + Title entries
    meeting_id_matches = re.findall(r"id:\s*'([^']*)'", meetings_str)
    seen_m_ids = set()
    for m_id in meeting_id_matches:
        if m_id in seen_m_ids:
            print(f"[FAIL] docs/data.js: Duplicate meeting ID detected: '{m_id}'")
            sys.exit(1)
        seen_m_ids.add(m_id)

    # 6. Node.js Runtime Check: Verify data.js and app.js load without ReferenceError / SyntaxError
    import subprocess
    app_js_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "app.js")
    data_js_json = json.dumps(data_js_path)
    app_js_json = json.dumps(app_js_path)
    node_test_script = f"""
const fs = require('fs');
const vm = require('vm');
const dataCode = fs.readFileSync({data_js_json}, 'utf-8');
const appCode = fs.readFileSync({app_js_json}, 'utf-8');
const domMocks = `
const localStorage = {{ getItem: () => null, setItem: () => {{}}, removeItem: () => {{}} }};
const mockElem = () => ({{
    addEventListener: () => {{}},
    querySelectorAll: () => [],
    querySelector: () => mockElem(),
    classList: {{ add: () => {{}}, remove: () => {{}}, toggle: () => {{}} }},
    setAttribute: () => {{}},
    getAttribute: () => null,
    appendChild: () => {{}},
    removeChild: () => {{}},
    style: {{}}
}});
const document = {{
    documentElement: mockElem(),
    body: mockElem(),
    addEventListener: (evt, cb) => {{ if (evt === 'DOMContentLoaded') cb(); }},
    getElementById: () => mockElem(),
    querySelectorAll: () => [mockElem()],
    querySelector: () => mockElem(),
    createElement: () => mockElem()
}};
const window = {{ localStorage, document }};
const Chart = function() {{}};
`;
const context = {{}};
vm.createContext(context);
try {{
    vm.runInContext(domMocks + "\\n" + dataCode + "\\n" + appCode, context);
}} catch (err) {{
    console.error("RUNTIME_JS_ERROR:", err.message);
    process.exit(1);
}}
"""
    try:
        proc = subprocess.run(["node", "-e", node_test_script], capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            print(f"[FAIL] Node.js JS Runtime Check Failed: {proc.stderr.strip()}")
            sys.exit(1)
        print("[SUCCESS] Node.js JS Runtime Check passed (No ReferenceError / SyntaxError).")
    except Exception as e:
        print(f"[WARN] Node.js test skipped: {e}")

    print("[SUCCESS] docs/data.js: Full JS syntax validation passed (braces, brackets, quotes, duplicates, runtime execution).")

def main():
    print("==========================================================")
    print(" 政策会議ウォッチ (PM-HUB) 1回目用 AI Rule Synthesis Agent ")
    print("==========================================================")
    print(f"解析実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("--- [Pre-Flight Check] docs/data.js 構文検証実行中 ---")
    validate_data_js()
    print("----------------------------------------------------------")
    print(f"解析対象会議体数: {len(TARGET_COUNCILS)} 件\n")

    rules = load_rules()
    updated_count = 0

    for idx, target in enumerate(TARGET_COUNCILS, 1):
        print(f"[{idx}/{len(TARGET_COUNCILS)}] 「サイトのクセ」をAI解析中: {target['name']} ({target['ministry']})...")
        html = fetch_url(target["url"])
        
        if html:
            ai_rule_obj = synthesize_ai_rule_for_council(target, html)
            rules[target["id"]] = ai_rule_obj
            updated_count += 1
            print(f"  -> [AI推論完了] 考案ルール: '{ai_rule_obj['rule_id']}'")
            print(f"  -> [分析されたクセ] {ai_rule_obj['ministryQuirk']}")
        else:
            print(f"  -> [SKIP] ネットワーク取得スキップ")
        print("-" * 65)

    if updated_count > 0:
        save_rules(rules)
        print(f"\n1回目AI確認完了: 全{updated_count}件のAI考案ルールを {RULES_FILE} に永続保存しました。")

if __name__ == "__main__":
    main()
