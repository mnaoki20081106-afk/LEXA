#!/bin/bash
set -e
cd /home/user/work/LEXA/pipeline
R=/root/.claude/projects/-home-user/85c9d7ac-55a7-53f9-8108-6da8233f1eeb/tool-results
declare -A files=(
["1788743120172"]=2007 ["1788743120511"]=2007 ["1788743121852"]=2007 ["1788743122454"]=2007 ["1788743123229"]=2007 ["1788743124155"]=2007 ["1788743124560"]=2007 ["1788743125607"]=2007
["1788743125337"]=2008 ["1788743126290"]=2008 ["1788743127101"]=2008 ["1788743127408"]=2008 ["1788743157153"]=2008 ["1788743157919"]=2008 ["1788743161122"]=2008
["1788743162858"]=2009 ["1788743199514"]=2009 ["1788743199384"]=2009 ["1788743199308"]=2009 ["1788743170277"]=2009 ["1788743168147"]=2009 ["1788743170408"]=2009
)
for ts in "${!files[@]}"; do
  yr=${files[$ts]}
  python3 06_process_exam_file.py --tool-result "$R/mcp-Google_Drive-download_file_content-$ts.txt" --university "青山学院大学" --year "$yr" --lemma-list data/processed/lemma_list.txt --agg-out data/interim/exam_freq_march.json
done
echo AOYAMA_BATCH1_DONE
