# STEP5 target_relevance 判定ルーブリック (v1)

STEP5判定バッチが `university_groups.<group>.relevance` を決める際の出発点。
完全な機械的閾値ではなく、STEP4-2 sense情報・reference_book情報を踏まえた
最終調整を許容するが、閾値から外れる場合は必ず reason に理由を書く。

対象は `step5_word_facts_v2.json` の各 lemma × group エントリ
（frequency>0 のグループのみ存在）。

## 入力事実（AIは再計算しない。事実は必ずこのファイルから転記する）
- `frequency`: このグループ内での総出現数
- `group_freq_percentile`: 同グループ内の全候補語に対するfrequencyの百分位
- `university_coverage_ratio`: 出現大学数 / グループ内総大学数
- `concentration_ratio`: 最頻出1大学が占める割合（1.0=1校に集中、低い=広く分散）

## 判定ロジック（出発点）

1. **HIGH**: `group_freq_percentile >= 70` かつ `university_coverage_ratio >= 0.75`
   かつ `concentration_ratio <= 0.6`
   → 「そのグループの多くの大学で、かつ高頻度に」出現 = グループ全体で重要

2. **MEDIUM**: 以下のいずれか
   - `group_freq_percentile >= 50` かつ `university_coverage_ratio >= 0.5`
   - `group_freq_percentile >= 85`（かなり高頻度だが coverage が低い＝特定大学偏重の可能性）
     → この場合は「グループ全体」というより「グループ内の特定大学」向けの
     TARGET候補である旨をreasonに明記する

3. **LOW**: 上記のいずれにも該当しない（出現はするが希薄）

4. **例外調整（AIが閾値から外れてよいケース、reason必須）**:
   - `concentration_ratio >= 0.8` の場合、たとえHIGH閾値を満たしても
     「特定大学集中型」である旨を明記し、relevanceをMEDIUMに落とすか、
     `final_role`側でTARGET寄りの判断材料として使う
   - STEP4-2で該当グループの過去問からexam_observedな根拠が得られているsenseは、
     頻度が閾値未満でも relevance を1段階引き上げてよい（reasonに明記）
   - `common_test=not_observed` は関連なし（除外理由にしない。ルール6参照）

## 適用しないこと
- グループ間の相対比較で「これは早慶よりMARCHの方が重要」のような
  ランキングは作らない（用途はグループごとの独立判定）
- 大学別(university_frequency)の個別relevanceはSTEP5-v1では生成しない
  （学部データがなく大学単体の教育的意味付けが弱いため）。ただし
  `per_university_frequency`は事実としてそのまま保持し、将来大学単位の
  relevance生成に使えるようにする。

## reference_coverage の閾値（v2で追加、Tier Bパイロットの指摘を受けて明文化）
`book_count`（在籍する参考書の冊数、7冊中）を以下で判定する。
- `FULLY_COVERED`: book_count >= 3
- `PARTIALLY_COVERED`: book_count == 1 または 2
- `NOT_COVERED`: book_count == 0
- `UNCERTAIN`: 上記に当てはまらない特殊ケース（基本的に発生しない想定）
この閾値はSTEP4-2済み語・未済み語の両方に共通して適用する。

## final_role 集約ロジック（v2で追加、Tier B用の明示的な集約式）
sense単位評価がない（Tier B）場合、lemma単位のfinal_roleは以下の優先順位で決定する。
1. `is_function_word` / `is_noise_fragment` / `is_phrase` のいずれかがtrue
   → `EXCLUDE_FROM_LEARNING`（他の基準より優先）
2. 以下の「広範重要」条件を**すべて**満たす → `CORE`
   - `total_frequency`が候補母集団の上位1割程度に相当する高水準
   - `university_count`が26,737語population全体で見て極めて高い（目安：25以上）
   - 出現する大学群のうち過半数で`relevance=HIGH`
   - 事実が強く一貫している（`confidence: high`を正当化できる）
3. 2に届かないが、出現する大学群のうち相当数（目安：半数以上）で
   `relevance=HIGH`または`MEDIUM` → `IMPORTANT`
4. 特定の1〜2大学群のみで`relevance=HIGH`、または`concentration_ratio>=0.8`の
   集中パターンが見られる → `TARGET`
5. 大学群のrelevanceがおおむね`LOW`〜`MEDIUM`混在で、決め手となる強いシグナルが
   ない（Tier Bでsense情報がなく判断材料が薄いケースを含む） → `CONTEXT`
6. `total_frequency`が極端に低い（目安：5以下）、出現大学数が1〜2校のみで
   継続的出現とは言えない → `ARCHIVE`
この優先順位はあくまで出発点であり、事実が強く矛盾する場合は`reason`に
明記した上で調整してよい（機械的閾値だけに縛られる必要はない、という
STEP5全体の方針は維持する）。

## 固有名詞・不明語の扱い（v2で追加）
Tier Bでは大量の未知語・固有名詞候補が出現しうる。sense分析がないため
断定的な判断はできないが、以下の優先順位で扱う。
1. 明らかな固有名詞（地名・人名として一般常識で判断できる、例: Brazil, John）
   → `learner_category: proper_noun`, `final_role: EXCLUDE_FROM_LEARNING`
2. 実在するが特定困難、またはOCR起因の疑いはあるが`is_noise_fragment`が
   upstreamでfalseのため断定できない語 → `learner_category: other`,
   `confidence: low`とし、`reason`に疑念を明記した上で`final_role`は
   通常のfact-basedロジック（上記集約ロジック）に従って決定する
   （`ocr_fragment`と断定しない — sense根拠なしにその診断はできない）
3. 完全に判別不能な文字列 → `learner_category: other`, `final_role: ARCHIVE`,
   `confidence: low`とし、`reason`に判別不能である旨を明記する
