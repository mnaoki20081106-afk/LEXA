#!/bin/bash
set -e
cd /home/user/work/LEXA/pipeline
R=/root/.claude/projects/-home-user/85c9d7ac-55a7-53f9-8108-6da8233f1eeb/tool-results
declare -A files=(
["1788706551285"]=2007 ["1788706552285"]=2007 ["1788706553625"]=2007 ["1788706554828"]=2007 ["1788706555622"]=2007
["1788706557495"]=2009 ["1788706558685"]=2009 ["1788706559713"]=2009 ["1788706734213"]=2009 ["1788706734493"]=2009
["1788706655477"]=2010 ["1788706657094"]=2010 ["1788706657742"]=2010 ["1788706658721"]=2010 ["1788706662246"]=2010
["1788706660905"]=2011 ["1788706661636"]=2011 ["1788706661865"]=2011 ["1788706677458"]=2011 ["1788706678847"]=2011
["1788706678241"]=2012 ["1788706679026"]=2012 ["1788706679880"]=2012 ["1788706682469"]=2012 ["1788706683222"]=2012
)
for ts in "${!files[@]}"; do
  yr=${files[$ts]}
  python3 06_process_exam_file.py --tool-result "$R/mcp-Google_Drive-download_file_content-$ts.txt" --university "駒澤大学" --year "$yr" --lemma-list data/processed/lemma_list.txt --agg-out data/interim/exam_freq_nittokomasen.json
done
echo KOMAZAWA_ALL_DONE
