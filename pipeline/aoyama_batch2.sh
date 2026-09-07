#!/bin/bash
set -e
cd /home/user/work/LEXA/pipeline
R=/root/.claude/projects/-home-user/85c9d7ac-55a7-53f9-8108-6da8233f1eeb/tool-results
declare -A files=(
["1788743952682"]=2010
["1788743954446"]=2011 ["1788743955097"]=2011 ["1788743955896"]=2011 ["1788743956966"]=2011 ["1788743958352"]=2011 ["1788743960176"]=2011 ["1788743961204"]=2011 ["1788743961950"]=2011
["1788743967663"]=2012 ["1788743969021"]=2012 ["1788743970486"]=2012 ["1788743971072"]=2012 ["1788743971810"]=2012 ["1788743973204"]=2012 ["1788743974207"]=2012 ["1788743974813"]=2012
)
for ts in "${!files[@]}"; do
  yr=${files[$ts]}
  python3 06_process_exam_file.py --tool-result "$R/mcp-Google_Drive-download_file_content-$ts.txt" --university "青山学院大学" --year "$yr" --lemma-list data/processed/lemma_list.txt --agg-out data/interim/exam_freq_march.json
done
echo AOYAMA_BATCH2_DONE
