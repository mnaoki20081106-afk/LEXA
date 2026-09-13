# STEP5 target_relevance 判定ルーブリック (v3)

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

## reference_coverage の閾値（v3で修正、LOのフィードバックを反映）
`book_count`（対象7冊中、lemmaそのものが掲載されている冊数）を以下で判定する。
- `FULLY_COVERED`: book_count == 7（7冊すべてに掲載）
- `PARTIALLY_COVERED`: book_count が 1〜6（一部の参考書にのみ掲載）
- `NOT_COVERED`: book_count == 0（どの参考書にも掲載なし）
- `UNCERTAIN`: 上記いずれにも該当しない特殊ケース（book_countデータが欠損・矛盾している
  場合のみ。通常は発生しない）

【重要】reference_coverageは「lemmaそのものが参考書に掲載されているか」という
事実ベースの指標であり、「その語の入試上重要なsenseまで参考書でカバーされているか」とは
明確に区別すること。
- Tier A（STEP4-2でsense分析済み）: sense単位のevidence_type/usage_typeを参照し、
  「参考書掲載senseと入試で重要なsenseに差がある」場合はlexa_added_value等の根拠として
  明示的に使ってよい（ただしreference_coverage自体の値は変えない — あくまでlemma掲載の
  事実のまま）。
- Tier B（sense分析未実施）: sense単位のカバレッジは一切推測しない。reference_coverageは
  book_countのみに基づく事実として扱い、reasonにも「sense単位の参考書カバレッジは不明」と
  明記すること。

## final_role 集約ロジック（v3で全面改訂、単純な「特定大学群HIGH→自動CORE」を廃止）

STEP5では以下の4つの評価軸を明確に分離する。これらを混同してはならない。
1. **university-group relevance**（`target_relevance.university_groups.<group>.relevance`）:
   各大学群「内」での必要性（HIGH/MEDIUM/LOW）。あくまで個々の大学群単位の判定。
2. **exam_necessity**: lemma全体として、入試という文脈でどれだけ必要とされているか
   （HIGH/MEDIUM/LOW）。特定の大学群だけでなく、複数大学群にまたがる出現パターン全体から
   判断する、lemma単位の集約評価。
3. **overall_learning_value**: LEXAの学習者にとって、この語を学習対象として提示する価値が
   どれだけあるか（HIGH/MEDIUM/LOW）。exam_necessityが高くても、語彙としての性質
   （固有名詞疑い、不明語、OCR疑いなど）によって独立に下がりうる。
4. **final_role**: 上記1〜3を総合した、LEXA上での最終的な扱い
   （CORE/IMPORTANT/TARGET/CONTEXT/ARCHIVE/EXCLUDE_FROM_LEARNING）。

final_roleは「1つの大学群がHIGHだから自動的に上位roleにする」という単純な機械的ルールに
してはならない。以下の基準を出発点とし、根拠をreasonに明記した上で判断する。

### EXCLUDE_FROM_LEARNING（他の基準より優先）
- `is_function_word` / `is_noise_fragment` / `is_phrase` のいずれかが upstream で true、
  または
- `learner_category = proper_noun`（一般常識で明らかに固有名詞と判断できる場合のみ。
  下記「learner_category」セクション参照）
のいずれかに該当する場合のみ。頻度や大学群での重要性に関わらず優先的にこの扱いとする。

### CORE（全国的に広く必要な語 — 厳格な基準、乱発しない）
以下を **すべて** 満たす場合のみ:
- `exam_necessity = HIGH`（複数大学群にまたがる一貫した高頻度・高カバレッジ。
  1つの大学群だけがHIGHでも他が軒並みLOW/データなしならHIGHにしない）
- 出現する大学群のうち**過半数**で`relevance = HIGH`（特定1〜2グループの偏りではない）
- `overall_learning_value = HIGH`
- 事実が一貫しており、`confidence: high`を正当化できる
「全国的に必要な語」「幅広い大学群で必要な語」はこの区分に該当する。

### IMPORTANT（広範囲だがCOREほど圧倒的ではない語）
CORE の基準に届かないが、以下のいずれかを満たす:
- 出現する大学群のうち相当数（目安：半数程度）で`relevance = HIGH`または`MEDIUM`
- `exam_necessity = MEDIUM`以上で、特定1〜2グループへの極端な偏りがない
「幅広い大学群で必要だが、CORE認定するほどの圧倒的な事実はまだない語」がここに入る。

### TARGET（特定大学群に強く必要な語 — 集中型）
以下のような「広くはないが特定文脈で強い」パターン:
- 出現する大学群の**一部（1〜2グループ）でのみ**`relevance = HIGH`、かつ他グループでは
  データが薄い/存在しない、または
- `concentration_ratio`が高く（目安0.8以上）、かつ意味のある頻度（目安：総頻度6以上。
  単発出現（total_frequency=1程度）で機械的に concentration_ratio=1.0 になるだけの
  ケースは「集中パターン」に含めない）がある場合
「特定大学群に強く必要な語」「頻度は低いが特定大学で意味がある語」はここに入る。
exam_necessityはLOW〜MEDIUMでも構わない（全国的な必要性は低くても、特定ターゲット校を
選ぶ学習者には重要、というLEXAの目的に合致するroleのため）。

### CONTEXT（弱い/混在シグナル — デフォルトの保守的区分）
- 大学群のrelevanceがおおむねLOW〜MEDIUM混在で、CORE/IMPORTANT/TARGETいずれの
  明確なパターンにも該当しない
- `learner_category = uncertain_lexical_item`で、事実（頻度・大学数）が「ゼロではないが
  弱い」場合のデフォルト
「入試には出現するが通常学習対象としての優先度が低い語」のうち、完全に無視はできない
程度の事実がある場合はここに入れる（ARCHIVEほど切り捨てない）。

### ARCHIVE（事実が乏しい/不明で保守的に据え置く語）
以下のいずれか:
- `total_frequency`が極めて低い（目安5以下）かつ`university_count`が1〜2校のみ
- `learner_category = likely_ocr_artifact`（upstream `is_noise_fragment=true`で
  裏付けがある場合のみ。裏付けなしにここへ誘導しない）
- `learner_category = uncertain_lexical_item`で、かつ事実自体もほぼ存在しない
  （データが乏しすぎて判断材料がない）
これは「不要語だから除外」ではなく、「現時点の事実からは能動的な学習対象と判断できない
ため、保守的に保持する」という扱いである。EXCLUDE_FROM_LEARNINGとは異なり、将来的な
再評価（sense分析の追加など）で昇格しうる可能性を閉じない。

上記はあくまで出発点であり、事実が強く矛盾する場合はreasonに明記した上で調整してよい。
ただし「1グループHIGHだから自動的にCORE」のような単一シグナルへの安易な昇格は禁止する。

## learner_category: 固有名詞・不明語・OCR疑いの扱い（v3で全面改訂）

Tier B（21,539語、sense分析未実施）では大量の未知語・固有名詞候補・OCR起因の疑いのある
文字列が出現しうる。これらを根拠なく機械的に不要語・除外語と判断してはならない。

`learner_category`は以下の4値のいずれかを取る。

1. **known_lexical_item**: 実在する英単語として確信を持って識別できる語
   （基本語・専門語・古語・口語問わず、識別に疑いがない場合）。
2. **proper_noun**: 一般常識で明らかに固有名詞と判断できる語で、実用的な普通名詞としての
   用法がほぼない場合（例：Brazil, John のような明白なケース）。判断に迷う場合
   （普通名詞の用法も現実的にありうる語）はこちらに分類しない。
3. **uncertain_lexical_item**: 実在する語である可能性はあるが、identity（綴り・語源・
   用法）を確信を持って断定できない語。OCR起因の疑いがあっても upstream の
   `is_noise_fragment` が false の場合は、これに分類する（下記4は使わない）。
4. **likely_ocr_artifact**: upstream の `is_noise_fragment = true` という機械的事実で
   裏付けられている場合 **のみ** 使用する。この事実的裏付けがない限り、どれほど
   文字列が不自然に見えても`likely_ocr_artifact`と断定してはならない。

【禁止事項】
- 「知らない語だから不要語」という推測により`uncertain_lexical_item`や
  `likely_ocr_artifact`を`final_role: EXCLUDE_FROM_LEARNING`に直結させることは禁止。
  最終的なfinal_roleは通常のfinal_role集約ロジック（上記セクション）に従って
  事実ベースで決定し、`uncertain_lexical_item`は基本的にCONTEXT/ARCHIVEなど保守的な
  roleに倒すが、EXCLUDE_FROM_LEARNINGにはしない（proper_nounの確信がある場合を除く）。
- 「頻度が低いからOCRだろう」という推測でlearner_categoryを`likely_ocr_artifact`と
  判定することは禁止。この判定は必ずupstreamの`is_noise_fragment`フラグという
  既存の機械判定結果を事実として優先し、それに基づいてのみ行う。
- 判断に十分な根拠がない場合は、無理に`known_lexical_item`や`proper_noun`に
  分類せず、`uncertain_lexical_item`として「不明」であることを明示的に保持する。
  この場合、confidenceは`low`とし、reasonにその旨を明記する。

## confidenceの扱い（v3で新規追加、明文化）

`analysis_tier`（Tier A / Tier B）と`confidence`は独立した軸であり、機械的に
1対1対応させてはならない。

- Tier B（sense分析未実施）であっても、lemma単位の事実（総頻度・大学数・大学群
  カバレッジの一貫性など）が十分強く一貫していれば、`confidence: high`を
  つけてよい。「Tier Bだから最大でもmedium」という機械的な上限キャップは禁止。
- ただし、tierに関わらず、以下のような **sense単位の断定** は常に禁止:
  - 「この語のこの意味が重要である」
  - 「入試ではこの語のこのsenseが必要とされる」
  Tier Bではsense分析自体が存在しないため、このような断定は原理的に不可能。
  Tier Aであっても、STEP4-2のsense分析で裏付けられていない断定は禁止。
- lemma単位の事実に基づく確信度（confidence）と、sense単位の意味論的な断定は
  完全に別の話である、という区別を常にreasonの記述でも明確にすること。
