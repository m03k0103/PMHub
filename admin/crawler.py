#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - 2回目用情報取得Engine (2nd-Time Information Retrieval Engine)
1回目用情報確認Agent (agent_initial_verifier.py) が生成した抽出ルール (scraping_rules.json) を読み込み、
高速・高精度な2段階階層クロールおよび資料データ取得を実行する専用Engine
"""

import sys
import os
import json
import urllib.request
import urllib.parse
import re
import io
from datetime import datetime, timedelta

# Windows ターミナルログの文字化け防止 (chcp 65001 & UTF-8 再構成)
if sys.platform == "win32":
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
CRAWL_TARGETS = [
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
]

def load_scraping_rules():
    """2回目用情報取得ルール (scraping_rules.json) を読み込む"""
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to load scraping_rules.json: {e}", file=sys.stderr)
    return {}

def fetch_url(url):
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.scheme not in ("http", "https"):
        print(f"[ERROR] Invalid scheme: {url}", file=sys.stderr)
        return None
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) PMHubRetrievalEngine/2.0'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}", file=sys.stderr)
        return None

def parse_materials_from_html(html, base_url, pdf_selector):
    """HTMLから全配布資料（公開PDFおよび非公開資料）を抽出"""
    materials = []
    
    pdf_matches = re.findall(r'<a[^>]*href=["\']([^"\']+\.pdf)["\'][^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
    for pdf_url, link_text in pdf_matches:
        clean_name = re.sub(r'<[^>]+>', '', link_text).strip()
        if not clean_name:
            clean_name = os.path.basename(pdf_url)
        abs_url = urllib.parse.urljoin(base_url, pdf_url)
        materials.append({
            "name": clean_name,
            "url": abs_url,
            "type": "PDF",
            "isPrivate": False
        })
        
    private_lines = re.findall(r'(資料\d+[\s\:\：]*[^\n<]+(?:非公開)[^\n<]*)', html)
    for p_text in private_lines:
        clean_p_text = re.sub(r'<[^>]+>', '', p_text).strip()
        materials.append({
            "name": clean_p_text,
            "url": "#",
            "type": "非公開",
            "isPrivate": True
        })
        
    return materials

def normalize_japanese_numbers(text):
    """全角英数字・漢数字を半角数値に正規化"""
    tr_map = str.maketrans('０１２３４５６７８９', '0123456789')
    return text.translate(tr_map)

def _crawl_subpages(target_url, html, rule, quirk_note, pdf_pattern):
    """サブページの深掘りクロールロジック"""
    subpage_meetings = []
    additional_materials = []
    all_extracted_dates = []

    subpage_pattern = rule.get("subpage_discovery_pattern", r'href=["\']([^"\']*(?:dai\d+|\d+kai|kaisai|gijisidai)[^"\'#]*)["\']')
    subpage_links = re.findall(subpage_pattern, html, re.IGNORECASE)

    if subpage_links:
        unique_subpages = list(dict.fromkeys([urllib.parse.urljoin(target_url, l) for l in subpage_links]))[:6]
        print(f"   [2回目情報取得Engine ({quirk_note})] サブページ {len(unique_subpages)} 件を深掘り巡回中...")

        for sub_url in unique_subpages:
            parsed_url = urllib.parse.urlparse(sub_url)
            if parsed_url.scheme not in ('http', 'https'):
                continue

            sub_html = fetch_url(sub_url)
            if sub_html:
                sub_title_match = re.search(r'<title>(.*?)</title>', sub_html, re.IGNORECASE | re.DOTALL)
                sub_title = sub_title_match.group(1).strip() if sub_title_match else sub_url

                sub_materials = parse_materials_from_html(sub_html, sub_url, pdf_pattern)
                raw_sub_dates = re.findall(rule.get("date_regex", r'(?:令和|平成)\d+年\d+月\d+日|\d{4}年\d+月\d+日|\d{4}[/-]\d+[/-]\d+'), sub_html)
                norm_sub_dates = [normalize_japanese_numbers(d) for d in raw_sub_dates]
                all_extracted_dates.extend(norm_sub_dates)

                subpage_meetings.append({
                    "subpageUrl": sub_url,
                    "title": sub_title,
                    "extractedMaterialsCount": len(sub_materials),
                    "materials": sub_materials,
                    "extractedDates": list(set(norm_sub_dates))[:2]
                })
                additional_materials.extend(sub_materials)

    return subpage_meetings, additional_materials, all_extracted_dates

def parse_japanese_date(date_str):
    """和暦・西暦文字列を datetime オブジェクトに変換"""
    if not date_str:
        return None
    date_str = normalize_japanese_numbers(date_str)
    m_reiwa = re.search(r'令和(\d+)年(\d+)月(\d+)日', date_str)
    if m_reiwa:
        try:
            return datetime(2018 + int(m_reiwa.group(1)), int(m_reiwa.group(2)), int(m_reiwa.group(3)))
        except Exception:
            pass
    m_heisei = re.search(r'平成(\d+)年(\d+)月(\d+)日', date_str)
    if m_heisei:
        try:
            return datetime(1988 + int(m_heisei.group(1)), int(m_heisei.group(2)), int(m_heisei.group(3)))
        except Exception:
            pass
    m_seireki = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_str)
    if m_seireki:
        try:
            return datetime(int(m_seireki.group(1)), int(m_seireki.group(2)), int(m_seireki.group(3)))
        except Exception:
            pass
    m_slash = re.search(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', date_str)
    if m_slash:
        try:
            return datetime(int(m_slash.group(1)), int(m_slash.group(2)), int(m_slash.group(3)))
        except Exception:
            pass
    return None

def calculate_past_year_count(extracted_dates, ref_date=None):
    """抽出された日付から過去1年間の開催数を算出。トップページ等に日付がなければ ('-', False) を返す"""
    if ref_date is None:
        ref_date = datetime.now()
    if not extracted_dates:
        return "-", False
    
    parsed_dates = []
    for d_str in extracted_dates:
        dt = parse_japanese_date(d_str)
        if dt:
            parsed_dates.append(dt)
            
    if not parsed_dates:
        return "-", False
        
    one_year_ago = ref_date - timedelta(days=365)
    unique_past_year_dates = set([dt.strftime('%Y-%m-%d') for dt in parsed_dates if one_year_ago <= dt <= ref_date])
    return len(unique_past_year_dates), True

def execute_rule_retrieval(target, html, rule_item):
    """【2回目情報取得Engine】AI考案ルールに基づき2段階階層クロールおよび資料データをフル抽出"""
    rule = rule_item.get("rules", {})
    quirk_note = rule_item.get("ministryQuirk", "標準抽出ルール")
    
    title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    page_title = title_match.group(1).strip() if title_match else target["name"]

    pdf_pattern = rule.get("pdf_selector", r'href=["\']([^"\']+\.pdf)["\']')
    top_materials = parse_materials_from_html(html, target["url"], pdf_pattern)

    subpage_meetings = []
    deep_enabled = rule.get("deep_crawl_enabled", True)
    all_extracted_dates = []
    
    if deep_enabled:
        new_meetings, new_materials, new_dates = _crawl_subpages(target["url"], html, rule, quirk_note, pdf_pattern)
        subpage_meetings.extend(new_meetings)
        top_materials.extend(new_materials)
        all_extracted_dates.extend(new_dates)

    unique_materials = []
    seen_keys = set()
    for m in top_materials:
        key = m["url"] if m["url"] != "#" else m["name"]
        if key not in seen_keys:
            seen_keys.add(key)
            unique_materials.append(m)

    raw_date_matches = re.findall(rule.get("date_regex", r'(?:令和|平成)\d+年\d+月\d+日|\d{4}年\d+月\d+日|\d{4}[/-]\d+[/-]\d+'), html)
    norm_date_matches = [normalize_japanese_numbers(d) for d in raw_date_matches]
    all_extracted_dates.extend(norm_date_matches)

    past_year_count, has_top_page_dates = calculate_past_year_count(all_extracted_dates)

    scraped_item = {
        "councilId": target["id"],
        "councilName": target["name"],
        "ministry": target["ministry"],
        "officialUrl": target["url"],
        "scrapedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ruleApplied": rule_item.get("rule_id", "rule-default"),
        "ministryQuirk": quirk_note,
        "pageTitle": page_title,
        "pastYearCount": past_year_count,
        "hasTopPageDates": has_top_page_dates,
        "totalExtractedMaterials": len(unique_materials),
        "materials": unique_materials,
        "extractedDates": list(set(norm_date_matches))[:5],
        "subpageMeetings": subpage_meetings
    }
    return scraped_item

def main():
    print("==========================================================")
    print(" 政策会議ウォッチ (PM-HUB) 2回目用情報取得Engine ")
    print("==========================================================")
    print(f"取得実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"対象会議体数: {len(CRAWL_TARGETS)} 件\n")

    rules = load_scraping_rules()
    if not rules:
        print("[WARN] 'scraping_rules.json' が見つかりません。先に agent_initial_verifier.py を実行してください。", file=sys.stderr)

    results = []

    for idx, target in enumerate(CRAWL_TARGETS, 1):
        print(f"[{idx}/{len(CRAWL_TARGETS)}] HTTP GET: {target['name']} ({target['url']})...")
        html = fetch_url(target["url"])
        
        if html:
            c_id = target["id"]
            rule_obj = rules.get(c_id, {
                "rule_id": "rule-fallback-v1",
                "rules": {
                    "pdf_selector": r'href=["\']([^"\']+\.pdf)["\']',
                    "date_regex": r'令和\d+年\d+月\d+日'
                }
            })
            print(f"   [2回目ルール適用] '{rule_obj.get('rule_id')}' に基づき全自動データ抽出")

            item = execute_rule_retrieval(target, html, rule_obj)
            results.append(item)
            
            print(f"  -> [200 OK] タイトル: {item['pageTitle']}")
            print(f"  -> [データ抽出成功] 総抽出資料数: {item['totalExtractedMaterials']} 件, 検出日付: {item['extractedDates']}")
        else:
            print(f"  -> [SKIP] ネットワーク取得スキップ")
        print("-" * 65)

    output_filename = os.path.join(os.path.dirname(__file__), "scraped_councils_output.json")
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # public/data.js の LAST_CRAWL_TIME を最新のクロール実行時刻に自動更新
    project_root = os.path.dirname(os.path.dirname(__file__))
    data_js_path = os.path.join(project_root, "public", "data.js")
    if os.path.exists(data_js_path):
        now_str = datetime.now().strftime("%Y/%m/%d %H:%M")
        with open(data_js_path, "r", encoding="utf-8") as f:
            content = f.read()
        if "const LAST_CRAWL_TIME =" in content:
            updated_content = re.sub(
                r"const LAST_CRAWL_TIME = '[^']*';",
                f"const LAST_CRAWL_TIME = '{now_str}';",
                content
            )
            with open(data_js_path, "w", encoding="utf-8") as f:
                f.write(updated_content)
            print(f"[更新成功] public/data.js の LAST_CRAWL_TIME を '{now_str}' に更新しました。")

    print(f"\nデータ取得完了: 結果を {output_filename} に保存しました。")

if __name__ == "__main__":
    main()
