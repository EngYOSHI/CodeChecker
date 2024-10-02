# 使い方
1. コンパイラであるmingw-w64のバイナリをダウンロードする  
https://github.com/niXman/mingw-builds-binaries/releases/latest
2. ダウンロードした圧縮ファイルを，`CodeChecker\mingw64\`に展開する  
このとき，`CodeChecker\mingw64\`フォルダ配下に`bin`, `include`フォルダなどが配置されるようにすること
3. `CodeChecker\src\`フォルダを作成し，その中に1授業回分のソースコードを入れる  
4. `CodeChecker\work\`フォルダを作成する  
実行ファイルが読み込むファイルがある場合は，このフォルダに入れる
5. `CodeChecker\student_list.txt`ファイルを作成し，採点対象の学籍番号を1行に一名分入れる
6. `CodeChecker\task_list.txt`ファイルを作成し，この授業回の課題番号を1行に1つ入れる  
課題番号は`1-1a`や`1-A1`といったもの
7. スクリプトを実行する  
```
python main.py
```