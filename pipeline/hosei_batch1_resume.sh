#!/bin/bash
set -e
cd /home/user/work/LEXA/pipeline
R=/root/.claude/projects/-home-user/85c9d7ac-55a7-53f9-8108-6da8233f1eeb/tool-results
declare -A files=(
["1788760739048"]=2007
["1788760748374"]=2008
["1788760774277"]=2010
["1788760782526"]=2010
["1788760787904"]=2011
["1788760788869"]=2011
["1788760790458"]=2011
["1788760800149"]=2011
["1788760804397"]=2011
["1788760804721"]=2011
)
for ts in "${!files[@]}"; do
  yr=${files[$ts]}
  python3 06_process_exam_file.py --tool-result "$R/mcp-Google_Drive-download_file_content-$ts.txt" --university "法政大学" --year "$yr" --lemma-list data/processed/lemma_list.txt --agg-out data/interim/exam_freq_march.json
done
echo HOSEI_BATCH1_RESUME_DONE
