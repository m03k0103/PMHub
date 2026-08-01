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
    officialUrl: 'https://www8.cao.go.jp/cstp/ai/ai_senryaku/ai_senryaku.html',
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
    name: 'デジタル社会推進会議幹事会',
    ministry: 'DIGITAL',
    category: 'COUNCIL',
    pastYearCount: 23,
    description: 'マイナンバー制度、ベース・レジストリ、ガバメントクラウド (Gov-Cloud) および行政DXの推進実務を取りまとめる幹事会。',
    officialUrl: 'https://www.digital.go.jp/councils/social-promotion-executive',
    isWatched: true,
    trackedSince: '2021-09-01'
  },
  // 3. CFA
  {
    id: 'cfa-kodomo-suishin',
    name: 'こども政策推進会議',
    ministry: 'CFA',
    category: 'COUNCIL',
    pastYearCount: 6,
    description: 'こどもまんなか実行計画、こども・若者自殺防止総力戦略、こども施策の基本方針を閣僚級で推進・決定する重要会議。',
    officialUrl: 'https://www.cfa.go.jp/councils/suishinkaigi',
    isWatched: true,
    trackedSince: '2023-04-01'
  },
  {
    id: 'cfa-kodomo-shingikai',
    name: 'こども家庭審議会',
    ministry: 'CFA',
    category: 'COUNCIL',
    pastYearCount: 12,
    description: '「こども未来戦略」に基づく少子化対策、児童手当拡充、こども誰でも通園制度、児童虐待防止・予算案の中長期計画を審議。',
    officialUrl: 'https://www.cfa.go.jp/councils/shingikai',
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
    officialUrl: 'https://www.soumu.go.jp/menu_kyotsuu/whatsnew/kaigi_index.html',
    isWatched: false,
    trackedSince: '2022-06-01'
  },
  // 6. MOJ
  {
    id: 'moj-hosei-shingi',
    name: '法制審議会',
    ministry: 'MOJ',
    category: 'COUNCIL',
    pastYearCount: 9,
    description: '民法・会社法・刑事法・各種手続法等の法改正要綱案の答申、および法務大臣からの諮問事項（犯罪被害者支援・会社法制等）を審議。',
    officialUrl: 'https://www.moj.go.jp/shingi1/shingikai_soukai.html',
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
    officialUrl: 'https://www.mofa.go.jp/mofaj/index.html',
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
    officialUrl: 'https://www.mhlw.go.jp/stf/shingi/index.html',
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
    officialUrl: 'https://www.mlit.go.jp/policy/shingikai/index.html',
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
    id: 'mod-cho-shin',
    name: '防衛調達審議会',
    ministry: 'MOD',
    category: 'COUNCIL',
    pastYearCount: 198,
    description: '防衛調達の公平性・透明性の確保および防衛装備品の効率的な調達・契約変更適正審査に関する調査審議。',
    officialUrl: 'https://www.mod.go.jp/j/policy/agenda/meeting/cho-shin/index.html',
    isWatched: true,
    trackedSince: '2022-01-10'
  },
  {
    id: 'mod-drastic-reinforcement',
    name: '防衛力の抜本的強化に関する有識者会議',
    ministry: 'MOD',
    category: 'PANEL',
    pastYearCount: 14,
    description: '国家安全保障戦略に基づき、防衛力の抜本的強化・防衛生産・技術基盤の維持強化に関する提言および有識者議論。',
    officialUrl: 'https://www.mod.go.jp/j/policy/agenda/meeting/drastic-reinforcement/index.html',
    isWatched: true,
    trackedSince: '2023-01-15'
  },
  {
    id: 'mod-defense-industry-wg',
    name: '防衛産業ワーキンググループ',
    ministry: 'MOD',
    category: 'ROUNDTABLE',
    pastYearCount: 5,
    description: '防衛生産・技術基盤の強化、防衛装備品の官民連携・産業基盤育成に向けたワーキンググループ。',
    officialUrl: 'https://www.mod.go.jp/j/policy/agenda/meeting/defense_industry_wg/index.html',
    isWatched: true,
    trackedSince: '2023-05-20'
  },
  // 16. NPA
  {
    id: 'npa-cyber-keisatsu',
    name: 'サイバー犯罪・サイバー攻撃対策有識者会議',
    ministry: 'NPA',
    category: 'PANEL',
    pastYearCount: 6,
    description: 'ランサムウェア・フィッシング被害対策、暗号資産の不正送金防止、重要インフラ防護および能動的サイバー防御の法的整理。',
    officialUrl: 'https://www.npa.go.jp/bureau/cyber/index.html',
    isWatched: true,
    trackedSince: '2023-03-15'
  },
  // 17. FSA
  {
    id: 'fsa-kinyu-shingi',
    name: '金融審議会',
    ministry: 'FSA',
    category: 'COUNCIL',
    pastYearCount: 16,
    description: '金融システムの安定、市場機能の円滑化、地域金融力の強化、暗号資産制度、サステナビリティ開示、ディスクロージャー等の金融行政の重要事項を審議。',
    officialUrl: 'https://www.fsa.go.jp/singi/singi_kinyu/base_gijiroku.html',
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
    officialUrl: 'https://www.caa.go.jp',
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
    officialUrl: 'https://www.ppc.go.jp/aboutus/',
    isWatched: true,
    trackedSince: '2023-04-15'
  },
  // 20. NRA
  {
    id: 'nra-teireikai',
    name: '原子力規制委員会 定例会',
    ministry: 'NRA',
    category: 'COUNCIL',
    pastYearCount: 48,
    description: '原子力発電所の新規制基準適合性審査、高レベル放射性廃棄物最終処分場の地質調査評価、安全協定の検証を実施。',
    officialUrl: 'https://www.nra.go.jp/index.html',
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
    id: 'meet-2025-0602-ai14',
    councilId: 'cao-ai-strategy',
    councilName: 'AI戦略会議',
    ministry: 'CAO',
    category: 'PANEL',
    title: '第14回 AI戦略会議',
    date: '2025-06-02',
    updatedAt: '2025-06-02 18:30',
    location: '中央合同庁舎第8号館 講堂（オンライン併用）',
    summary: 'AI法の概要案および今後のAI政策の進め方について審議が行われた。',
    agenda: [
      'AI法の概要についての説明および質疑応答',
      '今後のAI政策の進め方に関する方針議論',
      '統合イノベーション戦略2025 AIパート（案）の審議'
    ],
    materials: [
      { name: '資料1-1: AI法の概要 (PDF / 442KB)', type: 'PDF', size: '442 KB', url: 'https://www8.cao.go.jp/cstp/ai/ai_senryaku/14kai/shiryou1-1.pdf', isMinutes: false },
      { name: '資料1-2: 今後のAI政策の進め方 (PDF / 515KB)', type: 'PDF', size: '515 KB', url: 'https://www8.cao.go.jp/cstp/ai/ai_senryaku/14kai/shiryou1-2.pdf', isMinutes: false },
      { name: '資料2: 統合イノベーション戦略2025AIパート（案）', type: '非公開', size: '-', url: '#', isPrivate: true, isMinutes: false },
      { name: '参考資料: AI戦略会議 構成員名簿 (PDF / 164KB)', type: 'PDF', size: '164 KB', url: 'https://www8.cao.go.jp/cstp/ai/ai_senryaku/14kai/sankou.pdf', isMinutes: false },
      { name: '第14回 会議公式ページ', type: 'HTML', size: '35 KB', url: 'https://www8.cao.go.jp/cstp/ai/ai_senryaku/14kai/14kai.html', isMinutes: false }
    ],
    tags: ['AI', 'AI法', 'AI戦略会議', '統合イノベーション戦略', '内閣府'],
    officialUrl: 'https://www8.cao.go.jp/cstp/ai/ai_senryaku/14kai/14kai.html',
    hasMinutes: true,
    docCount: 5
  },
  // 2. DIGITAL
  {
    id: 'meet-2025-0512-digital18',
    councilId: 'digital-suishin',
    councilName: 'デジタル社会推進会議',
    ministry: 'DIGITAL',
    category: 'COUNCIL',
    title: '第3回各府省庁DX推進連絡会議・第18回デジタル社会推進会議幹事会合同会議',
    date: '2025-05-12',
    updatedAt: '2025-05-12 17:00',
    location: '中央合同庁舎第4号館 全省庁共用 1208 特別会議室',
    summary: 'デジタル行財政改革の更なる推進、各府省庁DX推進の依頼事項、人事管理業務のデジタル化・高度化、旅費業務プロセスの改善について審議された。',
    agenda: [
      'デジタル行財政改革の更なる推進について',
      '各府省庁DXの更なる効果発現に向けた依頼事項について',
      '人事管理業務のデジタル化・高度化および旅費業務プロセスの改善について'
    ],
    materials: [
      { name: '議事次第 (PDF / 53KB)', type: 'PDF', size: '53 KB', url: 'https://www.digital.go.jp/assets/contents/node/basic_page/field_ref_resources/6b76d2f7-8381-4173-9820-623ad9f20b64/88608d98/20250512_meeting_executive_agenda_01.pdf', isMinutes: false },
      { name: '資料1: デジタル行財政改革の更なる推進について (PDF / 1,000KB)', type: 'PDF', size: '1,000 KB', url: 'https://www.digital.go.jp/assets/contents/node/basic_page/field_ref_resources/6b76d2f7-8381-4173-9820-623ad9f20b64/7108a06f/20250512_meeting_executive_outline_02.pdf', isMinutes: false },
      { name: '資料2: 各府省庁DXの更なる効果発現に向けた依頼事項について (PDF / 1,930KB)', type: 'PDF', size: '1,930 KB', url: 'https://www.digital.go.jp/assets/contents/node/basic_page/field_ref_resources/6b76d2f7-8381-4173-9820-623ad9f20b64/f95e885a/20250512_meeting_executive_outline_03.pdf', isMinutes: false },
      { name: '資料3: 人事管理業務のデジタル化・高度化について (PDF / 1,350KB)', type: 'PDF', size: '1,350 KB', url: 'https://www.digital.go.jp/assets/contents/node/basic_page/field_ref_resources/6b76d2f7-8381-4173-9820-623ad9f20b64/a09760b9/20250512_meeting_executive_outline_04.pdf', isMinutes: false },
      { name: '資料4: 旅費業務プロセスの改善について (PDF / 1,450KB)', type: 'PDF', size: '1,450 KB', url: 'https://www.digital.go.jp/assets/contents/node/basic_page/field_ref_resources/6b76d2f7-8381-4173-9820-623ad9f20b64/73db36c7/20250512_meeting_executive_outline_05.pdf', isMinutes: false },
      { name: '資料5: 経由調査に関する業務の実態把握の結果 (PDF / 2,200KB)', type: 'PDF', size: '2,200 KB', url: 'https://www.digital.go.jp/assets/contents/node/basic_page/field_ref_resources/6b76d2f7-8381-4173-9820-623ad9f20b64/2623a736/20250512_meeting_executive_outline_06.pdf', isMinutes: false },
      { name: '資料6: DX推進のための体制整備について (PDF / 1,780KB)', type: 'PDF', size: '1,780 KB', url: 'https://www.digital.go.jp/assets/contents/node/basic_page/field_ref_resources/6b76d2f7-8381-4173-9820-623ad9f20b64/34ee9056/20250512_meeting_executive_outline_07.pdf', isMinutes: false },
      { name: '第18回 会議公式ページ', type: 'HTML', size: '35 KB', url: 'https://www.digital.go.jp/councils/social-promotion-executive/6b76d2f7-8381-4173-9820-623ad9f20b64', isMinutes: false }
    ],
    tags: ['デジタル行財政改革', 'Gov-Cloud', '行政DX', 'デジタル庁', '旅費改革'],
    officialUrl: 'https://www.digital.go.jp/councils/social-promotion-executive/6b76d2f7-8381-4173-9820-623ad9f20b64',
    hasMinutes: true,
    docCount: 8
  },
  // 3. CFA
  {
    id: 'meet-2026-0609-suishin',
    councilId: 'cfa-kodomo-suishin',
    councilName: 'こども政策推進会議',
    ministry: 'CFA',
    category: 'COUNCIL',
    title: '第6回 こども政策推進会議',
    date: '2026-06-09',
    updatedAt: '2026-06-09 08:40',
    location: '首相官邸 4階 大会議室',
    summary: '「こどもまんなか実行計画2026」概要案および大臣プロジェクト2026第1弾「こども・若者 自殺防止総力戦略」について決定・指示が行われた。',
    agenda: [
      '「こどもまんなか実行計画2026」について',
      '「こどもの命と安全を徹底的に守る」大臣プロジェクト2026 第1弾『こども・若者 自殺防止総力戦略』について'
    ],
    materials: [
      { name: '議事次第 (PDF / 179KB)', type: 'PDF', size: '179 KB', url: 'https://www.cfa.go.jp/assets/contents/node/basic_page/field_ref_resources/4c72c8fd-e687-4a9d-ae40-b48448ecc5b2/0398f0eb/20260608_councils_suishinkaigi_4c72c8fd_01.pdf', isMinutes: false },
      { name: '資料1: 「こどもまんなか実行計画2026」概要（案） (PDF / 713KB)', type: 'PDF', size: '713 KB', url: 'https://www.cfa.go.jp/assets/contents/node/basic_page/field_ref_resources/4c72c8fd-e687-4a9d-ae40-b48448ecc5b2/5c47bc06/20260608_councils_suishinkaigi_4c72c8fd_05.pdf', isMinutes: false },
      { name: '資料2: 「こどもの命と安全を徹底的に守る」大臣プロジェクト2026 第1弾『こども・若者 自殺防止総力戦略』について (PDF / 534KB)', type: 'PDF', size: '534 KB', url: 'https://www.cfa.go.jp/assets/contents/node/basic_page/field_ref_resources/4c72c8fd-e687-4a9d-ae40-b48448ecc5b2/25910313/20260608_councils_suishinkaigi_4c72c8fd_03.pdf', isMinutes: false },
      { name: '資料3: こどもまんなか実行計画2026（案） (PDF / 1.0MB)', type: 'PDF', size: '1.0 MB', url: 'https://www.cfa.go.jp/assets/contents/node/basic_page/field_ref_resources/4c72c8fd-e687-4a9d-ae40-b48448ecc5b2/f30a7b88/20260608_councils_suishinkaigi_4c72c8fd_07.pdf', isMinutes: false },
      { name: '議事要旨 (PDF / 248KB)', type: 'PDF', size: '248 KB', url: 'https://www.cfa.go.jp/assets/contents/node/basic_page/field_ref_resources/4c72c8fd-e687-4a9d-ae40-b48448ecc5b2/469ce15f/20260622_councils_suishinkaigi_4c72c8fd_08.pdf', isMinutes: true },
      { name: '第6回 会議公式ページ', type: 'HTML', size: '35 KB', url: 'https://www.cfa.go.jp/councils/suishinkaigi/4c72c8fd', isMinutes: false }
    ],
    tags: ['こども政策推進会議', 'こどもまんなか', '自殺防止', 'こども家庭庁'],
    officialUrl: 'https://www.cfa.go.jp/councils/suishinkaigi/4c72c8fd',
    hasMinutes: true,
    docCount: 6
  },
  {
    id: 'meet-2026-0122-shingikai',
    councilId: 'cfa-kodomo-shingikai',
    councilName: 'こども家庭審議会',
    ministry: 'CFA',
    category: 'COUNCIL',
    title: '第7回 こども家庭審議会',
    date: '2026-01-22',
    updatedAt: '2026-01-22 16:00',
    location: 'こども家庭庁 14階 共用大会議室',
    summary: '各分科会・部会の調査審議状況、令和8年度当初予算案のポイントおよび「こどもまんなか実行計画2026」策定について意見交換が行われた。',
    agenda: [
      '今後の分科会・部会における調査・審議及びこども家庭庁の最近の取組等について',
      '「こどもまんなか実行計画2026」の策定について（案）',
      '令和8年度こども家庭庁当初予算案のポイント'
    ],
    materials: [
      { name: '議事次第 (PDF / 155KB)', type: 'PDF', size: '155 KB', url: 'https://www.cfa.go.jp/assets/contents/node/basic_page/field_ref_resources/f1e48c87-1be5-46c9-908d-b6e93dc09f6b/1d9cb810/20260115_councils_shingikai_f1e48c87_06.pdf', isMinutes: false },
      { name: '資料1: こども家庭審議会 各分科会・部会の調査審議状況について (PDF / 563KB)', type: 'PDF', size: '563 KB', url: 'https://www.cfa.go.jp/assets/contents/node/basic_page/field_ref_resources/f1e48c87-1be5-46c9-908d-b6e93dc09f6b/69125f20/20260115_councils_shingikai_f1e48c87_01.pdf', isMinutes: false },
      { name: '資料2: 「こどもまんなか実行計画2026」の策定について（案） (PDF / 1.4MB)', type: 'PDF', size: '1.4 MB', url: 'https://www.cfa.go.jp/assets/contents/node/basic_page/field_ref_resources/f1e48c87-1be5-46c9-908d-b6e93dc09f6b/56721525/20260115_councils_shingikai_f1e48c87_07.pdf', isMinutes: false },
      { name: '資料3: 令和8年度こども家庭庁当初予算案のポイント (PDF / 1.9MB)', type: 'PDF', size: '1.9 MB', url: 'https://www.cfa.go.jp/assets/contents/node/basic_page/field_ref_resources/f1e48c87-1be5-46c9-908d-b6e93dc09f6b/3cfafbf2/20260115_councils_shingikai_f1e48c87_03.pdf', isMinutes: false },
      { name: '資料4: 五十嵐委員提出資料 (PDF / 207KB)', type: 'PDF', size: '207 KB', url: 'https://www.cfa.go.jp/assets/contents/node/basic_page/field_ref_resources/f1e48c87-1be5-46c9-908d-b6e93dc09f6b/7299c5f2/20260115_councils_shingikai_f1e48c87_08.pdf', isMinutes: false },
      { name: '資料5: 倉石委員提出資料 (PDF / 713KB)', type: 'PDF', size: '713 KB', url: 'https://www.cfa.go.jp/assets/contents/node/basic_page/field_ref_resources/f1e48c87-1be5-46c9-908d-b6e93dc09f6b/6b4ed8d3/20260115_councils_shingikai_f1e48c87_09.pdf', isMinutes: false },
      { name: '参考資料1: 令和8年度こども家庭庁当初予算案主要施策集 (PDF / 3.3MB)', type: 'PDF', size: '3.3 MB', url: 'https://www.cfa.go.jp/assets/contents/node/basic_page/field_ref_resources/f1e48c87-1be5-46c9-908d-b6e93dc09f6b/964190c4/20260115_councils_shingikai_f1e48c87_04.pdf', isMinutes: false },
      { name: '議事録 (PDF / 579KB)', type: 'PDF', size: '579 KB', url: 'https://www.cfa.go.jp/assets/contents/node/basic_page/field_ref_resources/f1e48c87-1be5-46c9-908d-b6e93dc09f6b/2ce7e02c/20260212_councils_shingikai_f1e48c87_10.pdf', isMinutes: true },
      { name: '第7回 会議公式ページ', type: 'HTML', size: '35 KB', url: 'https://www.cfa.go.jp/councils/shingikai/f1e48c87', isMinutes: false }
    ],
    tags: ['こども家庭審議会', 'こども家庭庁', '予算案', '実行計画', '福祉'],
    officialUrl: 'https://www.cfa.go.jp/councils/shingikai/f1e48c87',
    hasMinutes: true,
    docCount: 9
  },
  // 4. FSA
  {
    id: 'meet-2026-0203-fsa',
    councilId: 'fsa-kinyu-shingi',
    councilName: '金融審議会',
    ministry: 'FSA',
    category: 'COUNCIL',
    title: '第56回金融審議会総会・第44回金融分科会合同会合',
    date: '2026-02-03',
    updatedAt: '2026-02-03 11:30',
    location: '中央合同庁舎第７号館13階 共用第１特別会議室 及び オンライン形式',
    summary: '「地域金融力の強化WG」「暗号資産制度WG」「市場制度WG」「サステナビリティ情報の開示と保証のあり方WG」「ディスクロージャーWG」の各報告および答申案が審議・報告された。',
    agenda: [
      '開会・挨拶',
      '諮問事項にかかる報告（地域金融・暗号資産・市場制度・サステナビリティ開示・ディスクロージャー）',
      '討議および報告書の取りまとめ',
      '閉会'
    ],
    materials: [
      { name: '資料1-1: 説明資料（金融審議会「地域金融力の強化に関するワーキング・グループ」報告） (PDF)', type: 'PDF', size: '1.2 MB', url: 'https://www.fsa.go.jp/singi/singi_kinyu/soukai/siryou/20260203/1-1.pdf', isMinutes: false },
      { name: '資料1-2: 金融審議会「地域金融力の強化に関するワーキング・グループ」報告 (PDF)', type: 'PDF', size: '2.4 MB', url: 'https://www.fsa.go.jp/singi/singi_kinyu/soukai/siryou/20260203/1-2.pdf', isMinutes: false },
      { name: '資料2-1: 説明資料（金融審議会「暗号資産制度に関するワーキング・グループ」報告） (PDF)', type: 'PDF', size: '1.5 MB', url: 'https://www.fsa.go.jp/singi/singi_kinyu/soukai/siryou/20260203/2-1.pdf', isMinutes: false },
      { name: '資料2-2: 金融審議会「暗号資産制度に関するワーキング・グループ」報告 (PDF)', type: 'PDF', size: '3.1 MB', url: 'https://www.fsa.go.jp/singi/singi_kinyu/soukai/siryou/20260203/2-2.pdf', isMinutes: false },
      { name: '資料3-1: 説明資料（金融審議会「市場制度ワーキング・グループ」報告） (PDF)', type: 'PDF', size: '1.8 MB', url: 'https://www.fsa.go.jp/singi/singi_kinyu/soukai/siryou/20260203/3-1.pdf', isMinutes: false },
      { name: '資料3-2: 金融審議会「市場制度ワーキング・グループ」報告 (PDF)', type: 'PDF', size: '3.6 MB', url: 'https://www.fsa.go.jp/singi/singi_kinyu/soukai/siryou/20260203/3-2.pdf', isMinutes: false },
      { name: '資料4-1: 説明資料（金融審議会「サステナビリティ情報の開示と保証のあり方に関するワーキング・グループ」報告） (PDF)', type: 'PDF', size: '1.4 MB', url: 'https://www.fsa.go.jp/singi/singi_kinyu/soukai/siryou/20260203/4-1.pdf', isMinutes: false },
      { name: '資料4-2: 金融審議会「サステナビリティ情報の開示と保証のあり方に関するワーキング・グループ」報告 (PDF)', type: 'PDF', size: '2.9 MB', url: 'https://www.fsa.go.jp/singi/singi_kinyu/soukai/siryou/20260203/4-2.pdf', isMinutes: false },
      { name: '資料5-1: 説明資料（金融審議会「ディスクロージャーワーキング・グループ」報告） (PDF)', type: 'PDF', size: '1.1 MB', url: 'https://www.fsa.go.jp/singi/singi_kinyu/soukai/siryou/20260203/5-1.pdf', isMinutes: false },
      { name: '資料5-2: 金融審議会「ディスクロージャーワーキング・グループ」報告 (PDF)', type: 'PDF', size: '2.2 MB', url: 'https://www.fsa.go.jp/singi/singi_kinyu/soukai/siryou/20260203/5-2.pdf', isMinutes: false },
      { name: '資料6: 金融審議会委員名簿 (PDF)', type: 'PDF', size: '210 KB', url: 'https://www.fsa.go.jp/singi/singi_kinyu/soukai/siryou/20260203/6.pdf', isMinutes: false },
      { name: '第56回総会・第44回分科会合同会合 議事次第ページ', type: 'HTML', size: '35 KB', url: 'https://www.fsa.go.jp/singi/singi_kinyu/soukai/siryou/20260203.html', isMinutes: false }
    ],
    tags: ['金融審議会', '地域金融', '暗号資産', '市場制度', 'サステナビリティ開示', 'ディスクロージャー', '金融庁'],
    officialUrl: 'https://www.fsa.go.jp/singi/singi_kinyu/soukai/siryou/20260203.html',
    hasMinutes: true,
    docCount: 12
  },
  // 6. MOJ
  {
    id: 'meet-2026-0615-moj',
    councilId: 'moj-hosei-shingi',
    councilName: '法制審議会',
    ministry: 'MOJ',
    category: 'COUNCIL',
    title: '法制審議会第２０５回会議',
    date: '2026-06-15',
    updatedAt: '2026-06-15 17:00',
    location: '法務省 大会議室',
    summary: '「犯罪被害者等の刑事手続への関与等の在り方に関する諮問第130号」に関し刑事法（犯罪被害者関係）部会への付託が決定され、会社法制（株式・株主総会等関係）部会における審議経過報告が行われた。',
    agenda: [
      '犯罪被害者等の刑事手続への関与等の在り方に関する諮問第１３０号について',
      '会社法制に関する諮問第１２７号について'
    ],
    materials: [
      { name: '配布資料1: 諮問第１３0号 (PDF)', type: 'PDF', size: '180 KB', url: 'https://www.moj.go.jp/content/001464734.pdf', isMinutes: false },
      { name: '配布資料2: 「第５次犯罪被害者等基本計画」該当箇所抜粋 (PDF)', type: 'PDF', size: '320 KB', url: 'https://www.moj.go.jp/content/001464735.pdf', isMinutes: false },
      { name: '配布資料3: 会社法制（株式・株主総会等関係）の見直しに関する中間試案 (PDF)', type: 'PDF', size: '1.8 MB', url: 'https://www.moj.go.jp/content/001464736.pdf', isMinutes: false },
      { name: '配布資料4: 会社法制（株式・株主総会等関係）の見直しに関する中間試案（概要） (PDF)', type: 'PDF', size: '750 KB', url: 'https://www.moj.go.jp/content/001464743.pdf', isMinutes: false },
      { name: '配布資料5: 会社法制（株式・株主総会等関係）の見直しに関する中間試案の補足説明 (PDF)', type: 'PDF', size: '1.2 MB', url: 'https://www.moj.go.jp/content/001464738.pdf', isMinutes: false },
      { name: '会議用資料: 法制審議会委員等名簿 (PDF)', type: 'PDF', size: '160 KB', url: 'https://www.moj.go.jp/content/001464739.pdf', isMinutes: false },
      { name: '第205回 会議議事録 (PDF版)', type: 'PDF', size: '420 KB', url: 'https://www.moj.go.jp/content/001466596.pdf', isMinutes: true },
      { name: '第205回 会議議事録 (TXT版)', type: 'TXT', size: '95 KB', url: 'https://www.moj.go.jp/content/001466595.txt', isMinutes: true },
      { name: '法制審議会第２０５回会議 開催ページ', type: 'HTML', size: '35 KB', url: 'https://www.moj.go.jp/shingi1/shingi03500044_00015.html', isMinutes: false }
    ],
    tags: ['法制審議会', '犯罪被害者支援', '会社法', '株主総会', '法務省'],
    officialUrl: 'https://www.moj.go.jp/shingi1/shingi03500044_00015.html',
    hasMinutes: true,
    docCount: 9
  },
  // 7. MOD
  {
    id: 'meet-mod-cho-shin-latest',
    councilId: 'mod-cho-shin',
    councilName: '防衛調達審議会',
    ministry: 'MOD',
    category: 'COUNCIL',
    title: '防衛調達審議会 令和8年度開催計画および審議事項',
    date: '2026-07-17',
    updatedAt: '2026-07-17 19:00',
    location: '防衛省 A棟',
    summary: '防衛装備品等の調達価格の適正化および契約変更適正審査について審議が行われ、令和8年度開催計画に基づき議事要旨が公開された。',
    agenda: [
      '令和8年度防衛調達審議会開催計画について',
      '防衛装備品等の契約変更および調達価格の適正性審査について'
    ],
    materials: [
      { name: '令和8年度防衛調達審議会開催計画 (PDF)', type: 'PDF', size: '150 KB', url: 'https://www.mod.go.jp/j/policy/agenda/meeting/cho-shin/giji/pdf/r08_keikaku.pdf', isMinutes: false },
      { name: '防衛調達審議会議事要旨 第198回 (PDF)', type: 'PDF', size: '280 KB', url: 'https://www.mod.go.jp/j/policy/agenda/meeting/cho-shin/giji/pdf/198.pdf', isMinutes: true },
      { name: '防衛調達審議会議事要旨 第197回 (PDF)', type: 'PDF', size: '260 KB', url: 'https://www.mod.go.jp/j/policy/agenda/meeting/cho-shin/giji/pdf/197.pdf', isMinutes: true },
      { name: '防衛調達審議会 公式ポータル', type: 'HTML', size: '35 KB', url: 'https://www.mod.go.jp/j/policy/agenda/meeting/cho-shin/index.html', isMinutes: false }
    ],
    tags: ['防衛調達審議会', '防衛装備品', '調達価格', '契約審査', '防衛省'],
    officialUrl: 'https://www.mod.go.jp/j/policy/agenda/meeting/cho-shin/index.html',
    hasMinutes: true,
    docCount: 4
  },
  {
    id: 'meet-mod-drastic-reinforcement-7th',
    councilId: 'mod-drastic-reinforcement',
    councilName: '防衛力の抜本的強化に関する有識者会議',
    ministry: 'MOD',
    category: 'PANEL',
    title: '防衛力の抜本的強化に関する有識者会議（第7回）',
    date: '2026-03-10',
    updatedAt: '2026-03-10 17:00',
    location: '防衛省 特別会議室',
    summary: '第7回会議が開催され、防衛力の抜本的強化の進捗、今後の課題、ならびに防衛基盤強化方策について報告・意見交換が行われた。',
    agenda: [
      '防衛力の抜本的強化に関する取り組み状況について',
      '第7回会議資料および議事要旨の確認'
    ],
    materials: [
      { name: '会議資料 (PDF)', type: 'PDF', size: '1.1 MB', url: 'https://www.mod.go.jp/j/policy/agenda/meeting/drastic-reinforcement/pdf/siryo07_01.pdf', isMinutes: false },
      { name: '議事要旨 (PDF)', type: 'PDF', size: '340 KB', url: 'https://www.mod.go.jp/j/policy/agenda/meeting/drastic-reinforcement/pdf/siryo07_02.pdf', isMinutes: true },
      { name: '防衛力の抜本的強化に関する有識者会議 公式ポータル', type: 'HTML', size: '35 KB', url: 'https://www.mod.go.jp/j/policy/agenda/meeting/drastic-reinforcement/index.html', isMinutes: false }
    ],
    tags: ['防衛力抜本強化', '有識者会議', '第7回', '安全保障戦略', '防衛省'],
    officialUrl: 'https://www.mod.go.jp/j/policy/agenda/meeting/drastic-reinforcement/index.html',
    hasMinutes: true,
    docCount: 3
  },
  {
    id: 'meet-mod-drastic-reinforcement-6th',
    councilId: 'mod-drastic-reinforcement',
    councilName: '防衛力の抜本的強化に関する有識者会議',
    ministry: 'MOD',
    category: 'PANEL',
    title: '防衛力の抜本的強化に関する有識者会議（第6回）',
    date: '2025-09-19',
    updatedAt: '2025-09-19 18:00',
    location: '防衛省 特別会議室',
    summary: '第6回会議が開催され、防衛力の抜本的強化に関する有識者会議報告書（提言の概要、報告書本編、議事要旨）が取りまとめられた。',
    agenda: [
      '「防衛力の抜本的強化に関する有識者会議」報告書について',
      '報告書による提言の概要および議事要旨のとりまとめ'
    ],
    materials: [
      { name: '会議資料１: 報告書による提言の概要 (PDF)', type: 'PDF', size: '850 KB', url: 'https://www.mod.go.jp/j/policy/agenda/meeting/drastic-reinforcement/pdf/siryo06_01.pdf', isMinutes: false },
      { name: '会議資料２: 「防衛力の抜本的強化に関する有識者会議」報告書 (PDF)', type: 'PDF', size: '2.4 MB', url: 'https://www.mod.go.jp/j/policy/agenda/meeting/drastic-reinforcement/pdf/siryo06_02.pdf', isMinutes: false },
      { name: '議事要旨 (PDF)', type: 'PDF', size: '360 KB', url: 'https://www.mod.go.jp/j/policy/agenda/meeting/drastic-reinforcement/pdf/siryo06_03.pdf', isMinutes: true },
      { name: 'Summary of Recommendations [ENG] (PDF)', type: 'PDF', size: '620 KB', url: 'https://www.mod.go.jp/j/policy/agenda/meeting/drastic-reinforcement/pdf/siryo06_01_en.pdf', isMinutes: false },
      { name: '開催要綱 (PDF)', type: 'PDF', size: '120 KB', url: 'https://www.mod.go.jp/j/policy/agenda/meeting/drastic-reinforcement/pdf/youkou-01.pdf', isMinutes: false },
      { name: '運営要領 (PDF)', type: 'PDF', size: '110 KB', url: 'https://www.mod.go.jp/j/policy/agenda/meeting/drastic-reinforcement/pdf/youryou-01.pdf', isMinutes: false },
      { name: '防衛力の抜本的強化に関する有識者会議 公式ポータル', type: 'HTML', size: '35 KB', url: 'https://www.mod.go.jp/j/policy/agenda/meeting/drastic-reinforcement/index.html', isMinutes: false }
    ],
    tags: ['防衛力抜本強化', '有識者会議', '第6回', '報告書', '防衛省'],
    officialUrl: 'https://www.mod.go.jp/j/policy/agenda/meeting/drastic-reinforcement/index.html',
    hasMinutes: true,
    docCount: 7
  },
  {
    id: 'meet-mod-defense-industry-wg-latest',
    councilId: 'mod-defense-industry-wg',
    councilName: '防衛産業ワーキンググループ',
    ministry: 'MOD',
    category: 'ROUNDTABLE',
    title: '防衛産業ワーキンググループ 第2回会議',
    date: '2026-06-20',
    updatedAt: '2026-06-20 16:30',
    location: '防衛省 会議室',
    summary: '防衛産業の基盤強化、装備品等のサプライチェーン維持および官民連携に関する事務局説明資料・議事要旨が協議された。',
    agenda: [
      '防衛産業ワーキンググループの開催および運営要領について',
      '防衛産業基盤育成とサプライチェーン強化に関する事務局説明'
    ],
    materials: [
      { name: '第2回 議事次第 (PDF)', type: 'PDF', size: '95 KB', url: 'https://www.mod.go.jp/j/policy/agenda/meeting/defense_industry_wg/pdf/giji_02.pdf', isMinutes: false },
      { name: '第2回 事務局説明資料 (PDF)', type: 'PDF', size: '1.6 MB', url: 'https://www.mod.go.jp/j/policy/agenda/meeting/defense_industry_wg/pdf/siryou02_01.pdf', isMinutes: false },
      { name: '第2回 議事要旨 (PDF)', type: 'PDF', size: '240 KB', url: 'https://www.mod.go.jp/j/policy/agenda/meeting/defense_industry_wg/pdf/giji_yoshi_02.pdf', isMinutes: true },
      { name: '資料1 防衛産業ワーキンググループの開催について (PDF)', type: 'PDF', size: '180 KB', url: 'https://www.mod.go.jp/j/policy/agenda/meeting/defense_industry_wg/pdf/siryou01_01.pdf', isMinutes: false },
      { name: '資料2 防衛産業ワーキンググループ運営 (PDF)', type: 'PDF', size: '150 KB', url: 'https://www.mod.go.jp/j/policy/agenda/meeting/defense_industry_wg/pdf/siryou01_02.pdf', isMinutes: false },
      { name: '防衛産業ワーキンググループ 公式ポータル', type: 'HTML', size: '35 KB', url: 'https://www.mod.go.jp/j/policy/agenda/meeting/defense_industry_wg/index.html', isMinutes: false }
    ],
    tags: ['防衛産業WG', '官民連携', 'サプライチェーン', '防衛生産基盤', '防衛省'],
    officialUrl: 'https://www.mod.go.jp/j/policy/agenda/meeting/defense_industry_wg/index.html',
    hasMinutes: true,
    docCount: 6
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
      { name: '食料・農業・農村政策審議会 公式ポータル', type: 'HTML', size: '35 KB', url: 'https://www.maff.go.jp/j/council/seisaku/', isMinutes: false }
    ],
    tags: ['農林水産', '食料安全保障', 'スマート農業', '食料基本法', '環境'],
    officialUrl: 'https://www.maff.go.jp/j/council/seisaku/',
    hasMinutes: true,
    docCount: 1
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
      { name: '社会資本整備審議会 公式ポータル', type: 'HTML', size: '35 KB', url: 'https://www.mlit.go.jp/policy/shingikai/index.html', isMinutes: false }
    ],
    tags: ['国土交通', '自動運転', 'インフラ', '国土強靱化', '高速道路'],
    officialUrl: 'https://www.mlit.go.jp/policy/shingikai/index.html',
    hasMinutes: true,
    docCount: 1
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
      { name: '警察庁 サイバー攻撃対策 公式ポータル', type: 'HTML', size: '35 KB', url: 'https://www.npa.go.jp/bureau/cyber/index.html', isMinutes: false }
    ],
    tags: ['警察庁', 'サイバーセキュリティ', 'ランサムウェア', 'ディープフェイク', '捜査'],
    officialUrl: 'https://www.npa.go.jp/bureau/cyber/index.html',
    hasMinutes: true,
    docCount: 1
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
      { name: '原子力規制委員会 公式ポータル', type: 'HTML', size: '35 KB', url: 'https://www.nra.go.jp/index.html', isMinutes: false }
    ],
    tags: ['原子力', '安全審査', 'SMR', 'エネルギー', '規制'],
    officialUrl: 'https://www.nra.go.jp/index.html',
    hasMinutes: true,
    docCount: 1
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
      { name: '外務省 外交政策 公式ポータル', type: 'HTML', size: '35 KB', url: 'https://www.mofa.go.jp/mofaj/index.html', isMinutes: false }
    ],
    tags: ['外交', '経済安全保障', 'FOIP', 'ODA', '外務省'],
    officialUrl: 'https://www.mofa.go.jp/mofaj/index.html',
    hasMinutes: true,
    docCount: 1
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
      { name: '復興推進委員会 公式ポータル', type: 'HTML', size: '35 KB', url: 'https://www.reconstruction.go.jp/topics/cat-11/cat-47/cat-155/cat-156/000813/', isMinutes: false }
    ],
    tags: ['復興', '福島', 'FIREC', '防災', '復興庁'],
    officialUrl: 'https://www.reconstruction.go.jp/topics/cat-11/cat-47/cat-155/cat-156/000813/',
    hasMinutes: true,
    docCount: 1
  },
  // 14. CAS & User Requested Council Meetings
  {
    id: 'meet-2025-0623-zensedai',
    councilId: 'cas-zensedai-hosyo',
    councilName: '全世代型社会保障構築会議',
    ministry: 'CAS',
    category: 'PANEL',
    title: '第21回 全世代型社会保障構築会議',
    date: '2025-06-23',
    updatedAt: '2025-06-23 17:00',
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
    id: 'meet-2026-0710-aihq',
    councilId: 'cao-ai-hq',
    councilName: '人工知能戦略本部',
    ministry: 'CAO',
    category: 'COUNCIL',
    title: '第5回 人工知能戦略本部 会議',
    date: '2026-07-10',
    updatedAt: '2026-07-10 16:30',
    location: '内閣府 講堂（中央合同庁舎第8号館）',
    summary: '人工知能基本計画（案）およびバーティカルＡＩ領域別戦略の中間とりまとめ案が提示され、各省庁連携によるAI社会実装方針が決定した。',
    agenda: [
      '人工知能基本計画（案）の審議および決定',
      'バーティカルＡＩ領域別戦略 中間とりまとめ報告',
      '我が国におけるAIインフラ整備および安全評価体制の強化'
    ],
    materials: [
      { name: '資料1-1: 人工知能基本計画（案）の概要 (PDF / 576KB)', type: 'PDF', size: '576 KB', url: 'https://www8.cao.go.jp/cstp/ai/ai_hq/5kai/shiryo1_1.pdf', isMinutes: false },
      { name: '資料1-2: 人工知能基本計画（案） (PDF / 609KB)', type: 'PDF', size: '609 KB', url: 'https://www8.cao.go.jp/cstp/ai/ai_hq/5kai/shiryo1_2.pdf', isMinutes: false },
      { name: '資料2-1: バーティカルＡＩ領域別戦略 中間とりまとめの概要 (PDF / 422KB)', type: 'PDF', size: '422 KB', url: 'https://www8.cao.go.jp/cstp/ai/ai_hq/5kai/shiryo2_1.pdf', isMinutes: false },
      { name: '資料2-2: バーティカルＡＩ領域別戦略 中間とりまとめ (PDF / 1,332KB)', type: 'PDF', size: '1,332 KB', url: 'https://www8.cao.go.jp/cstp/ai/ai_hq/5kai/shiryo2_2.pdf', isMinutes: false },
      { name: '第5回 人工知能戦略本部 会議公式ページ', type: 'HTML', size: '35 KB', url: 'https://www8.cao.go.jp/cstp/ai/ai_hq/5kai/5kai.html', isMinutes: false }
    ],
    tags: ['AI', '人工知能戦略本部', '基本計画', 'バーティカルAI', '内閣府'],
    officialUrl: 'https://www8.cao.go.jp/cstp/ai/ai_hq/5kai/5kai.html',
    hasMinutes: true,
    docCount: 5
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
