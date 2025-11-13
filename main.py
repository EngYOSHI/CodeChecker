import subprocess
import os
import re
import difflib
import argparse
import shutil
import multiprocessing

import common as c
import xl


srclist: list[str] = []


def main():
    global srclist
    (student_numbers, _) = c.file2list(os.path.join(c.CASE_PATH, "students.txt"), True)
    print("学生数: " + str(len(student_numbers)))
    c.debug(str(student_numbers))
    tasks:list[c.Task] = get_tasklist(os.path.join(c.CASE_PATH, "tasks.txt"))
    print("課題数: " + str(len(tasks)))
    for task in tasks:
        c.debug(task.content())
    srclist = c.get_filelist(c.SRC_PATH)
    print("ソースファイル数: " + str(len(srclist)))
    c.debug(str(srclist))
    students:list[c.Student] = eval_loop(student_numbers, tasks)
    c.del_dir(c.TEMP_PATH)  # tempフォルダを削除
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
    task_result = c.TaskResult(task)
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
            for i, run_result in enumerate(task_result.run_results, 1):
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
    copy_from = os.path.join(c.SRC_PATH, src_filename)
    shutil.copy(copy_from, c.TEMP_PATH)
    src_abs = os.path.join(os.path.abspath(c.TEMP_PATH), src_filename)
    exe_abs = os.path.join(os.path.abspath(c.TEMP_PATH), exe_filename)
    enc = c.get_fileenc(src_abs)
    cmd = ["gcc.exe", f"-finput-charset={enc.value}", src_abs, "-o", exe_abs]
    c.debug(str(cmd), "compile")
    r = subprocess.run(cmd, cwd=c.GCC_PATH, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, shell=True)
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


def run_loop(exe: str, task: c.Task) -> list[c.RunResult]:
    run_results: list[c.RunResult] = []
    if task.testcases is None:
        # コンパイルのみの場合
        run_result = c.RunResult()
        run_result.result = c.RunResultState.NOTEST
        run_result.reason = "ﾃｽﾄｹｰｽなし"
        run_results.append(run_result)
    else:
        for case_num, testcase in enumerate(task.testcases):
            run_results.append(
                run_exe(exe, case_num, testcase, task.outfile))
    return run_results


def run_exe(exe: str, case_num: int,
            testcase: c.Testcase, outfile: None | str) -> c.RunResult:
    c.debug(f"[{case_num}]", "run_exe")
    cmd = [os.path.join(c.TEMP_PATH, exe)]
    if testcase.arg is not None:
        cmd += testcase.arg
    run_result = c.RunResult()
    c.debug(c.str_indent(f"arg: {cmd}", 1))
    proc = subprocess.Popen(cmd, cwd=c.TEMP_PATH, stdout=subprocess.PIPE,
                            stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        if testcase.str_in is None:
            r = proc.communicate(timeout=c.TIMEOUT)
        else:
            r = proc.communicate(timeout=c.TIMEOUT, input=testcase.str_in.encode(c.Encode.SJIS))
    except subprocess.TimeoutExpired:
        #タイムアウト
        proc.kill()
        c.debug(c.str_indent("タイムアウト", 1))
        run_result.result = c.RunResultState.NG
        run_result.reason = "タイムアウト"
        return run_result
    c.debug(c.str_indent(f"Mode: {testcase.check_type.value}", 1))
    if outfile is not None and testcase.check_type == c.CheckType.FILE:
        # ファイル出力をチェック
        filepath = os.path.join(c.TEMP_PATH, outfile)
        if not os.path.isfile(filepath):
            run_result.result = c.RunResultState.NG
            run_result.reason = "出力ﾌｧｲﾙ名間違いorなし"
            return run_result
        (str_out, str_out_encode) = c.file2str(filepath)  # ファイルを読み込んで文字列に変換
    elif testcase.check_type == c.CheckType.STDERR:
        # stderrをチェック
        (str_out, str_out_encode) = c.byte2str(r[1])  # エラー出力のバイトストリームを文字列に変換
    else:
        # stdoutをチェック
        (str_out, str_out_encode) = c.byte2str(r[0])  # 標準出力のバイトストリームを文字列に変換
    c.debug(c.str_indent(f"Encode of output[{case_num}]: {str_out_encode.value}", 1))
    if str_out_encode == c.Encode.ERROR:
        run_result.result = c.RunResultState.ENCERR
        run_result.reason = "未サポートｴﾝｺｰﾄﾞ"
    elif testcase.check_type == c.CheckType.SKIP or testcase.str_out is None:
        run_result.result = c.RunResultState.SKIP
        run_result.str_out = str_out
    else:
        run_result.str_out = str_out
        run_result.ratio = get_ratio(str_out, testcase.str_out)
        if run_result.str_out == testcase.str_out:
            run_result.result = c.RunResultState.OK
        else:
            run_result.result = c.RunResultState.NG
            run_result.reason = "ﾃｽﾄｹｰｽと不一致"
    return run_result


def get_ratio(a, b) -> float | None:
    result_queue = multiprocessing.Queue()
    process = multiprocessing.Process(target=compute_ratio, args=(a, b, result_queue))
    process.start()
    process.join(timeout = c.TIMEOUT_CALC_RATIO)
    if process.is_alive():
        process.terminate()
        process.join()
        c.debug("一致率計算タイムアウト", "get_ratio")
        return None
    else:
        return result_queue.get() if not result_queue.empty() else None


def compute_ratio(a, b, result_queue):
    try:
        ratio = round(difflib.SequenceMatcher(None, a, b, False).ratio(), 3)
        result_queue.put(ratio)
    except Exception as e:
        result_queue.put(None)


def print_score(student: c.Student, progress):
    output = f"学籍番号: {student.student_number}  {progress}\n"
    for task_result in student.task_results:
        output += c.str_indent(f"課題番号: {task_result.task.tasknumber}\n", 1)
        output += c.str_indent(f"コンパイル: {bool2str(task_result.compile_result.result, "OK", "NG")}\n", 2)
        if task_result.compile_result.result:
            run_results = task_result.run_results
            if run_results is not None:
                correct = 0
                failed = 0
                skip = 0
                encerr = 0
                notest = 0
                for i, run_result in enumerate(run_results, 1):
                    output += c.str_indent(f"[{i}] -> 結果: {run_result_to_str(run_result.result)}", 3)
                    if run_result.reason is not None:
                        output += f" (理由: {run_result.reason})"
                    if run_result.result == c.RunResultState.SKIP:
                        skip += 1
                    elif run_result.result == c.RunResultState.NOTEST:
                        notest += 1
                    elif run_result.result == c.RunResultState.OK:
                        correct += 1
                    elif run_result.result == c.RunResultState.NG:
                        failed += 1
                        if run_result.ratio is not None:
                            output += f" (一致率: {run_result.ratio})"
                    elif run_result.result == c.RunResultState.ENCERR:
                        encerr += 1
                    output += "\n"
                output += c.str_indent(f"サマリ: {correct}/{correct + failed + encerr}  (スキップ:{skip}, 未評価:{notest + encerr})\n", 2)
        else:
            # コンパイル失敗時
            if task_result.compile_result.reason is not None:
                output = output.rstrip("\n")  # 末尾の改行をキャンセル
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


def temp_reset():
    """一時保存フォルダ(temp)を初期化する
    
    一時保存フォルダが存在する場合はフォルダごと消す
    その後，workフォルダをtempフォルダとしてコピー
    """
    c.del_dir(c.TEMP_PATH)
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
        if c.OVERWRITE:
            c.del_dir(c.RESULT_PATH)
            os.mkdir(c.RESULT_PATH)
        else:
            c.error(f"結果ファイルの格納先フォルダ({c.RESULT_PATH})の中身を空にしてください．")


def get_tasklist(filename) -> list[c.Task]:
    (taskfiles, _) = c.file2list(filename, True)
    tasks: list[c.Task] = []
    pattern = re.compile(
            r"(?P<kadai_number>[1-9][0-9]*-(?:A[1-9]|[1-9][a-z]*))"
            r" (?P<testcase_num>[0-9])"
            r"( outfile=\"(?P<outfile>[^\"]+)\")?"
        )
    for taskfile in taskfiles:
        match = pattern.fullmatch(taskfile)
        if match:
            kadai_number = match["kadai_number"]
            testcase_num = int(match["testcase_num"])
            outfile: str | None = match["outfile"]
            outfile_enable = True if outfile is not None else False
            testcases = read_casefiles(
                kadai_number, testcase_num, outfile_enable)
            tasks.append(c.Task(kadai_number, testcases, outfile))
        else:
            c.error("'tasks.txt'の構文エラー")
    return tasks


def read_casefiles(tasknumber: str, case_num: int,
                   outfile_enable: bool) -> list[c.Testcase] | None:
    if case_num == 0:
        return None
    testcases: list[c.Testcase] = []
    for i in range(1, case_num + 1):
        testcase = c.Testcase()
        file_arg = os.path.join(c.CASE_PATH, f"{tasknumber}_{i}_arg.txt")
        file_out = os.path.join(c.CASE_PATH, f"{tasknumber}_{i}_out.txt")
        file_fout = os.path.join(c.CASE_PATH, f"{tasknumber}_{i}_fout.txt")
        file_eout = os.path.join(c.CASE_PATH, f"{tasknumber}_{i}_eout.txt")
        file_in = os.path.join(c.CASE_PATH, f"{tasknumber}_{i}_in.txt")
        if os.path.isfile(file_arg):
            testcase.arg = c.file2list(file_arg, True)[0]
        if os.path.isfile(file_fout):
            if not outfile_enable:
                c.error(f"ファイル出力のチェックが無効なのに，foutが指定されています．（{tasknumber}_{i}_fout.txt）")
            (testcase.str_out, _) = c.file2str(file_fout, True)
            testcase.check_type = c.CheckType.FILE
        elif os.path.isfile(file_eout):
            (testcase.str_out, _) = c.file2str(file_eout, True)
            testcase.check_type = c.CheckType.STDERR
        elif os.path.isfile(file_out):
            (testcase.str_out, _) = c.file2str(file_out, True)
            testcase.check_type = c.CheckType.STDOUT
        if os.path.isfile(file_in):
            (testcase.str_in, _) = c.file2str(file_in, True)
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
    elif res == c.RunResultState.ENCERR:
        return c.str_color(c.Color.BG_LIGHTGRAY, res)
    elif res == c.RunResultState.NOTEST:
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
    parser.add_argument('--ratio_timeout', help="一致率計算のタイムアウトを秒で指定", type=int, default=c.TIMEOUT_CALC_RATIO)
    parser.add_argument('--nocolor', help="色付き出力を無効化", action='store_true')
    parser.add_argument('--overwrite', help="結果フォルダの上書きを許可", action='store_true')
    args = parser.parse_args()
    c.DEBUG = args.debug
    c.SRC_PATH = args.src
    c.WORK_PATH = args.work
    c.CASE_PATH = args.case
    c.RESULT_PATH = args.result
    c.TEMP_PATH = args.temp
    c.TIMEOUT = args.timeout
    c.TIMEOUT_CALC_RATIO = args.ratio_timeout
    c.NOCOLOR = args.nocolor
    c.OVERWRITE = args.overwrite
    c.debug(f"Source: {c.SRC_PATH}", "chkarg")
    c.debug(f"Work: {c.WORK_PATH}", "chkarg")
    c.debug(f"Case: {c.CASE_PATH}", "chkarg")
    c.debug(f"Result: {c.RESULT_PATH}", "chkarg")
    c.debug(f"Temp: {c.TEMP_PATH}", "chkarg")
    c.debug(f"タイムアウト: {c.TIMEOUT}s", "chkarg")
    c.debug(f"一致率計算タイムアウト: {c.TIMEOUT_CALC_RATIO}s", "chkarg")
    c.debug(f"Result上書き: {c.OVERWRITE}", "chkarg")


if __name__ == "__main__":
    os.system("")
    chkarg()
    chkpath()
    main()