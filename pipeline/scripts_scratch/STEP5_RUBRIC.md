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
