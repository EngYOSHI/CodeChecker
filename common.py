import sys
import os
import shutil
from enum import Enum


DEBUG = False
PRINT_SCORE = True
GCC_PATH = "mingw64\\bin\\"
SRC_PATH = "src\\"
WORK_PATH = "work\\"
CASE_PATH = "case\\"
RESULT_PATH = "result\\"
TEMP_PATH = "temp\\"
TIMEOUT = 10
TIMEOUT_CALC_RATIO = 5
NOCOLOR = False
OVERWRITE= False
INDENT = 2
STR_CUT_LEN = -1
COMPILER = "msvc"  # msvc or gcc


class Color(str, Enum):
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"
    BG_CYAN = "\033[46m"
    BG_LIGHTGRAY = "\033[48;5;240m"


class Encode(str, Enum):
    UTF8 = "utf-8"
    SJIS = "cp932"
    ERROR = "Encode error"


class RunResultState(str, Enum):
    OK = "OK"
    NG = "NG"
    SKIP = "SKIP"
    NOTEST = "NOTEST"  # コンパイルのみ
    ENCERR = "ENCERR"  # 出力がエンコードエラー等により未評価


class OutType(str, Enum):
    STDOUT = "stdout"
    STDERR = "stderr"
    FILE = "file"


class RunResultReason(str, Enum):
    NO_TESTCASE = "ﾃｽﾄｹｰｽなし"
    TIMEOUT = "タイムアウト"
    OUTFILE_ERROR = "出力ﾌｧｲﾙ名間違いorなし"
    ENCODE_ERROR = "未サポートｴﾝｺｰﾄﾞ"
    WRONG = "ﾃｽﾄｹｰｽと不一致"


class TaskDeclare:
    kadai_number: str
    testcase_num: int
    outfile: str | None = None
    skip: dict[int, OutType]
    include: list[str]

    def __init__(self, kadai_number: str, testcase_num: int):
        self.kadai_number = kadai_number
        self.testcase_num = testcase_num
        self.skip = {}
        self.include = []


class Testcase:
    # str_outがNoneの場合は実行だけ行い比較はしない（スキップ）
    arg: list[str] | None = None
    out_type: OutType
    str_out: str | None = None
    str_in: str | None = None

    def content(self, offset: int = 0, cut: int = -1) -> str:
        return str_indent(
            f"arg: {self.arg}, OutType: {self.out_type.value},"
            f" str_out: {str_cut(repr(self.str_out), cut)},"
            f" str_in: {str_cut(repr(self.str_in), cut)}",
            offset)


class Task:
    tasknumber: str  # 課題番号
    testcases: list[Testcase] | None  # テストケースのリスト，コンパイルのみの場合はNone
    outfile: None | str = None  # ファイル出力をチェックする場合はそのファイル名
    include: list[str]  # コンパイルの際に追加で必要なファイル名

    def __init__(self, tasknumber: str, testcases: list[Testcase] | None,
                 outfile: None | str, include: list[str]):
        self.tasknumber = tasknumber
        self.testcases = testcases
        self.outfile = outfile
        self.include = include

    def content(self, offset: int = 0, cut: int = -1) -> str:
        s = str_indent(f"課題番号: {self.tasknumber}\n", offset)
        if self.testcases is None:
            s += str_indent("コンパイルのみ\n", offset + 1)
        else:
            if self.outfile is not None:
                s += str_indent(f"ﾁｪｯｸ対象ﾌｧｲﾙ: {self.outfile}\n", offset + 1)
            if len(self.include) > 0:
                s += str_indent(f"インクルード: {self.include}\n", offset + 1)
            for i, testcase in enumerate(self.testcases, 1):
                s += str_indent(f"[{i}]: {testcase.content(cut = cut)}\n", offset + 1)
        return s.rstrip("\n")


class CompileResult:
    result: bool = True  # コンパイル成功時True, 失敗時False
    reason: None | str = None  # コンパイル成功時None，失敗時失敗理由
    stdout: str = ""  # コンパイラ出力．ソースコードなし，エンコードエラー等の場合は空文字

    def content(self, offset: int = 0, cut: int = -1) -> str:
        return str_indent(
            f"result: {self.result}, reason: {self.reason},"
            f" stdout: {str_cut(self.stdout, cut)}",
            offset)


class RunResult:
    result: RunResultState = RunResultState.SKIP  # テスト結果がテストケースと一致時OK，テスト失敗時NG，スキップ時SKIP
    reason: RunResultReason | None = None  # テスト失敗時はその理由．テスト成功時はNone
    str_out: str | None = None  # 実行時の標準出力．実行失敗時や未実行時はNone
    ratio: float | None = None  # 一致率．実行成功時で計算がタイムアウトせず完了したら値が入る

    def content(self, offset: int = 0, cut: int = -1) -> str:
        reason = "None" if self.reason is None else self.reason.value
        return str_indent(
            f"result: {self.result.value}, reason: {reason},"
            f" str_out: {str_cut(repr(self.str_out), cut)}, ratio: {self.ratio}",
            offset)


class TaskResult:
    task: Task
    compile_result: CompileResult
    run_results: list[RunResult] | None = None  # コンパイルエラーならNone

    def __init__(self, task: Task):
        self.task = task

    def content(self, offset: int = 0, cut: int = -1) -> str:
        s = str_indent(f"課題番号: {self.task.tasknumber}\n", offset)
        s += str_indent(f"コンパイル結果: {self.compile_result.content(cut = cut)}\n", offset + 1)
        if self.run_results is not None:
            for i, run_result in enumerate(self.run_results):
                s += str_indent(f"[{i}]: {run_result.content(cut = cut)}\n", offset + 2)
        return s.rstrip("\n")


class Student:
    student_number: str  # 学籍番号
    task_results: list[TaskResult]

    def __init__(self, student_number: str):
        self.student_number = student_number
        self.task_results = []

    def content(self, offset: int = 0, cut: int = -1) -> str:
        s = str_indent(f"学籍番号: {self.student_number}\n", offset)
        for task_result in self.task_results:
            s += str_indent(f"{task_result.content(cut = cut)}\n", offset + 1)
        return s.rstrip("\n")


def str_indent(s: str, offset: int):
    return (" " * INDENT * offset) + s


def str_color(color: Color, s: str) -> str:
    """文字列にANSIで指定の色をつける

    :param Color color: 色
    :param str s: 文字列
    :return: ANSIエスケープシーケンス付きの文字列
    :rtype: str
    """
    if NOCOLOR:
        return s
    else:
        return color + s + Color.RESET


def byte2str(byte) -> tuple[str, Encode]:
    try:
        # UTF8でデコードする
        s = byte.decode(Encode.UTF8)
        s = s.replace("\r\n","\n")
        return s, Encode.UTF8
    except:
        pass
    try:
        # SJISでデコードする
        s = byte.decode(Encode.SJIS)
        s = s.replace("\r\n","\n")
        return s, Encode.SJIS
    except:
        pass
    debug("サポートされていないエンコード", "byte2str")
    return "", Encode.ERROR


def del_dir(dir: str):
    """指定したフォルダを中身ごと削除する"""
    if os.path.isdir(dir):
        shutil.rmtree(dir)


def error(msg: str, need_exit: bool = True):
    print(str_color(Color.RED, msg))
    if need_exit:
        sys.exit(1)


def debug(msg: str, title: str | None = None):
    if DEBUG:
        if title is not None:
            print(str_color(Color.BG_GREEN, title + ":") + str_color(Color.GREEN, " " + msg))
        else:
            print(str_color(Color.GREEN, msg))


def str_cut(s: str, length: int):
    if length < 0:
        return s
    elif len(s) > length:
        return s[:length] + f"...(省略:{len(s) - length})"
    else:
        return s


def file2list(filename: str, err_exit: bool = False) -> tuple[list[str], Encode]:
    """テキストファイルをUTF-8で読み込み，各行を要素とするlist[str]を返す

    :param str filename: テキストファイル名
    :param err_exit bool: エンコードエラーのとき終了するか
    :return: (ファイルの中身, ファイルのエンコード)
    :rtype: tuple[str, Encode]
    """
    (s, enc) = file2str(filename, err_exit)
    l = s.splitlines()
    # 中身がないもの(空文字，改行や空白文字だけ)は排除
    l = [x for x in l if x.strip() != ""]
    return (l, enc)


def file2str(filename: str, err_exit = False) -> tuple[str, Encode]:
    """テキストファイルを読み込み，strとして返す

    :param str filename: テキストファイル名
    :param err_exit bool: エンコードエラーのとき終了するか
    :return: (ファイルの中身, ファイルのエンコード)
    :rtype: tuple[str, Encode]
    """
    with open(filename, 'rb') as f:
        try:
            b = f.read()
            (s, enc) = byte2str(b)
        except FileNotFoundError:
            error(f"{filename}がありません．", True)
    debug(f"{filename}: {enc.value}", "file2str")
    if err_exit and enc == Encode.ERROR:
        error(f"{filename}の読み込みでエンコードエラー．UTF-8のBOM無で記述してください．", True)
    return (s, enc)


def get_fileenc(filename: str) -> Encode:
    with open(filename, 'rb') as f:
        b = f.read()
        (_, enc) = byte2str(b)
    return enc


def conv_fileenc(from_file: str, from_enc: Encode, to_file: str, to_enc: Encode):
    with open(from_file, 'r', encoding=from_enc.value) as f_from:
        with open(to_file, 'x', encoding=to_enc.value) as f_to:
            basename = os.path.basename(from_file)
            debug(f"{basename}: {from_enc.value} -> {to_enc.value}", "conv_fileenc")
            f_to.write(f_from.read())


def get_filelist(dir: str) -> list[str]:
    """dirに入っているファイルのファイル名をlist[str]でsrclistに返す"""
    li = [
        f for f in os.listdir(dir) if os.path.isfile(os.path.join(dir, f))
    ]
    return li
