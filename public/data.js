/* ==========================================================================
   政策会議ウォッチ (PM-HUB) - All 21 Japanese Government Ministries & Agencies Dataset
   ========================================================================== */

const MINISTRIES = {
  CAO: { name: '内閣府', kanji: '内閣府', code: 'CAO', color: 'var(--color-cao)', officialUrl: 'https://www.cao.go.jp' },
  CAS: { name: '内閣官房', kanji: '内閣官房', code: 'CAS', color: 'var(--color-cas)', officialUrl: 'https://www.cas.go.jp' },
  DIGITAL: { name: 'デジタル庁', kanji: 'デジタル庁', code: 'DIGITAL', color: 'var(--color-digital)', officialUrl: 'https://www.digital.go.jp' },
  CFA: { name: 'こども家庭庁', kanji: 'こども家庭庁', code: 'CFA', color: 'var(--color-cfa)', officialUrl: 'https://www.cfa.go.jp' },
  RA: { name: '復興庁', kanji: '復興庁', code: 'RA', color: 'var(--color-ra)', officialUrl: 'https://www.reconstruction.go.jp' },
  MIC: { name: '総務省', kanji: '総務省', code: 'MIC', color: 'var(--color-mic)', officialUrl: 'https://www.soumu.go.jp' },
  MOJ: { name: '法務省', kanji: '法務省', code: 'MOJ', color: 'var(--color-moj)', officialUrl: 'https://www.moj.go.jp' },
  MOFA: { name: '外務省', kanji: '外務省', code: 'MOFA', color: 'var(--color-mofa)', officialUrl: 'https://www.mofa.go.jp' },
  MOF: { name: '財務省', kanji: '財務省', code: 'MOF', color: 'var(--color-mof)', officialUrl: 'https://www.mof.go.jp' },
  MEXT: { name: '文部科学省', kanji: '文部科学省', code: 'MEXT', color: 'var(--color-mext)', officialUrl: 'https://www.mext.go.jp' },
  MHLW: { name: '厚生労働省', kanji: '厚生労働省', code: 'MHLW', color: 'var(--color-mhlw)', officialUrl: 'https://www.mhlw.go.jp' },
  MAFF: { name: '農林水産省', kanji: '農林水産省', code: 'MAFF', color: 'var(--color-maff)', officialUrl: 'https://www.maff.go.jp' },
  METI: { name: '経済産業省', kanji: '経済産業省', code: 'METI', color: 'var(--color-meti)', officialUrl: 'https://www.meti.go.jp' },
  MLIT: { name: '国土交通省', kanji: '国土交通省', code: 'MLIT', color: 'var(--color-mlit)', officialUrl: 'https://www.mlit.go.jp' },
  MOE: { name: '環境省', kanji: '環境省', code: 'MOE', color: 'var(--color-moe)', officialUrl: 'https://www.env.go.jp' },
  MOD: { name: '防衛省', kanji: '防衛省', code: 'MOD', color: 'var(--color-mod)', officialUrl: 'https://www.mod.go.jp' },
  NPA: { name: '警察庁', kanji: '警察庁', code: 'NPA', color: 'var(--color-npa)', officialUrl: 'https://www.npa.go.jp' },
  FSA: { name: '金融庁', kanji: '金融庁', code: 'FSA', color: 'var(--color-fsa)', officialUrl: 'https://www.fsa.go.jp' },
  CAA: { name: '消費者庁', kanji: '消費者庁', code: 'CAA', color: 'var(--color-caa)', officialUrl: 'https://www.caa.go.jp' },
  PPC: { name: '個人情報保護委員会', kanji: '個人情報保護委員会', code: 'PPC', color: 'var(--color-ppc)', officialUrl: 'https://www.ppc.go.jp' },
  FTC: { name: '公正取引委員会', kanji: '公正取引委員会', code: 'FTC', color: 'var(--color-ftc)', officialUrl: 'https://www.jftc.go.jp' },
  NRA: { name: '原子力規制委員会', kanji: '原子力規制委員会', code: 'NRA', color: 'var(--color-nra)', officialUrl: 'https://www.nra.go.jp' }
};

const CATEGORIES = {
  COUNCIL: '審議会・諮問会議',
  SUBCOMMITTEE: '分科会・部会',
  PANEL: '検討会・有識者会議',
  ROUNDTABLE: '懇談会・作業部会'
};

const DOC_TYPES = {
  MINUTES: '議事録・要旨',
  MATERIALS: '配布資料',
  REPORT: '答申・報告書'
};

const COUNCILS = [
  // 1. CAO
  {
    id: 'cao-ai-strategy',
    name: 'AI戦略会議',
    ministry: 'CAO',
    category: 'PANEL',
    pastYearCount: 14,
    description: 'AIの利活用とリスク管理に関する国家戦略、ガバナンスガイドライン、フロンティアAIモデルの安全評価等を討議する有識者会議。',
    officialUrl: 'https://www8.cao.go.jp/cstp/ai/',
    isWatched: true,
    trackedSince: '2023-05-01'
  },
  {
    id: 'cao-kisei-kaikaku',
    name: '規制改革推進会議',
    ministry: 'CAO',
    category: 'COUNCIL',
    pastYearCount: 22,
    description: '経済社会の構造改革を推進するため、各種規制の点検・見直し、スタートアップ・デジタル化の障害除去を答申する内閣府諮問機関。',
    officialUrl: 'https://www8.cao.go.jp/kisei-kaikaku/index.html',
    isWatched: true,
    trackedSince: '2022-10-01'
  },
  // 2. DIGITAL
  {
    id: 'digital-suishin',
    name: 'デジタル社会推進会議',
    ministry: 'DIGITAL',
    category: 'COUNCIL',
    pastYearCount: 8,
    description: 'マイナンバー制度、ベース・レジストリ、政府クラウド (Gov-Cloud) および行政DXの推進基本計画を取りまとめる政府全体の意思決定会議。',
    officialUrl: 'https://www.digital.go.jp/councils/social-promotion',
    isWatched: true,
    trackedSince: '2021-09-01'
  },
  // 3. CFA
  {
    id: 'cfa-kodomo-seisaku',
    name: 'こども政策審議会',
    ministry: 'CFA',
    category: 'COUNCIL',
    pastYearCount: 12,
    description: '「こども未来戦略」に基づく少子化対策、児童手当拡充、こども誰でも通園制度、児童虐待防止・貧困対策の中長期計画を審議。',
    officialUrl: 'https://www.cfa.go.jp/councils/kodomo_seisaku/',
    isWatched: true,
    trackedSince: '2023-04-01'
  },
  // 4. RA
  {
    id: 'ra-fukko-suishin',
    name: '復興推進委員会',
    ministry: 'RA',
    category: 'COUNCIL',
    pastYearCount: 4,
    description: '東日本大震災および能登半島地震等からの復興基本方針、福島国際研究教育機構 (FIREC) の推進構想を討議。',
    officialUrl: 'https://www.reconstruction.go.jp/topics/cat-11/cat-47/cat-155/cat-156/000813/',
    isWatched: false,
    trackedSince: '2022-03-01'
  },
  // 5. MIC
  {
    id: 'mic-joho-tsushin',
    name: '情報通信審議会 情報通信政策部会',
    ministry: 'MIC',
    category: 'COUNCIL',
    pastYearCount: 11,
    description: '6G・光通信規格、電波周波数割り当て、プラットフォーム事業者規制、サイバーセキュリティ対策を審議。',
    officialUrl: 'https://www.soumu.go.jp/main_sosiki/joho_tsusin/policykyoku/shingikai.html',
    isWatched: false,
    trackedSince: '2022-06-01'
  },
  // 6. MOJ
  {
    id: 'moj-hosei-shingi',
    name: '法制審議会 民法部会',
    ministry: 'MOJ',
    category: 'SUBCOMMITTEE',
    pastYearCount: 9,
    description: 'デジタル時代の契約法制、共同親権、戸籍の読み仮名法制化、AI生成物の権利関係など民法・刑事法制の改正要綱案を答申。',
    officialUrl: 'https://www.moj.go.jp/shingi1/housei_index.html',
    isWatched: true,
    trackedSince: '2022-01-15'
  },
  // 7. MOFA
  {
    id: 'mofa-gaiko-seisaku',
    name: '外交政策有識者懇談会',
    ministry: 'MOFA',
    category: 'ROUNDTABLE',
    pastYearCount: 6,
    description: '経済安全保障、自由で開かれたインド太平洋 (FOIP)、Global South との連携強化、ODA改革に関する中長期戦略を助言。',
    officialUrl: 'https://www.mofa.go.jp/mofaj/ms/is/page25_001234.html',
    isWatched: false,
    trackedSince: '2023-05-10'
  },
  // 8. MOF
  {
    id: 'mof-zaisei-seido',
    name: '財政制度等審議会 財政制度分科会',
    ministry: 'MOF',
    category: 'SUBCOMMITTEE',
    pastYearCount: 18,
    description: '国家予算編成における歳出改革、防衛費・社会保障費・公共事業費の効率化と財政健全化目標を審議し「意見書」を取りまとめる。',
    officialUrl: 'https://www.mof.go.jp/about_mof/councils/fiscal_system_council/index.html',
    isWatched: true,
    trackedSince: '2022-09-01'
  },
  // 9. MEXT
  {
    id: 'mext-chuo-kyoiku',
    name: '中央教育審議会 初等中等教育分科会',
    ministry: 'MEXT',
    category: 'SUBCOMMITTEE',
    pastYearCount: 10,
    description: 'GIGAスクール構想、教員の働き方改革、学習指導要領の改定、生成AIの学校教育利用ガイドラインを策定。',
    officialUrl: 'https://www.mext.go.jp/b_menu/shingi/chukyo/chukyo0/index.htm',
    isWatched: false,
    trackedSince: '2023-02-01'
  },
  // 10. MHLW
  {
    id: 'mhlw-shakai-hosho',
    name: '社会保障審議会 医療保険部会',
    ministry: 'MHLW',
    category: 'SUBCOMMITTEE',
    pastYearCount: 24,
    description: '医療保険制度改革、マイナ保険証の普及・運用、診療報酬改定の基本方針および薬価制度の見直しを審議。',
    officialUrl: 'https://www.mhlw.go.jp/stf/shingi/shingi-iryou.html',
    isWatched: true,
    trackedSince: '2021-11-01'
  },
  // 11. MAFF
  {
    id: 'maff-shokuryo-nogyo',
    name: '食料・農業・農村政策審議会',
    ministry: 'MAFF',
    category: 'COUNCIL',
    pastYearCount: 12,
    description: '食料安全保障、スマート農業・農業DX推進、農林水産物輸出拡大、環境負荷低減型農業 (みどりの食料システム戦略) を策定。',
    officialUrl: 'https://www.maff.go.jp/j/council/seisaku/',
    isWatched: false,
    trackedSince: '2022-08-01'
  },
  // 12. METI
  {
    id: 'meti-sangyo-kozo',
    name: '産業構造審議会 新産業構造部会',
    ministry: 'METI',
    category: 'SUBCOMMITTEE',
    pastYearCount: 15,
    description: 'GX (グリーン・トランスフォーメーション)、半導体・量子技術の国産化、サプライチェーン強靱化等の経済産業政策の中長期方針を策定。',
    officialUrl: 'https://www.meti.go.jp/shingikai/sankoshin/index.html',
    isWatched: true,
    trackedSince: '2022-04-01'
  },
  // 13. MLIT
  {
    id: 'mlit-shakai-sihon',
    name: '社会資本整備審議会 道路分科会',
    ministry: 'MLIT',
    category: 'SUBCOMMITTEE',
    pastYearCount: 9,
    description: '高速道路の老朽化修繕、防災・減災国土強靱化計画、自動運転インフラ整備、物流2024年問題に伴うモーダルシフト促進。',
    officialUrl: 'https://www.mlit.go.jp/shingikai/sakai/index.html',
    isWatched: false,
    trackedSince: '2022-07-15'
  },
  // 14. MOE
  {
    id: 'moe-chuo-kankyo',
    name: '中央環境審議会 地球環境部会',
    ministry: 'MOE',
    category: 'SUBCOMMITTEE',
    pastYearCount: 7,
    description: '2030年・2050年温室効果ガス削減目標 (カーボンプライシング、排出量取引制度) の制度設計および環境アセスメントを審議。',
    officialUrl: 'https://www.env.go.jp/council/06earth/yoshi06.html',
    isWatched: false,
    trackedSince: '2022-05-01'
  },
  // 15. MOD
  {
    id: 'mod-boei-seisan',
    name: '防衛生産・技術基盤強化有識者会議',
    ministry: 'MOD',
    category: 'PANEL',
    pastYearCount: 12,
    description: '防衛装備移転三原則の見直し、先端技術 (AI・ドローン・量子) の防衛応用、国内防衛産業の事業継続支援策を検討。',
    officialUrl: 'https://www.mod.go.jp/j/approach/agenda/index.html',
    isWatched: true,
    trackedSince: '2023-01-10'
  },
  // 16. NPA
  {
    id: 'npa-cyber-keisatsu',
    name: 'サイバー犯罪・サイバー攻撃対策有識者会議',
    ministry: 'NPA',
    category: 'PANEL',
    pastYearCount: 6,
    description: 'ランサムウェア・フィッシング被害対策、暗号資産の不正送金防止、重要インフラ防護および能動的サイバー防御の法的整理。',
    officialUrl: 'https://www.npa.go.jp/bureau/cyber/council/',
    isWatched: true,
    trackedSince: '2023-03-15'
  },
  // 17. FSA
  {
    id: 'fsa-kinyu-shingi',
    name: '金融審議会 金融制度スタディ・グループ',
    ministry: 'FSA',
    category: 'SUBCOMMITTEE',
    pastYearCount: 16,
    description: 'ステーブルコイン・Web3暗号資産の規制フレームワーク、資産運用立国実現に向けたNISA制度拡充・顧客中心主義を審議。',
    officialUrl: 'https://www.fsa.go.jp/singi/singizu/index.html',
    isWatched: true,
    trackedSince: '2022-11-01'
  },
  // 18. CAA
  {
    id: 'caa-shohisha-seisaku',
    name: '消費者委員会 生成AI・消費者問題作業部会',
    ministry: 'CAA',
    category: 'ROUNDTABLE',
    pastYearCount: 10,
    description: 'ダークパターン規制、生成AIによる誤情報・悪質商法からの消費者保護、ステマ（ステルスマーケティング）規制の運用評価。',
    officialUrl: 'https://www.caa.go.jp/shingikai/consumer/',
    isWatched: false,
    trackedSince: '2023-06-01'
  },
  // 19. PPC
  {
    id: 'ppc-ai-privacy',
    name: '生成AIと個人情報保護に関する専門委員会',
    ministry: 'PPC',
    category: 'PANEL',
    pastYearCount: 11,
    description: '大規模言語モデル (LLM) 学習データにおける個人情報の匿名加工基準、海外テック企業への適格性審査および同意なし学習の権利保護。',
    officialUrl: 'https://www.ppc.go.jp/aboutus/kekka/',
    isWatched: true,
    trackedSince: '2023-04-15'
  },
  // 20. FTC
  {
    id: 'ftc-digital-platform',
    name: 'デジタル・プラットフォーム競合市場実態調査会',
    ministry: 'FTC',
    category: 'PANEL',
    pastYearCount: 13,
    description: '巨大IT企業 (Big Tech) に対するスマートフォンOS・アプリストア事前規制、生成AI分野における獨占禁止法上の論点整理。',
    officialUrl: 'https://www.jftc.go.jp/councils/index.html',
    isWatched: true,
    trackedSince: '2022-12-01'
  },
  // 21. NRA
  {
    id: 'nra-teireikai',
    name: '原子力規制委員会 定例会',
    ministry: 'NRA',
    category: 'COUNCIL',
    pastYearCount: 48,
    description: '原子力発電所の新規制基準適合性審査、高レベル放射性廃棄物最終処分場の地質調査評価、安全協定の検証を実施。',
    officialUrl: 'https://www.nra.go.jp/gikai/kisei-gikai/index.html',
    isWatched: false,
    trackedSince: '2021-10-01'
  },
  // 22. CAS Councils (User Requested)
  {
    id: 'cas-zensedai-hosyo',
    name: '全世代型社会保障構築会議',
    ministry: 'CAS',
    category: 'PANEL',
    pastYearCount: 21,
    description: '全世代型社会保障の構築に向け、医療・介護の構造改革、少子化対策、年金改革の具体策を審議・答申する内閣官房会議。',
    officialUrl: 'https://www.cas.go.jp/jp/seisaku/zensedai_hosyo/index.html',
    isWatched: true,
    trackedSince: '2022-01-10'
  },
  {
    id: 'cas-kokumin-kaigi',
    name: '社会保障国民会議',
    ministry: 'CAS',
    category: 'COUNCIL',
    pastYearCount: 12,
    description: '持続可能な社会保障制度の確立に向け、安心と信頼の社会保障構造の将来像と財源確保策を議論する国民的会議。',
    officialUrl: 'https://www.cas.go.jp/jp/seisaku/kokuminkaigi/index.html',
    isWatched: true,
    trackedSince: '2021-08-01'
  },
  {
    id: 'cao-ai-hq',
    name: '人工知能戦略本部',
    ministry: 'CAO',
    category: 'COUNCIL',
    pastYearCount: 5,
    description: '総合科学技術・イノベーション会議 (CSTP) の下、国家全体のAI技術戦略、安全性評価、法整備および国際ルール策定を推進。',
    officialUrl: 'https://www8.cao.go.jp/cstp/ai/ai_hq/kaisai.html',
    isWatched: true,
    trackedSince: '2023-04-01'
  },
  {
    id: 'cas-chutou-jyousei',
    name: '中東情勢に関する関係閣僚会議',
    ministry: 'CAS',
    category: 'PANEL',
    pastYearCount: 8,
    description: '中東地域情勢の緊迫化に伴う在留邦人の安全確保、原油・LNG供給体制の安定、および海上交通路の安全対策を迅速に協議する関係閣僚会議。',
    officialUrl: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/index.html',
    isWatched: true,
    trackedSince: '2023-10-10'
  }
];

const MEETINGS = [
  // 1. CAO
  {
    id: 'meet-2026-0728-ai',
    councilId: 'cao-ai-strategy',
    councilName: 'AI戦略会議',
    ministry: 'CAO',
    category: 'PANEL',
    title: '第14回 AI戦略会議',
    date: '2026-07-28',
    updatedAt: '2026-07-28 11:30',
    location: '中央合同庁舎第8号館 講堂（オンライン併用）',
    summary: '生成AIの事業者向け「安全評価基準（セーフティベンチマーク）」の最終案が示され、国による実証事業の導入方針が合意された。また、著作権法におけるAI学習と侵害判断の clarified ガイドライン運用状況について報告が行われた。',
    agenda: [
      'フロンティアAIモデルにおけるセーフティベンチマーク試行評価結果について',
      'AI事業者向けガバナンスガイドライン（Ver 2.0）改定案の提示',
      '生成AIと著作権に関する最新の訴訟・権利保護動向の報告'
    ],
    materials: [
      { name: '第14回 AI戦略会議 議事要旨 (PDF)', type: 'PDF', size: '210 KB', url: 'https://www8.cao.go.jp/cstp/ai/ai_hq/5kai/gijigaiyo.pdf', isMinutes: true },
      { name: 'AI戦略会議 ポータル・配布資料一覧 (HTML)', type: 'HTML', size: '50 KB', url: 'https://www8.cao.go.jp/cstp/ai/', isMinutes: false }
    ],
    tags: ['AI', '生成AI', 'ガバナンス', '著作権', 'セーフティ'],
    officialUrl: 'https://www8.cao.go.jp/cstp/ai/',
    hasMinutes: true,
    docCount: 2
  },
  // 2. DIGITAL
  {
    id: 'meet-2026-0725-digital',
    councilId: 'digital-suishin',
    councilName: 'デジタル社会推進会議',
    ministry: 'DIGITAL',
    category: 'COUNCIL',
    title: '第18回 デジタル社会推進幹事会',
    date: '2026-07-25',
    updatedAt: '2026-07-25 17:00',
    location: 'デジタル庁 20階 大会議室',
    summary: 'マイナポータルのUI/UX刷新計画および次世代行政APIの基盤整備仕様が承認された。また、ガバメントクラウドにおけるマルチクラウド化推進と国産クラウド事業者の選定状況に関する中間報告が提出された。',
    agenda: [
      '行政手続きの原則オンライン化・完全ペーパーレス化の達成度評価',
      'ガバメントクラウドの利用実績および2027年度以降の調達方針',
      'マイナポータルのプッシュ型通知機能拡張に関する基本仕様'
    ],
    materials: [
      { name: '議事次第', type: 'PDF', size: '98 KB', url: 'https://www.digital.go.jp/assets/contents/node/basic_page/field_ref_resources/20260725_01.pdf', isMinutes: false },
      { name: '資料1: 行政DX推進ロードマップ改定（案）', type: 'PDF', size: '3.1 MB', url: 'https://www.digital.go.jp/assets/contents/node/basic_page/field_ref_resources/20260725_02.pdf', isMinutes: false },
      { name: '第18回 議事要旨', type: 'PDF', size: '210 KB', url: 'https://www.digital.go.jp/assets/contents/node/basic_page/field_ref_resources/20260725_minutes.pdf', isMinutes: true }
    ],
    tags: ['デジタル', 'Gov-Cloud', 'マイナンバー', '行政DX', 'API'],
    officialUrl: 'https://www.digital.go.jp/councils/social-promotion/meetings/20260725',
    hasMinutes: true,
    docCount: 3
  },
  // 3. CFA
  {
    id: 'meet-2026-0726-cfa',
    councilId: 'cfa-kodomo-seisaku',
    councilName: 'こども政策審議会',
    ministry: 'CFA',
    category: 'COUNCIL',
    title: '第11回 こども政策審議会 総会',
    date: '2026-07-26',
    updatedAt: '2026-07-26 16:00',
    location: 'こども家庭庁 2階 講堂',
    summary: '「こども加算」の支給実績および「こども誰でも通園制度」の全自治体本格展開に向けたガイドライン改定案が承認された。また、児童虐待防止の早期発見AIシステムの試行結果報告が行われた。',
    agenda: [
      '「こども未来戦略」進捗状況および2027年度予算要求重点事項',
      'こども誰でも通園制度のモデル事業成果検証と本格移行手順',
      '児童相談所におけるデジタルツール活用・AIリスクアセスメント導入'
    ],
    materials: [
      { name: '議事次第', type: 'PDF', size: '105 KB', url: 'https://www.cfa.go.jp/assets/contents/node/basic_page/field_ref_resources/20260726_shidai.pdf', isMinutes: false },
      { name: '資料1: こども未来戦略ロードマップ進捗状況報告', type: 'PDF', size: '2.8 MB', url: 'https://www.cfa.go.jp/assets/contents/node/basic_page/field_ref_resources/20260726_shiryou1.pdf', isMinutes: false },
      { name: '第11回 議事要旨', type: 'HTML', size: '42 KB', url: 'https://www.cfa.go.jp/councils/kodomo_seisaku/20260726_yoshi.html', isMinutes: true }
    ],
    tags: ['少子化対策', 'こども家庭', '児童手当', '保育', '福祉'],
    officialUrl: 'https://www.cfa.go.jp/councils/kodomo_seisaku/meetings/20260726',
    hasMinutes: true,
    docCount: 3
  },
  // 4. FTC
  {
    id: 'meet-2026-0724-ftc',
    councilId: 'ftc-digital-platform',
    councilName: 'デジタル・プラットフォーム競合市場実態調査会',
    ministry: 'FTC',
    category: 'PANEL',
    title: '第15回 デジタル・プラットフォーム競合市場実態調査会',
    date: '2026-07-24',
    updatedAt: '2026-07-24 18:30',
    location: '公正取引委員会 講堂',
    summary: 'スマートフォン向け新法（スマホ新法）に基づく指定事業者に対する遵守要件の運用ガイドライン最終案が公表された。アプリストア決済手数料の適正化およびサイドローディング安全規制について討議。',
    agenda: [
      '特定スマートフォンソフトウェア指定事業者ガイドライン（案）の審議',
      '生成AI基盤モデル開発者とアプリ事業者の独占禁止法上の取引実態報告',
      '欧州DMA（デジタル市場法）の施行状況と我が国独禁法運用の比較分析'
    ],
    materials: [
      { name: '議事次第', type: 'PDF', size: '95 KB', url: 'https://www.jftc.go.jp/houdou/pressrelease/2026/jul/20260724_shidai.pdf', isMinutes: false },
      { name: '資料1: スマホ新法指針運用ガイドライン案', type: 'PDF', size: '3.6 MB', url: 'https://www.jftc.go.jp/houdou/pressrelease/2026/jul/20260724_shiryou1.pdf', isMinutes: false },
      { name: '第15回 議事要旨', type: 'PDF', size: '180 KB', url: 'https://www.jftc.go.jp/houdou/pressrelease/2026/jul/20260724_yoshi.pdf', isMinutes: true }
    ],
    tags: ['独占禁止法', 'BigTech', 'スマホ新法', '公正取引', 'プラットフォーム'],
    officialUrl: 'https://www.jftc.go.jp/houdou/pressrelease/2026/jul/260724.html',
    hasMinutes: true,
    docCount: 3
  },
  // 5. FSA
  {
    id: 'meet-2026-0721-fsa',
    councilId: 'fsa-kinyu-shingi',
    councilName: '金融審議会 金融制度スタディ・グループ',
    ministry: 'FSA',
    category: 'SUBCOMMITTEE',
    title: '金融審議会 金融制度スタディ・グループ 第12回',
    date: '2026-07-21',
    updatedAt: '2026-07-21 17:15',
    location: '金融庁 9階 901会議室',
    summary: '円建てステーブルコインの発行・決済事業に関する銀行法・資金決済法上の実務留意事項および、AIによる投資助言アルゴリズムに対する金融商品取引法上の登録基準が審議された。',
    agenda: [
      'デジタル通貨・ステーブルコインの決済インフラ接続に関する論点整理',
      '生成AIを用いたロボアドバイザー等の規制・説明責任の clarified 化',
      '資産形成推進に向けた新NISA成長投資枠の利用状況統計'
    ],
    materials: [
      { name: '議事次第', type: 'PDF', size: '110 KB', url: 'https://www.fsa.go.jp/singi/singizu/taikou/20260721/shidai.pdf', isMinutes: false },
      { name: '資料1: 金融機関におけるAI利活用ガイドライン（論点メモ）', type: 'PDF', size: '2.1 MB', url: 'https://www.fsa.go.jp/singi/singizu/taikou/20260721/shiryou1.pdf', isMinutes: false },
      { name: '第12回 議事録（全文）', type: 'PDF', size: '450 KB', url: 'https://www.fsa.go.jp/singi/singizu/taikou/20260721/gijiroku.pdf', isMinutes: true }
    ],
    tags: ['金融', 'ステーブルコイン', 'Web3', 'NISA', 'ロボアドバイザー'],
    officialUrl: 'https://www.fsa.go.jp/singi/singizu/taikou/20260721.html',
    hasMinutes: true,
    docCount: 3
  },
  // 6. MOJ
  {
    id: 'meet-2026-0719-moj',
    councilId: 'moj-hosei-shingi',
    councilName: '法制審議会 民法部会',
    ministry: 'MOJ',
    category: 'SUBCOMMITTEE',
    title: '法制審議会 民法部会 第112回会議',
    date: '2026-07-19',
    updatedAt: '2026-07-20 09:30',
    location: '法務省 2階 大会議室',
    summary: 'デジタル署名およびスマートコントラクトの法的効力に関する民法上の特例要綱案が取りまとめられた。AIが自動生成した契約の成立時期と無効・取消原因について法制化の基本方針が示された。',
    agenda: [
      'デジタル技術を活用した契約法制に関する要綱案（中間整理）',
      '共同親権施行後の運用ガイドラインおよびADR（紛争解決手続）整備',
      '戸籍法改定に伴う氏名の読み仮名届出の全国展開状況'
    ],
    materials: [
      { name: '議事次第', type: 'PDF', size: '90 KB', url: 'https://www.moj.go.jp/content/00142001.pdf', isMinutes: false },
      { name: '資料1: 民法（電子契約関係）改正要綱素案', type: 'PDF', size: '1.9 MB', url: 'https://www.moj.go.jp/content/00142002.pdf', isMinutes: false },
      { name: '第112回 部会議事要旨', type: 'PDF', size: '160 KB', url: 'https://www.moj.go.jp/content/00142003.pdf', isMinutes: true }
    ],
    tags: ['法制審議会', '民法', '電子契約', '共同親権', '法務省'],
    officialUrl: 'https://www.moj.go.jp/shingi1/housei_20260719.html',
    hasMinutes: true,
    docCount: 3
  },
  // 7. MOD
  {
    id: 'meet-2026-0717-mod',
    councilId: 'mod-boei-seisan',
    councilName: '防衛生産・技術基盤強化有識者会議',
    ministry: 'MOD',
    category: 'PANEL',
    title: '第9回 防衛生産・技術基盤強化有識者会議',
    date: '2026-07-17',
    updatedAt: '2026-07-17 19:00',
    location: '防衛省 A棟17階 特別会議室',
    summary: '防衛技術イノベーション機関 (GIDO) の設立準備状況、および民生デュアルユース技術 (AI・無人アセット) の急速装備化に向けたファストトラック調達制度の運用方針が合意された。',
    agenda: [
      '防衛技術イノベーション機関の組織構想およびスタートアップ採択スキーム',
      '防衛装備品の指定サプライチェーン企業に対するサイバーセキュリティ認証',
      '自衛隊における自立型無人アセット（USV・UAV）の共同開発要領'
    ],
    materials: [
      { name: '議事次第', type: 'PDF', size: '100 KB', url: 'https://www.mod.go.jp/j/approach/agenda/meeting/20260717_shidai.pdf', isMinutes: false },
      { name: '資料1: 防衛技術イノベーション機関の設立について', type: 'PDF', size: '2.5 MB', url: 'https://www.mod.go.jp/j/approach/agenda/meeting/20260717_shiryou1.pdf', isMinutes: false },
      { name: '第9回 会議要旨', type: 'HTML', size: '36 KB', url: 'https://www.mod.go.jp/j/approach/agenda/meeting/20260717_yoshi.html', isMinutes: true }
    ],
    tags: ['防衛', '安全保障', 'デュアルユース', 'サイバー防衛', '防衛省'],
    officialUrl: 'https://www.mod.go.jp/j/approach/agenda/meeting/20260717.html',
    hasMinutes: true,
    docCount: 3
  },
  // 8. MAFF
  {
    id: 'meet-2026-0712-maff',
    councilId: 'maff-shokuryo-nogyo',
    councilName: '食料・農業・農村政策審議会',
    ministry: 'MAFF',
    category: 'COUNCIL',
    title: '食料・農業・農村政策審議会 企画部会（第45回）',
    date: '2026-07-12',
    updatedAt: '2026-07-12 16:45',
    location: '農林水産省 本館7階 第1特別会議室',
    summary: '改正食料・農業・農村基本法に基づく「食料安全保障指針」およびスマート農業技術導入促進法に基づく融資制度が審議された。気候変動に伴う農産物適応技術の実証成果報告。',
    agenda: [
      '食料自給率目標（カロリーベース）および食料安全保障インディケーター',
      'スマート農業機械の自動走行・遠隔監視における安全基準改定案',
      '環境負荷低減型農業（有機農業・バイオマス利用）の面的拡大スキーム'
    ],
    materials: [
      { name: '議事次第', type: 'PDF', size: '105 KB', url: 'https://www.maff.go.jp/j/council/seisaku/kikaku/attach/pdf/20260712-01.pdf', isMinutes: false },
      { name: '資料1: 食料安全保障指針（案）の概要', type: 'PDF', size: '3.1 MB', url: 'https://www.maff.go.jp/j/council/seisaku/kikaku/attach/pdf/20260712-02.pdf', isMinutes: false },
      { name: '第45回 議事要旨', type: 'PDF', size: '190 KB', url: 'https://www.maff.go.jp/j/council/seisaku/kikaku/attach/pdf/20260712-minutes.pdf', isMinutes: true }
    ],
    tags: ['農林水産', '食料安全保障', 'スマート農業', '食料基本法', '環境'],
    officialUrl: 'https://www.maff.go.jp/j/council/seisaku/kikaku/20260712.html',
    hasMinutes: true,
    docCount: 3
  },
  // 9. MLIT
  {
    id: 'meet-2026-0708-mlit',
    councilId: 'mlit-shakai-sihon',
    councilName: '社会資本整備審議会 道路分科会',
    ministry: 'MLIT',
    category: 'SUBCOMMITTEE',
    title: '第78回 社会資本整備審議会 道路分科会',
    date: '2026-07-08',
    updatedAt: '2026-07-08 17:30',
    location: '国土交通省 10階 共用大会議室',
    summary: '自動運転レベル4対応トラック専用レーンの新東名高速道路での試行区間拡大計画、および老朽化橋梁・トンネルのインフラモニタリングセンサー義務化方針が決定された。',
    agenda: [
      '自動運転対応道路インフラ（磁気マーカー・路車間通信）の全国整備計画',
      '防災・減災、国土強靱化5か年加速化対策の実施状況と達成度',
      '高速道路料金体系の見直し（深夜割引の完全自動適用）'
    ],
    materials: [
      { name: '議事次第', type: 'PDF', size: '110 KB', url: 'https://www.mlit.go.jp/shingikai/sakai/douro/078/images/shidai.pdf', isMinutes: false },
      { name: '資料1: 自動運転社会に向けた道路インフラロードマップ', type: 'PDF', size: '4.2 MB', url: 'https://www.mlit.go.jp/shingikai/sakai/douro/078/images/shiryou1.pdf', isMinutes: false },
      { name: '第78回 議事要旨', type: 'HTML', size: '38 KB', url: 'https://www.mlit.go.jp/shingikai/sakai/douro/078/yoshi.html', isMinutes: true }
    ],
    tags: ['国土交通', '自動運転', 'インフラ', '国土強靱化', '高速道路'],
    officialUrl: 'https://www.mlit.go.jp/shingikai/sakai/douro/078/index.html',
    hasMinutes: true,
    docCount: 3
  },
  {
    id: 'meet-2026-0626-chutou11',
    councilId: 'cas-chutou-jyousei',
    councilName: '中東情勢に関する関係閣僚会議',
    ministry: 'CAS',
    category: 'PANEL',
    title: '中東情勢に関する関係閣僚会議（第11回）',
    date: '2026-06-26',
    updatedAt: '2026-06-26 18:00',
    location: '首相官邸 2階 危機管理センター',
    summary: '中東情勢の緊迫化に伴う日本関係船舶の航行安全確保策、原油・LNG調達体制の安定性評価、および現地邦人保護の手順が確認された。',
    agenda: [
      '中東地域の最新情勢および関係閣僚による安全確保措置の評価',
      '日本関係船舶の航行安全および原油・LNG等のエネルギー安定供給確保',
      '現地在留邦人の安全確保および緊急支援体制の維持方針'
    ],
    materials: [
      { name: '資料1: 経済産業省提出資料 (PDF / 1,068KB)', type: 'PDF', size: '1,068 KB', url: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai11/pdf/siryou1.pdf', isMinutes: false },
      { name: '資料2: 厚生労働省提出資料 (PDF / 852KB)', type: 'PDF', size: '852 KB', url: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai11/pdf/siryou2.pdf', isMinutes: false },
      { name: '資料3: 国土交通省提出資料 (PDF / 767KB)', type: 'PDF', size: '767 KB', url: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai11/pdf/siryou3.pdf', isMinutes: false },
      { name: '資料4: 農林水産省提出資料 (PDF / 575KB)', type: 'PDF', size: '575 KB', url: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai11/pdf/siryou4.pdf', isMinutes: false },
      { name: '資料5: 外務省提出資料（非公開）', type: '非公開', size: '-', url: '#', isMinutes: false, isPrivate: true },
      { name: '資料6: 塗料・シンナーの目詰まり解消対策の進捗 (PDF / 739KB)', type: 'PDF', size: '739 KB', url: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai11/pdf/siryou6.pdf', isMinutes: false },
      { name: '資料7: 目詰まり・偏り解消協力団体・企業名の公表状況 (PDF / 441KB)', type: 'PDF', size: '441 KB', url: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai11/pdf/siryou7.pdf', isMinutes: false },
      { name: '資料8: 自動車のエンジンオイル・シンナーの供給状況に関するアンケート結果 (PDF / 493KB)', type: 'PDF', size: '493 KB', url: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai11/pdf/siryou8.pdf', isMinutes: false },
      { name: '資料9: パン・菓子等販売店の実態把握・目詰まり解消 (PDF / 440KB)', type: 'PDF', size: '440 KB', url: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai11/pdf/siryou9.pdf', isMinutes: false },
      { name: '資料10: 中東情勢を踏まえた医療用手袋の備蓄の放出 (PDF / 447KB)', type: 'PDF', size: '447 KB', url: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai11/pdf/siryou10.pdf', isMinutes: false },
      { name: '資料11: 供給の偏り・流通の目詰まりの解消案件 (PDF / 450KB)', type: 'PDF', size: '450 KB', url: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai11/pdf/siryou11.pdf', isMinutes: false },
      { name: '資料12: Ｇ７の消費者物価と実質賃金 (PDF / 270KB)', type: 'PDF', size: '270 KB', url: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai11/pdf/siryou12.pdf', isMinutes: false }
    ],
    tags: ['中東情勢', '安全保障', '邦人保護', 'エネルギー', '内閣官房'],
    officialUrl: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai11/gijisidai.html',
    hasMinutes: true,
    docCount: 12
  },
  {
    id: 'meet-2026-0611-chutou10',
    councilId: 'cas-chutou-jyousei',
    councilName: '中東情勢に関する関係閣僚会議',
    ministry: 'CAS',
    category: 'PANEL',
    title: '中東情勢に関する関係閣僚会議（第10回）',
    date: '2026-06-11',
    updatedAt: '2026-06-11 17:30',
    location: '首相官邸 2階 危機管理センター',
    summary: 'ホルムズ海峡周辺の情勢推移、海上自衛隊による情報収集活動、および国家備蓄放出の準備状況について協議が行われた。',
    agenda: [
      '中東情勢に関する関係閣僚会議（第10回）開催報告',
      'エネルギー供給への影響と石油備蓄放出手続きの事前確認'
    ],
    materials: [
      { name: '第10回 会議議事要旨 (PDF)', type: 'PDF', size: '210 KB', url: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai10/gijiyoushi.pdf', isMinutes: true },
      { name: '第10回 会議開催概要ページ', type: 'HTML', size: '30 KB', url: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai10/gijisidai.html', isMinutes: false }
    ],
    tags: ['中東情勢', '安全保障', 'エネルギー', '内閣官房'],
    officialUrl: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai10/gijisidai.html',
    hasMinutes: true,
    docCount: 2
  },
  {
    id: 'meet-2026-0602-chutou9',
    councilId: 'cas-chutou-jyousei',
    councilName: '中東情勢に関する関係閣僚会議',
    ministry: 'CAS',
    category: 'PANEL',
    title: '中東情勢に関する関係閣僚会議（第9回）',
    date: '2026-06-02',
    updatedAt: '2026-06-02 16:00',
    location: '首相官邸 2階 危機管理センター',
    summary: '現地邦人の安全確保および民間航空便の運航支援手続きについて審議された。',
    agenda: [
      '現地在留邦人の安全状況および退避支援手順の確認',
      '関係省庁（外務省・防衛省・国土交通省）の連携体制強化'
    ],
    materials: [
      { name: '第9回 会議議事要旨 (PDF)', type: 'PDF', size: '190 KB', url: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai9/gijiyoushi.pdf', isMinutes: true },
      { name: '第9回 会議開催概要ページ', type: 'HTML', size: '28 KB', url: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai9/gijisidai.html', isMinutes: false }
    ],
    tags: ['中東情勢', '邦人保護', '内閣官房'],
    officialUrl: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai9/gijisidai.html',
    hasMinutes: true,
    docCount: 2
  },
  // 10. NPA
  {
    id: 'meet-2026-0704-npa',
    councilId: 'npa-cyber-keisatsu',
    councilName: 'サイバー犯罪・サイバー攻撃対策有識者会議',
    ministry: 'NPA',
    category: 'PANEL',
    title: '第10回 サイバー犯罪・サイバー攻撃対策有識者会議',
    date: '2026-07-04',
    updatedAt: '2026-07-04 18:00',
    location: '警察庁 グランドプラザ会議室',
    summary: '警察庁サイバー特別捜査隊による国際共同テイクダウン作戦の成果報告、およびディープフェイク・音声捏造を用いた詐欺手法に対する注意喚起と高度解析システムの配備が議論された。',
    agenda: [
      'ランサムウェアグループに対する国際刑事警察機構（ICPO）連携の現状',
      'ディープフェイク動画・音声のフォレンジック解析ツールの全国整備',
      '暗号資産交換業者に対する不正送金検知・口座凍結要請手順の標準化'
    ],
    materials: [
      { name: '議事次第', type: 'PDF', size: '85 KB', url: 'https://www.npa.go.jp/bureau/cyber/council/10th/shidai.pdf', isMinutes: false },
      { name: '資料1: 最新のサイバー脅威情勢と警察の取組', type: 'PDF', size: '2.3 MB', url: 'https://www.npa.go.jp/bureau/cyber/council/10th/shiryou1.pdf', isMinutes: false },
      { name: '第10回 議事要旨', type: 'PDF', size: '150 KB', url: 'https://www.npa.go.jp/bureau/cyber/council/10th/yoshi.pdf', isMinutes: true }
    ],
    tags: ['警察庁', 'サイバーセキュリティ', 'ランサムウェア', 'ディープフェイク', '捜査'],
    officialUrl: 'https://www.npa.go.jp/bureau/cyber/council/10th/index.html',
    hasMinutes: true,
    docCount: 3
  },
  // 11. NRA
  {
    id: 'meet-2026-0702-nra',
    councilId: 'nra-teireikai',
    councilName: '原子力規制委員会 定例会',
    ministry: 'NRA',
    category: 'COUNCIL',
    title: '令和8年度 第18回 原子力規制委員会 定例会',
    date: '2026-07-02',
    updatedAt: '2026-07-02 15:00',
    location: '原子力規制委員会 13階 会議室',
    summary: '高浜原子力発電所の運転期間延長（60年超）に関する高経年化技術評価結果、および次世代革新炉（SMR・高温ガス炉）の安全審査指針骨子案が審議・可決された。',
    agenda: [
      '運転期間延長に関する安全審査結果の取りまとめ',
      '次世代小型モジュール炉 (SMR) の設置許可審査ガイドライン（案）',
      '自然災害（火山・大規模地震）発生時における緊急時対応計画の検証'
    ],
    materials: [
      { name: '議事次第', type: 'PDF', size: '90 KB', url: 'https://www.nra.go.jp/data/00045001.pdf', isMinutes: false },
      { name: '資料1: 高浜発電所高経年化評価審査書（案）', type: 'PDF', size: '5.1 MB', url: 'https://www.nra.go.jp/data/00045002.pdf', isMinutes: false },
      { name: '第18回 定例会議事録', type: 'PDF', size: '380 KB', url: 'https://www.nra.go.jp/data/00045003.pdf', isMinutes: true }
    ],
    tags: ['原子力', '安全審査', 'SMR', 'エネルギー', '規制'],
    officialUrl: 'https://www.nra.go.jp/gikai/kisei-gikai/20260702.html',
    hasMinutes: true,
    docCount: 3
  },
  // 12. MOFA
  {
    id: 'meet-2026-0630-mofa',
    councilId: 'mofa-gaiko-seisaku',
    councilName: '外交政策有識者懇談会',
    ministry: 'MOFA',
    category: 'ROUNDTABLE',
    title: '第14回 外交政策有識者懇談会',
    date: '2026-06-30',
    updatedAt: '2026-06-30 18:45',
    location: '外務省 南庁舎3階 特別会議室',
    summary: 'G7サミット成果文書を踏まえた経済安全保障外交戦略、グローバルサウス諸国への技術支援・インフラ投融資 (ODA) の新ガイドラインについて有識者と意見交換を実施。',
    agenda: [
      '自由で開かれたインド太平洋 (FOIP) の推進状況と今後の外交方針',
      'サプライチェーンの多様化に向けた資源国との二国間協定策定',
      'AIガバナンスにおける広島AIプロセスの国際標準化展開'
    ],
    materials: [
      { name: '議事次第', type: 'PDF', size: '85 KB', url: 'https://www.mofa.go.jp/mofaj/files/10052001.pdf', isMinutes: false },
      { name: '資料1: 経済安全保障外交の戦略的展開（論点資料）', type: 'PDF', size: '2.0 MB', url: 'https://www.mofa.go.jp/mofaj/files/10052002.pdf', isMinutes: false },
      { name: '第14回 懇談会概要要旨', type: 'HTML', size: '35 KB', url: 'https://www.mofa.go.jp/mofaj/ms/is/page25_001234_yoshi.html', isMinutes: true }
    ],
    tags: ['外交', '経済安全保障', 'FOIP', 'ODA', '外務省'],
    officialUrl: 'https://www.mofa.go.jp/mofaj/ms/is/page25_001234.html',
    hasMinutes: true,
    docCount: 3
  },
  // 13. RA
  {
    id: 'meet-2026-0625-ra',
    councilId: 'ra-fukko-suishin',
    councilName: '復興推進会議',
    ministry: 'RA',
    category: 'COUNCIL',
    title: '第22回 復興推進会議',
    date: '2026-06-25',
    updatedAt: '2026-06-25 14:30',
    location: '首相官邸 4階 大ホール',
    summary: '福島第1原発周辺の帰還困難区域における避難指示解除ロードマップおよび、福島国際研究教育機構 (FIREC) の先端研究プロジェクト（ロボティクス・廃炉技術・放射線医学）の進捗が確認された。',
    agenda: [
      '特定帰還居住区域の復興・再生計画の認定状況',
      '福島国際研究教育機構（FIREC）の研究開発・産業化事業成果報告',
      '東日本大震災および近年の大規模災害からの復興予算執行状況'
    ],
    materials: [
      { name: '議事次第', type: 'PDF', size: '95 KB', url: 'https://www.reconstruction.go.jp/topics/main-cat1/sub-cat1-1/20260625_shidai.pdf', isMinutes: false },
      { name: '資料1: 福島復興・再生の現状と今後の課題', type: 'PDF', size: '3.4 MB', url: 'https://www.reconstruction.go.jp/topics/main-cat1/sub-cat1-1/20260625_shiryou1.pdf', isMinutes: false },
      { name: '第22回 議事要旨', type: 'PDF', size: '170 KB', url: 'https://www.reconstruction.go.jp/topics/main-cat1/sub-cat1-1/20260625_yoshi.pdf', isMinutes: true }
    ],
    tags: ['復興', '福島', 'FIREC', '防災', '復興庁'],
    officialUrl: 'https://www.reconstruction.go.jp/topics/main-cat1/sub-cat1-1/20260625.html',
    hasMinutes: true,
    docCount: 3
  },
  // 14. CAS & User Requested Council Meetings
  {
    id: 'meet-2026-0730-zensedai',
    councilId: 'cas-zensedai-hosyo',
    councilName: '全世代型社会保障構築会議',
    ministry: 'CAS',
    category: 'PANEL',
    title: '第21回 全世代型社会保障構築会議',
    date: '2026-07-30',
    updatedAt: '2026-07-30 17:00',
    location: '首相官邸 2階 大ホール',
    summary: '医療・介護の自己負担見直しおよび子支援財源「支援金制度」の具体的な徴収スキームに関する議論の取りまとめ案が提示された。',
    agenda: [
      '全世代型社会保障構築に向けた改革工程表の実施状況評価',
      '医療保険制度における高所得者の負担適正化と医療DXの効果波及',
      '介護サービスの基盤整備と生産性向上（ロボット・ICT導入）'
    ],
    materials: [
      { name: '議事次第 (PDF / 70KB)', type: 'PDF', size: '70 KB', url: 'https://www.cas.go.jp/jp/seisaku/zensedai_hosyo/dai21/00_gijisidai.pdf', isMinutes: false },
      { name: '資料1: 医療・介護の構造改革等について (PDF / 1,597KB)', type: 'PDF', size: '1,597 KB', url: 'https://www.cas.go.jp/jp/seisaku/zensedai_hosyo/dai21/01_siryou1.pdf', isMinutes: false },
      { name: '資料2: 医療提供体制の推進方針について (PDF / 3,130KB)', type: 'PDF', size: '3,130 KB', url: 'https://www.cas.go.jp/jp/seisaku/zensedai_hosyo/dai21/02_siryou2.pdf', isMinutes: false },
      { name: '資料3: 介護基盤整備・生産性向上について (PDF / 3,816KB)', type: 'PDF', size: '3,816 KB', url: 'https://www.cas.go.jp/jp/seisaku/zensedai_hosyo/dai21/03_siryou3.pdf', isMinutes: false },
      { name: '資料4: 地域共生社会の構築に向けた施策 (PDF / 3,710KB)', type: 'PDF', size: '3,710 KB', url: 'https://www.cas.go.jp/jp/seisaku/zensedai_hosyo/dai21/04_siryou4.pdf', isMinutes: false },
      { name: '資料5: 高齢者医療制度の見直しについて (PDF / 836KB)', type: 'PDF', size: '836 KB', url: 'https://www.cas.go.jp/jp/seisaku/zensedai_hosyo/dai21/05_siryou5.pdf', isMinutes: false },
      { name: '資料6: 地域医療構想の推進について (PDF / 589KB)', type: 'PDF', size: '589 KB', url: 'https://www.cas.go.jp/jp/seisaku/zensedai_hosyo/dai21/06_siryou6.pdf', isMinutes: false },
      { name: '資料7: 委員提出資料 (PDF / 475KB)', type: 'PDF', size: '475 KB', url: 'https://www.cas.go.jp/jp/seisaku/zensedai_hosyo/dai21/07_siryou7.pdf', isMinutes: false },
      { name: '参考資料1: 経済財政運営と改革の基本方針2025 (PDF / 1,158KB)', type: 'PDF', size: '1,158 KB', url: 'https://www.cas.go.jp/jp/seisaku/zensedai_hosyo/dai21/08_sankou1.pdf', isMinutes: false },
      { name: '参考資料2: デジタル田園都市国家構想構想書 (PDF / 884KB)', type: 'PDF', size: '884 KB', url: 'https://www.cas.go.jp/jp/seisaku/zensedai_hosyo/dai21/09_sankou2.pdf', isMinutes: false },
      { name: '参考資料3: 全世代型社会保障構築会議 報告書 (PDF / 960KB)', type: 'PDF', size: '960 KB', url: 'https://www.cas.go.jp/jp/seisaku/zensedai_hosyo/dai21/10_sankou3.pdf', isMinutes: false }
    ],
    tags: ['社会保障', '医療 reform', '介護', '少子化対策', '内閣官房'],
    officialUrl: 'https://www.cas.go.jp/jp/seisaku/zensedai_hosyo/dai21/gijisidai.html',
    hasMinutes: true,
    docCount: 11
  },
  {
    id: 'meet-2026-0729-aihq',
    councilId: 'cao-ai-hq',
    councilName: '人工知能戦略本部',
    ministry: 'CAO',
    category: 'COUNCIL',
    title: '第5回 人工知能戦略本部 会議',
    date: '2026-07-29',
    updatedAt: '2026-07-29 16:30',
    location: '内閣府 講堂（中央合同庁舎第8号館）',
    summary: '国家AI安全法案（仮称）の骨子案が可決され、フロンティアAI事業者への安全評価届出義務化およびAI安全研究所 (AISI) の権限強化方針が決定した。',
    agenda: [
      'AI安全推進法制の整備に向けた基本方針の可決',
      '我が国におけるスーパーコンピュータ・AIインフラ整備計画（第2期）',
      '国際的なAIセーフティ・ネットワーク (AISN) への日本の貢献方針'
    ],
    materials: [
      { name: '第5回 人工知能戦略本部 会議議事概要 (PDF)', type: 'PDF', size: '210 KB', url: 'https://www8.cao.go.jp/cstp/ai/ai_hq/5kai/gijigaiyo.pdf', isMinutes: true },
      { name: '第3回 人工知能戦略本部 会議議事概要 (PDF)', type: 'PDF', size: '240 KB', url: 'https://www8.cao.go.jp/cstp/ai/ai_hq/3kai/gijigaiyo.pdf', isMinutes: true },
      { name: '人工知能戦略本部 開催状況公式ページ', type: 'HTML', size: '50 KB', url: 'https://www8.cao.go.jp/cstp/ai/ai_hq/kaisai.html', isMinutes: false }
    ],
    tags: ['AI', '人工知能戦略本部', 'AISI', 'AI法制', '内閣府'],
    officialUrl: 'https://www8.cao.go.jp/cstp/ai/ai_hq/kaisai.html',
    hasMinutes: true,
    docCount: 3
  },
  {
    id: 'meet-2026-0626-chutou11',
    councilId: 'cas-chutou-jyousei',
    councilName: '中東情勢に関する関係閣僚会議',
    ministry: 'CAS',
    category: 'PANEL',
    title: '中東情勢に関する関係閣僚会議（第11回）',
    date: '2026-06-26',
    updatedAt: '2026-06-26 18:00',
    location: '首相官邸 2階 危機管理センター',
    summary: '中東情勢の緊迫化に伴う日本関係船舶の航行安全確保策、原油・LNG調達体制の安定性評価、および現地邦人保護の手順が確認された。',
    agenda: [
      '中東地域の最新情勢および関係閣僚による安全確保措置の評価',
      '日本関係船舶の航行安全および原油・LNG等のエネルギー安定供給確保',
      '現地在留邦人の安全確保および緊急支援体制の維持方針'
    ],
    materials: [
      { name: '第11回 会議配布資料1 (PDF)', type: 'PDF', size: '240 KB', url: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai11/pdf/siryou1.pdf', isMinutes: false },
      { name: '第11回 会議開催概要ページ', type: 'HTML', size: '32 KB', url: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai11/gijisidai.html', isMinutes: true },
      { name: '中東情勢に関する対応 公式ポータル', type: 'HTML', size: '35 KB', url: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/index.html', isMinutes: false }
    ],
    tags: ['中東情勢', '安全保障', '邦人保護', 'エネルギー', '内閣官房'],
    officialUrl: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai11/gijisidai.html',
    hasMinutes: true,
    docCount: 3
  },
  {
    id: 'meet-2026-0611-chutou10',
    councilId: 'cas-chutou-jyousei',
    councilName: '中東情勢に関する関係閣僚会議',
    ministry: 'CAS',
    category: 'PANEL',
    title: '中東情勢に関する関係閣僚会議（第10回）',
    date: '2026-06-11',
    updatedAt: '2026-06-11 17:30',
    location: '首相官邸 2階 危機管理センター',
    summary: 'ホルムズ海峡周辺の情勢推移、海上自衛隊による情報収集活動、および国家備蓄放出の準備状況について協議が行われた。',
    agenda: [
      '中東情勢に関する関係閣僚会議（第10回）開催報告',
      'エネルギー供給への影響と石油備蓄放出手続きの事前確認'
    ],
    materials: [
      { name: '第10回 会議議事要旨 (PDF)', type: 'PDF', size: '210 KB', url: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai10/gijiyoushi.pdf', isMinutes: true },
      { name: '第10回 会議開催概要ページ', type: 'HTML', size: '30 KB', url: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai10/gijisidai.html', isMinutes: false }
    ],
    tags: ['中東情勢', '安全保障', 'エネルギー', '内閣官房'],
    officialUrl: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai10/gijisidai.html',
    hasMinutes: true,
    docCount: 2
  },
  {
    id: 'meet-2026-0602-chutou9',
    councilId: 'cas-chutou-jyousei',
    councilName: '中東情勢に関する関係閣僚会議',
    ministry: 'CAS',
    category: 'PANEL',
    title: '中東情勢に関する関係閣僚会議（第9回）',
    date: '2026-06-02',
    updatedAt: '2026-06-02 16:00',
    location: '首相官邸 2階 危機管理センター',
    summary: '現地邦人の安全確保および民間航空便の運航支援手続きについて審議された。',
    agenda: [
      '現地在留邦人の安全状況および退避支援手順の確認',
      '関係省庁（外務省・防衛省・国土交通省）の連携体制強化'
    ],
    materials: [
      { name: '第9回 会議議事要旨 (PDF)', type: 'PDF', size: '190 KB', url: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai9/gijiyoushi.pdf', isMinutes: true },
      { name: '第9回 会議開催概要ページ', type: 'HTML', size: '28 KB', url: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai9/gijisidai.html', isMinutes: false }
    ],
    tags: ['中東情勢', '邦人保護', '内閣官房'],
    officialUrl: 'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai9/gijisidai.html',
    hasMinutes: true,
    docCount: 2
  },
  {
    id: 'meet-2026-0714-kokumin',
    councilId: 'cas-kokumin-kaigi',
    councilName: '社会保障国民会議',
    ministry: 'CAS',
    category: 'COUNCIL',
    title: '第12回 社会保障国民会議',
    date: '2026-07-14',
    updatedAt: '2026-07-14 17:30',
    location: '内閣官房 講堂',
    summary: '2040年を見据えた社会保障給付と負担の将来見通し、年金受給開始年齢の柔軟化、高齢者の就労促進と医療費適正化の総合ビジョンが公表された。',
    agenda: [
      '2040年社会保障将来推計と必要財源のシミュレーション結果',
      '医療・介護従事者の確保と賃上げ支援の実施状況',
      '国民的合意形成に向けた社会保障改革広報戦略'
    ],
    materials: [
      { name: '社会保障国民会議 公式ポータル', type: 'HTML', size: '55 KB', url: 'https://www.cas.go.jp/jp/seisaku/kokuminkaigi/index.html', isMinutes: true }
    ],
    tags: ['社会保障', '医療', '年金', '介護', '内閣官房'],
    officialUrl: 'https://www.cas.go.jp/jp/seisaku/kokuminkaigi/index.html',
    hasMinutes: true,
    docCount: 1
  }
];

// Initial alert keywords stored in app
const INITIAL_ALERT_KEYWORDS = ['AI', 'サイバーセキュリティ', '規制改革', '社会保障', '脱炭素', '独占禁止法', '個人情報保護'];
