import subprocess
import os
import re
import pprint
import difflib
import argparse
import shutil

import common as c
import xl

srclist = []


def main():
    students = c.file2list(os.path.join(c.CASE_PATH, "students.txt"))
    print("学生数: " + str(len(students)))
    c.debug(str(students))
    tasks = read_taskfiles(os.path.join(c.CASE_PATH, "tasks.txt"))
    print("課題数: " + str(len(tasks)))
    tasks = read_casefiles(tasks)
    c.debug(pprint.pformat(tasks, sort_dicts=False))
    src_listgen()
    print("ソースファイル数: " + str(len(srclist)))
    c.debug(str(srclist))
    res = eval_loop(students, tasks)
    del_temp()  # tempフォルダを削除
    #pprint.pprint(res, sort_dicts=False)
    print("未処理のファイル数: " + str(len(srclist)))
    print("結果をxlsxファイルに書き込み中...")
    xl.write_xl(res)
    write_untouched()


def write_untouched():
    with open(os.path.join(c.RESULT_PATH, "untouched.txt"), 'w') as f:
        for x in srclist:
            f.write(x + "\n")


def eval_loop(students, tasks):
    res = []
    for i, s in enumerate(students):
        res_student = []
        for t in tasks:
            r = eval(s, t)
            res_student += [r]
        res += [{"student":s, "result":res_student}]
        if c.PRINT_SCORE:
            progress = f"({i + 1}/{len(students)})"
            print_score(s, res_student, progress)
    return res


def eval(student, task):
    r = {"task":task["name"], "compile":None, "run":None}
    exe = f"{student}_{task["name"]}"
    c.debug("\n")
    c.debug(exe, "eval")
    c.debug("----------------------")
    src = get_latest_src(student, task["name"])
    c.debug(src, "srcfile")
    # コンパイル
    temp_reset()  # Tempフォルダの初期化
    r["compile"] = compile(src, exe)
    c.debug(str(r["compile"]), "compile")
    if r["compile"]["result"]:
        # コンパイル成功ならテスト実行
        r["run"] = run_loop(exe + ".exe", task)
        c.debug("", "run_loop")
        c.debug(pprint.pformat(r["run"], sort_dicts=False))
        mv_temp2bin(exe + ".exe")  # 実行が終わったバイナリはbinフォルダへ移動
    return r


def get_latest_src(student, taskname):
    #命名条件に合致するファイルが一つもなければNoneを返す
    #命名条件に合致するファイルがあれば，評価対象のファイル名を返す
    global srclist
    r = student + "_" + taskname + r"(\([1-9][0-9]*\))?" + ".c"
    src = [x for x in srclist if re.match(r, x)]
    #命名条件に合致するファイルが一つもない -> None
    if len(src) == 0:
        return None
    #チェックしたファイルをソースファイルリストから削除する
    for s in src:
        srclist.remove(s)
    #チェックすべきソースファイルを識別
    #最新の提出物は，拡張子の前に番号が「付かない」，ピュアなファイル名のもの
    return f"{student}_{taskname}.c"


def compile(src, exe):
    res = {"result":True, "reason":None, "stdout":None}
    if src is None:
        res["result"] = False
        res["reason"] = "未提出orﾌｧｲﾙ名間違い"
        return res
    src_abs = os.path.join(os.path.abspath(c.SRC_PATH), src)
    exe_abs = os.path.join(os.path.abspath(c.TEMP_PATH), exe)
    cmd = ["gcc.exe", src_abs, "-o", exe_abs]
    r = subprocess.run(cmd, cwd=c.GCC_PATH, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,shell=True)
    (stdout_str, stdout_encode) = c.byte2str(r.stdout)
    c.debug(f"Encode of stdout: {stdout_encode}", "compile")
    res["stdout"] = stdout_str
    if r.returncode != 0:
        #コンパイル失敗
        res["result"] = False
        res["reason"] = "コンパイルエラー"
        if res["stdout"] is None:
            res["reason"] += " + 未サポートｴﾝｺｰﾄﾞ"
    return res


def run_loop(exe, task):
    res = []
    for case_num, case in enumerate(task["case"], start = 0):
        res += [run_exe(exe, case_num, case)]
    return res


def run_exe(exe, case_num, case):
    cmd = exe
    if case["arg"] is not None:
        c.debug(case["arg"], "arg")
        cmd = cmd + " " + case["arg"]
    res = {"result":None, "reason":None, "output":None, "ratio":None}
    proc = subprocess.Popen(cmd, cwd=c.TEMP_PATH, stdout=subprocess.PIPE, stdin=subprocess.PIPE, shell=True)
    try:
        if case["in"] is None:
            r = proc.communicate(timeout=c.TIMEOUT)
        else:
            r = proc.communicate(timeout=c.TIMEOUT, input=case["in"].encode("cp932"))
    except subprocess.TimeoutExpired:
        #タイムアウト
        proc.kill()
        c.debug("Time Out.", "run")
        res["result"] = False
        res["reason"] = "タイムアウト"
        return res
    (stdout_str, stdout_encode) = c.byte2str(r[0])  #標準出力のバイトストリームを文字列に変換
    c.debug(f"Encode of stdout[{case_num}]: {stdout_encode}", "run_exe")
    res["output"] = stdout_str
    if case["out"] is not None:
        if res["output"] is None:
            res["result"] = False
            res["reason"] = "未サポートｴﾝｺｰﾄﾞ"
            return res
        res["ratio"] = round(difflib.SequenceMatcher(None, res["output"], case["out"], False).ratio(), 3)
        if res["output"] == case["out"]:
            res["result"] = True
        else:
            res["reason"] = "ﾃｽﾄｹｰｽと不一致"
            res["result"] = False
    return res


def print_score(s, res_student, progress):
    output = "Student No.: " + s + "   " + progress
    for r in res_student:
        output += "\n\tTask: " + r["task"]
        output += "\n\t\tCompile: " + bool2str(r["compile"]["result"], "OK", "NG")
        if r["compile"]["result"]:
            correct = 0
            failed = 0
            skip = 0
            for i in range(len(r["run"])):
                output += "\n\t\t[" + str(i) + "] -> Result: " + bool2str(r["run"][i]["result"], "OK", "NG", "SKIP")
                if r["run"][i]["result"] is None:
                    skip += 1
                elif r["run"][i]["result"] == True:
                    correct += 1
                else:
                    failed += 1
                    if r["run"][i]["reason"] is not None:
                        output += f" (Reason: {r['run'][i]['reason']})"
                    if r["run"][i]["ratio"] is not None:
                        output += f" (Ratio: {r['run'][i]['ratio']})"
            output += f"\n\t\tSummary: {correct}/{correct + failed}  (skip:{skip})"
        else:
            output += " (" + r["compile"]["reason"] + ")"
    print(output + "\n")


def mv_temp2bin(exe):
    """exeをtempからresult\binに移動
    
    既に存在する場合は上書き
    """
    bin_path = os.path.join(c.RESULT_PATH, "bin\\")
    if not os.path.isdir(bin_path):
        os.mkdir(bin_path)
    mv_from = os.path.join(c.TEMP_PATH, exe)
    mv_to = os.path.join(bin_path, exe)
    c.debug(f"{mv_from} -> {mv_to}", "mv_temp2bin")
    shutil.move(mv_from, mv_to)


def del_temp():
    """一時保存フォルダ(temp)がある場合削除する"""
    if os.path.isdir(c.TEMP_PATH):
        shutil.rmtree(c.TEMP_PATH)


def temp_reset():
    """一時保存フォルダ(temp)を初期化する
    
    一時保存フォルダが存在する場合はフォルダごと消す
    その後，workフォルダをtempフォルダとしてコピー
    """
    del_temp()
    c.debug(f"Copying working files: {c.WORK_PATH} -> {c.TEMP_PATH}", "temp_reset")
    shutil.copytree(c.WORK_PATH, c.TEMP_PATH)


def chkpath():
    if not os.path.isdir(c.GCC_PATH):
        c.error(f"コンパイラがないか，正しく配置されていません．({c.GCC_PATH})")
    if not os.path.isdir(c.SRC_PATH):
        c.error(f"ソースファイルの格納先({c.SRC_PATH})がありません．")
    if not os.path.isdir(c.WORK_PATH):
        c.error(f"読み込ませるファイルの格納先({c.WORK_PATH})がありません．")
    if not os.path.isfile(os.path.join(c.CASE_PATH, "students.txt")):
        c.error(f"学籍番号ファイル'students.txt'が{c.CASE_PATH}にありません．")
    if not os.path.isfile(os.path.join(c.CASE_PATH, "tasks.txt")):
        c.error(f"タスクファイル'tasks.txt'が{c.CASE_PATH}にありません．")
    if not os.path.isdir(c.RESULT_PATH):
        c.error(f"結果ファイルの格納先({c.RESULT_PATH})がありません．")


def read_taskfiles(filename):
    l = c.file2list(filename)
    for i in range(len(l)):
        if re.fullmatch(r'[1-9][0-9]*-((A[1-9])|([1-9][a-z]*)) [1-9]', l[i]):
            temp = l[i].split(" ")
            l[i] = {"name" : temp[0], "count" : int(temp[1]), "case" : []}
        else:
            c.error("'tasks.txt'の構文エラー")
    return l


def read_casefiles(l):
    for i in range(len(l)):
        count = l[i]["count"]
        for j in range(count):
            d = {"arg":None, "out":None, "in":None}
            file_arg = os.path.join(c.CASE_PATH, l[i]["name"] + "_" + str(j) + "_arg.txt")
            file_out = os.path.join(c.CASE_PATH, l[i]["name"] + "_" + str(j) + "_out.txt")
            file_in = os.path.join(c.CASE_PATH, l[i]["name"] + "_" + str(j) + "_in.txt")
            if os.path.isfile(file_arg):
                d["arg"] = c.file2list(file_arg)[0]
            if os.path.isfile(file_out):
                d["out"] = c.file2str(file_out)
            if os.path.isfile(file_in):
                d["in"] = c.file2str(file_in)
            l[i]["case"] += [d]
    return l


def bool2str(b, str_true, str_false, none = None):
    if b is None:
        return c.str_color(c.Color.BG_CYAN, none)
    elif b:
        return c.str_color(c.Color.BG_BLUE, str_true)
    else:
        return c.str_color(c.Color.BG_RED, str_false)


def chkarg():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--debug", help="デバッグ出力を有効にする", action='store_true')
    parser.add_argument('--src', help="ソースファイルの格納先を指定", type=str, default=c.SRC_PATH)
    parser.add_argument('--work', help="読み込みファイルの格納先を指定", type=str, default=c.WORK_PATH)
    parser.add_argument('--case', help="テストケースの格納先を指定", type=str, default=c.CASE_PATH)
    parser.add_argument('--result', help="結果の格納先を指定", type=str, default=c.RESULT_PATH)
    parser.add_argument('--temp', help="一時ファイル格納先を指定", type=str, default=c.TEMP_PATH)
    parser.add_argument('--timeout', help="1プログラム当たりのタイムアウト時間を秒で指定", type=int, default=c.TIMEOUT)
    parser.add_argument('--nocolor', help="色付き出力を無効化", action='store_true')
    args = parser.parse_args()
    c.DEBUG = args.debug
    c.SRC_PATH = args.src
    c.WORK_PATH = args.work
    c.CASE_PATH = args.case
    c.RESULT_PATH = args.result
    c.TEMP_PATH = args.temp
    c.TIMEOUT = args.timeout
    c.NOCOLOR = args.nocolor
    c.debug(f"Source: {c.SRC_PATH}", "chkarg")
    c.debug(f"Work: {c.WORK_PATH}", "chkarg")
    c.debug(f"Case: {c.CASE_PATH}", "chkarg")
    c.debug(f"Result: {c.RESULT_PATH}", "chkarg")
    c.debug(f"Temp: {c.TEMP_PATH}", "chkarg")
    c.debug(f"タイムアウト: {c.TIMEOUT}s", "chkarg")


def src_listgen():
    global srclist
    srclist = [
        f for f in os.listdir(c.SRC_PATH) if os.path.join(os.path.join(c.SRC_PATH, f))
    ]


if __name__ == "__main__":
    os.system("")
    chkarg()
    chkpath()
    main()