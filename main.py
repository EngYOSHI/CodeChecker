import subprocess
import os
import re
import argparse
import shutil
import multiprocessing
import shlex
from rapidfuzz import fuzz

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
        c.debug(task.content(cut = c.STR_CUT_LEN))
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
    task_result.compile_result = compile(src_filename, current_process, task.include)
    c.debug(task_result.compile_result.content(cut = c.STR_CUT_LEN), "compile")
    if task_result.compile_result.result:
        # コンパイル成功ならテスト実行
        task_result.run_results = run_loop(current_process + ".exe", task)
        if task_result.run_results is None:
            c.debug("コンパイルのみ", "eval")
        else:
            c.debug("", "run_loop")
            for i, run_result in enumerate(task_result.run_results, 1):
                c.debug(f"  [{i}] {run_result.content(cut = c.STR_CUT_LEN)}")
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


def compile(src_filename: str | None, exe_filename: str, include: list[str]) -> c.CompileResult:
    compile_result = c.CompileResult()
    if src_filename is None:
        compile_result.result = False
        compile_result.reason = "未提出orﾌｧｲﾙ名間違い"
        return compile_result
    copy_from = os.path.join(c.SRC_PATH, src_filename)
    # ソースコードのエンコードがSJISの場合はUTF-8に変換したものをコピー
    if c.get_fileenc(copy_from) == c.Encode.SJIS:
        c.conv_fileenc(copy_from, c.Encode.SJIS,
                       os.path.join(c.TEMP_PATH, src_filename),
                       c.Encode.UTF8)
    else:
        shutil.copy(copy_from, c.TEMP_PATH)
    if c.COMPILER == "gcc":
        src_path = os.path.join(os.path.abspath(c.TEMP_PATH), src_filename)
        exe_path = os.path.join(os.path.abspath(c.TEMP_PATH), exe_filename)
        enc = c.get_fileenc(src_path)
        cmd = ["gcc.exe", f"-finput-charset={enc.value}", src_path, "-o", exe_path]
        c.debug(str(cmd), "compile")
        r = subprocess.run(cmd, cwd=c.GCC_PATH, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, shell=True)
    elif c.COMPILER == "msvc":
        # cl /source-charset:utf-8 /Fe:{exe_filename}.exe src1.c src2.c
        # ソースコード，インクルードするファイルはUTF-8でエンコードされている必要がある！
        src_path = src_filename
        enc = c.get_fileenc(os.path.join(os.path.abspath(c.TEMP_PATH), src_filename))
        cmd = ["cl", "/nologo", "/source-charset:utf-8", f"/Fe:{exe_filename + ".exe"}", src_path] + include
        c.debug(str(cmd), "compile")
        r = subprocess.run(cmd, cwd=c.TEMP_PATH, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, shell=True)
    else:
        c.error(f"コンパイラ指定がエラーです． ({c.COMPILER})")
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
        run_result.reason = c.RunResultReason.NO_TESTCASE
        run_results.append(run_result)
    else:
        for case_num, testcase in enumerate(task.testcases):
            run_results.append(
                run_exe(exe, case_num, testcase, task.outfile))
    return run_results


def run_exe(exe: str, case_num: int,
            testcase: c.Testcase, outfile: None | str) -> c.RunResult:
    c.debug(f"[{case_num + 1}]", "run_exe")
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
        run_result.reason = c.RunResultReason.TIMEOUT
        return run_result
    c.debug(c.str_indent(f"Mode: {testcase.out_type.value}", 1))
    if testcase.out_type == c.OutType.FILE:
        # ファイル出力をチェック
        if outfile is None:
            c.error("内部エラー: outfile should not be None.")
        else:
            filepath = os.path.join(c.TEMP_PATH, outfile)
            if not os.path.isfile(filepath):
                run_result.result = c.RunResultState.NG
                run_result.reason = c.RunResultReason.OUTFILE_ERROR
                return run_result
            (str_out, str_out_encode) = c.file2str(filepath)  # ファイルを読み込んで文字列に変換
    elif testcase.out_type == c.OutType.STDERR:
        # stderrをチェック
        (str_out, str_out_encode) = c.byte2str(r[1])  # エラー出力のバイトストリームを文字列に変換
    else:
        # stdoutをチェック
        (str_out, str_out_encode) = c.byte2str(r[0])  # 標準出力のバイトストリームを文字列に変換
    c.debug(c.str_indent(f"Encode of output: {str_out_encode.value}", 1))
    if str_out_encode == c.Encode.ERROR:
        run_result.result = c.RunResultState.ENCERR
        run_result.reason = c.RunResultReason.ENCODE_ERROR
    elif testcase.str_out is None:
        run_result.result = c.RunResultState.SKIP
        run_result.str_out = str_out
    else:
        run_result.str_out = str_out
        if run_result.str_out == testcase.str_out:
            run_result.result = c.RunResultState.OK
            run_result.ratio = 100.0
        else:
            run_result.result = c.RunResultState.NG
            run_result.ratio = get_ratio(str_out, testcase.str_out)
            run_result.reason = c.RunResultReason.WRONG
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
        ratio = round(fuzz.ratio(a, b), 3)
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
                        output += f" (理由: {run_result.reason.value})"
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
    for taskfile in taskfiles:
        task_declare = parse_tasklist(taskfile)
        testcases = read_casefiles(task_declare)
        tasks.append(c.Task(task_declare.kadai_number, testcases,
                            task_declare.outfile, task_declare.include))
    return tasks


def parse_tasklist(s: str) -> c.TaskDeclare:
    p_skip = re.compile(r"skip(?P<skip_num>[0-9])=(?P<skip_val>.+)")
    skip_type: list[str] = [member.value for member in c.OutType]
    def getval(s: str):
        return s.split("=", 1)[1]

    def skip(part: str) -> bool:
        match = p_skip.fullmatch(part)
        if match:
            skip_num = int(match["skip_num"])
            if skip_num in task_declare.skip:
                c.error(f"tasks.txt: skip{skip_num}が複数回指定されています．")
            if match["skip_val"] in skip_type:
                task_declare.skip[skip_num] = c.OutType(match["skip_val"])
            else:
                c.error(f"tasks.txt: skipは{skip_type}のどれかである必要があります．")
            return True
        else:
            return False

    parts = shlex.split(s)
    if not re.fullmatch(r"[1-9][0-9]*-(?:A[1-9]|[1-9][a-z]?)", parts[0]):
        c.error(f"tasks.txt: 課題番号に構文エラー  ({parts[0]})")
    elif not re.fullmatch(r"[0-9]", parts[1]):
        c.error(f"tasks.txt: テストケース数に構文エラー  ({parts[1]})")
    task_declare = c.TaskDeclare(parts[0], int(parts[1]))
    for part in parts[2:]:
        if part.startswith("outfile="):
            if task_declare.outfile is None:
                task_declare.outfile = getval(part)
            else:
                c.error(f"tasks.txt: outfileは複数指定できません．")
        elif skip(part):
            continue
        elif part.startswith("include="):
            # インクルードするファイルの存在と文字コードをチェック(UTF-8指定)
            val = getval(part)
            filepath = os.path.join(c.WORK_PATH, val)
            if not os.path.isfile(filepath):
                c.error(f"{parts[0]}で{part}が指定されていますが，workフォルダにありません．")
            elif c.get_fileenc(filepath) != c.Encode.UTF8:
                c.error(f"{filepath}とそのヘッダファイルは，UTF-8 BOMなしでエンコードしてください．")
            task_declare.include.append(val)
        else:
            c.error(f"tasks.txt: 構文エラー  (\"{part}\"付近)")
    return task_declare


def read_casefiles(task_declare: c.TaskDeclare) -> list[c.Testcase] | None:
    case_num = task_declare.testcase_num
    tasknumber = task_declare.kadai_number
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
        if i in task_declare.skip:
            testcase.out_type = task_declare.skip[i]
        elif os.path.isfile(file_fout):
            if task_declare.outfile is None:
                c.error(f"ファイル出力のチェックが無効なのに，foutが指定されています．（{tasknumber}_{i}_fout.txt）")
            (testcase.str_out, _) = c.file2str(file_fout, True)
            testcase.out_type = c.OutType.FILE
        elif os.path.isfile(file_eout):
            (testcase.str_out, _) = c.file2str(file_eout, True)
            testcase.out_type = c.OutType.STDERR
        elif os.path.isfile(file_out):
            (testcase.str_out, _) = c.file2str(file_out, True)
            testcase.out_type = c.OutType.STDOUT
        else:
            c.error(f"{tasknumber}[{i}]はSKIP指定でない，かつ，出力のテストパタンがありません．")
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
    parser.add_argument('--strcut', help="一部のデバッグ出力の文字数上限を指定", type=int, default=c.STR_CUT_LEN)
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
    c.STR_CUT_LEN = args.strcut
    c.NOCOLOR = args.nocolor
    c.OVERWRITE = args.overwrite
    c.debug(f"Source: {c.SRC_PATH}", "chkarg")
    c.debug(f"Work: {c.WORK_PATH}", "chkarg")
    c.debug(f"Case: {c.CASE_PATH}", "chkarg")
    c.debug(f"Result: {c.RESULT_PATH}", "chkarg")
    c.debug(f"Temp: {c.TEMP_PATH}", "chkarg")
    c.debug(f"タイムアウト: {c.TIMEOUT}s", "chkarg")
    c.debug(f"一致率計算タイムアウト: {c.TIMEOUT_CALC_RATIO}s", "chkarg")
    c.debug(f"デバッグ情報省略: {c.STR_CUT_LEN}", "chkarg")
    c.debug(f"Result上書き: {c.OVERWRITE}", "chkarg")


if __name__ == "__main__":
    os.system("")
    chkarg()
    chkpath()
    main()