@chcp 1251 >nul
"C:\Program Files\Python310\python.exe" ^
  ontology_highlighter.py ^
  "D:\Projects\Python\MachLearning\NornickelHackathon\docs_db\ЦП_ПГР\source\Доклады\Преза Рудник 2025.md" ^
  --out-dir "texts2_investigations" ^
  --domains "common,underground_mining"
@rem copy tmp/highlight/highlighted_entities.html


"C:\Program Files\Python310\python.exe" ^
  ontology_highlighter.py ^
  "D:\Projects\Python\MachLearning\NornickelHackathon\docs_db\ЦП_ПГР\source\Доклады\НДС Комсомольский.md" ^
  --out-dir "texts_investigations" ^
  --domains "common,underground_mining"

