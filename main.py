import subprocess
import os
import re
import difflib
import argparse
import shutil

import common as c
import xl


srclist: list[str] = []


def main():
    student_numbers = c.file2list(os.path.join(c.CASE_PATH, "students.txt"))
    print("学生数: " + str(len(student_numbers)))
    c.debug(str(student_numbers))
    tasks:list[c.Task] = get_tasklist(os.path.join(c.CASE_PATH, "tasks.txt"))
    print("課題数: " + str(len(tasks)))
    for task in tasks:
        c.debug(task.content())
    src_listgen()
    print("ソースファイル数: " + str(len(srclist)))
    c.debug(str(srclist))
    students:list[c.Student] = eval_loop(student_numbers, tasks)
    del_temp()  # tempフォルダを削除
    print("未処理のファイル数: " + str(len(srclist)))
    print("結果をxlsxファイルに書き込み中...")
    xl.write_xl(students)
    write_untouched()


def write_untouched():
    with open(os.path.join(c.RESULT_PATH, "untouched.txt"), 'w') as f:
        for x in srclist:
            f.write(x + "\n")


def eval_loop(student_numbers: list[str], tasks: list[c.Task]) -> list[c.Student]:
    students: list[c.Student] = []
    for i, student_number in enumerate(student_numbers):
        student = c.Student(student_number)
        for task in tasks:
            student.task_results.append(eval(student_number, task))
        students.append(student)
        if c.PRINT_SCORE:
            progress = f"({i + 1}/{len(student_numbers)})"
            print_score(student, progress)
    return students


def eval(student_number: str, task: c.Task) -> c.TaskResult:
    task_result = c.TaskResult(task.tasknumber)
    current_process = f"{student_number}_{task.tasknumber}"
    c.debug("")
    c.debug(current_process, "eval")
    c.debug("----------------------")
    src_filename = get_latest_src(student_number, task.tasknumber)
    c.debug(str(src_filename), "srcfile")
    # コンパイル
    temp_reset()  # Tempフォルダの初期化
    task_result.compile_result = compile(src_filename, current_process)
    c.debug(task_result.compile_result.content(), "compile")
    if task_result.compile_result.result:
        # コンパイル成功ならテスト実行
        task_result.run_results = run_loop(current_process + ".exe", task)
        if task_result.run_results is None:
            c.debug("コンパイルのみ", "eval")
        else:
            c.debug("", "run_loop")
            for i, run_result in enumerate(task_result.run_results):
                c.debug(f"  [{i}] {run_result.content()}")
        mv_temp2bin(current_process + ".exe")  # 実行が終わったバイナリはbinフォルダへ移動
    return task_result


def get_latest_src(student_number: str, tasknumber: str) -> str | None:
    """評価対象（提出された中で一番最新）のソースファイルを識別して，そのファイル名を返す

    :param str student_number: 学籍番号
    :param str tasknumber: 課題番号
    :return:
        命名条件に合致するファイルがあれば，評価対象のファイル名をstrで返す
        命名条件に合致するファイルが一つもなければNoneを返す
    :rtype: str | None
    """
    global srclist
    r = student_number + "_" + tasknumber + r"(\([1-9][0-9]*\))?" + ".c"
    src = [x for x in srclist if re.match(r, x)]
    # 命名条件に合致するファイルが一つもない -> None
    if len(src) == 0:
        return None
    # チェックしたファイルをソースファイルリストから削除する
    for s in src:
        srclist.remove(s)
    # チェックすべきソースファイルを識別
    # 最新の提出物は，拡張子の前に番号が「付かない」，ピュアなファイル名のもの
    return f"{student_number}_{tasknumber}.c"


def compile(src_filename: str | None, exe_filename: str) -> c.CompileResult:
    compile_result = c.CompileResult()
    if src_filename is None:
        compile_result.result = False
        compile_result.reason = "未提出orﾌｧｲﾙ名間違い"
        return compile_result
    src_abs = os.path.join(os.path.abspath(c.SRC_PATH), src_filename)
    exe_abs = os.path.join(os.path.abspath(c.TEMP_PATH), exe_filename)
    cmd = ["gcc.exe", src_abs, "-o", exe_abs]
    c.debug(str(cmd), "compile")
    r = subprocess.run(cmd, cwd=c.GCC_PATH, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,shell=True)
    (stdout_str, stdout_encode) = c.byte2str(r.stdout)
    c.debug(f"Encode of stdout: {stdout_encode.value}", "compile")
    compile_result.stdout = stdout_str
    if r.returncode != 0:
        #コンパイル失敗
        compile_result.result = False
        compile_result.reason = "コンパイルエラー"
        if stdout_encode == c.Encode.ERROR:
            compile_result.reason += " + 未サポートｴﾝｺｰﾄﾞ"
    return compile_result


def run_loop(exe: str, task: c.Task) -> list[c.RunResult] | None:
    if task.testcases is None:
        return None  # コンパイルのみの場合はNone
    run_results: list[c.RunResult] = []
    for case_num, testcase in enumerate(task.testcases, start = 0):
        run_results.append(run_exe(exe, case_num, testcase))
    return run_results


def run_exe(exe: str, case_num: int, testcase: c.Testcase) -> c.RunResult:
    cmd = exe
    if testcase.arg is not None:
        c.debug(testcase.arg, "arg")
        cmd = cmd + " " + testcase.arg
    run_result = c.RunResult()
    proc = subprocess.Popen(cmd, cwd=c.TEMP_PATH, stdout=subprocess.PIPE, stdin=subprocess.PIPE, shell=True)
    try:
        if testcase.stdin is None:
            r = proc.communicate(timeout=c.TIMEOUT)
        else:
            r = proc.communicate(timeout=c.TIMEOUT, input=testcase.stdin.encode(c.Encode.SJIS))
    except subprocess.TimeoutExpired:
        #タイムアウト
        proc.kill()
        c.debug("タイムアウト.", "run_exe")
        run_result.result = c.RunResultState.NG
        run_result.reason = "タイムアウト"
        return run_result
    (stdout_str, stdout_encode) = c.byte2str(r[0])  # 標準出力のバイトストリームを文字列に変換
    c.debug(f"Encode of stdout[{case_num}]: {stdout_encode.value}", "run_exe")
    if stdout_encode == c.Encode.ERROR:
        run_result.result = c.RunResultState.UNRATED
        run_result.reason = "未サポートｴﾝｺｰﾄﾞ"
    elif testcase.stdout is None:
        run_result.result = c.RunResultState.SKIP
    else:
        run_result.stdout = stdout_str
        run_result.ratio = round(difflib.SequenceMatcher(None, stdout_str, testcase.stdout, False).ratio(), 3)
        if run_result.stdout == testcase.stdout:
            run_result.result = c.RunResultState.OK
        else:
            run_result.result = c.RunResultState.NG
            run_result.reason = "ﾃｽﾄｹｰｽと不一致"
    return run_result


def print_score(student: c.Student, progress):
    output = f"学籍番号: {student.student_number}  {progress}\n"
    for task_result in student.task_results:
        output += c.str_indent(f"課題番号: {task_result.tasknumber}\n", 1)
        output += c.str_indent(f"コンパイル: {bool2str(task_result.compile_result.result, "OK", "NG")}\n", 2)
        if task_result.compile_result.result:
            run_results = task_result.run_results
            if run_results is not None:
                correct = 0
                failed = 0
                skip = 0
                unrated = 0
                for i, run_result in enumerate(run_results):
                    output += c.str_indent(f"[{i}] -> Result: {run_result_to_str(run_result.result)}", 2)
                    if run_result.result == c.RunResultState.SKIP:
                        skip += 1
                    elif run_result.result == c.RunResultState.OK:
                        correct += 1
                    elif run_result.result == c.RunResultState.NG:
                        failed += 1
                        if run_result.reason is not None:
                            output += f" (理由: {run_result.reason})"
                        if run_result.ratio is not None:
                            output += f" (一致率: {run_result.ratio})"
                    elif run_result.result == c.RunResultState.UNRATED:
                        unrated += 1
                        if run_result.reason is not None:
                            output += f" (理由: {run_result.reason})"
                    output += "\n"
                output += c.str_indent(f"Summary: {correct}/{correct + failed + unrated}  (skip:{skip}, unrated:{unrated})\n", 2)
        else:
            # コンパイル失敗時
            if task_result.compile_result.reason is not None:
                output.rsplit("\n")  # 末尾の改行をキャンセル
                output += f" ({task_result.compile_result.reason})\n"
    print(output)



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
    if len(os.listdir(c.RESULT_PATH)) > 0:
        c.error(f"結果ファイルの格納先フォルダ({c.RESULT_PATH})の中身を空にしてください．")


def get_tasklist(filename) -> list[c.Task]:
    taskfiles = c.file2list(filename)
    tasks: list[c.Task] = []
    for i in range(len(taskfiles)):
        if re.fullmatch(r'[1-9][0-9]*-((A[1-9])|([1-9][a-z]*)) [1-9]', taskfiles[i]):
            temp = taskfiles[i].split(" ")
            testcases: list[c.Testcase] = read_casefiles(temp[0], int(temp[1]))
            tasks.append(c.Task(temp[0], testcases))
        else:
            c.error("'tasks.txt'の構文エラー")
    return tasks


def read_casefiles(tasknumber: str, case_num: int) -> list[c.Testcase]:
    testcases: list[c.Testcase] = []
    for i in range(case_num):
        testcase = c.Testcase()
        file_arg = os.path.join(c.CASE_PATH, tasknumber + "_" + str(i) + "_arg.txt")
        file_out = os.path.join(c.CASE_PATH, tasknumber + "_" + str(i) + "_out.txt")
        file_in = os.path.join(c.CASE_PATH, tasknumber + "_" + str(i) + "_in.txt")
        if os.path.isfile(file_arg):
            testcase.arg = c.file2list(file_arg)[0]  # 1行目だけ
        if os.path.isfile(file_out):
            testcase.stdout = c.file2str(file_out)
        if os.path.isfile(file_in):
            testcase.stdin = c.file2str(file_in)
        testcases.append(testcase)
    return testcases


def bool2str(b: bool, str_true: str, str_false: str, none: str = "None"):
    if b is None:
        return c.str_color(c.Color.BG_CYAN, none)
    elif b:
        return c.str_color(c.Color.BG_BLUE, str_true)
    else:
        return c.str_color(c.Color.BG_RED, str_false)


def run_result_to_str(res: c.RunResultState) -> str:
    if res == c.RunResultState.OK:
        return c.str_color(c.Color.BG_BLUE, res)
    elif res == c.RunResultState.NG:
        return c.str_color(c.Color.BG_RED, res)
    elif res == c.RunResultState.SKIP:
        return c.str_color(c.Color.BG_CYAN, res)
    elif res == c.RunResultState.UNRATED:
        return c.str_color(c.Color.BG_LIGHTGRAY, res)
    else:
        return res


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
    # SRC_PATHに入っているファイルのファイル名をlist[str]でsrclistに返す
    srclist = [
        f for f in os.listdir(c.SRC_PATH) if os.path.isfile(os.path.join(c.SRC_PATH, f))
    ]


if __name__ == "__main__":
    os.system("")
    chkarg()
    chkpath()
    main()