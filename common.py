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
TIMEOUT = 5
NOCOLOR = False
OVERWRITE= False
INDENT = 2


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
    UNRATED = "??"  # 出力がエンコードエラー等により未評価


class Testcase:
    # stdoutがNoneの場合は実行だけ行い比較はしない（スキップ）
    arg: str | None = None
    stdout: str | None = None
    stdin: str | None = None

    def content(self, offset: int = 0) -> str:
        return str_indent(
            f"arg: {self.arg}, stdout: {repr(self.stdout)}, stdin: {repr(self.stdin)}",
            offset)


class Task:
    tasknumber: str  # 課題番号
    testcases: list[Testcase] | None  # テストケースのリスト，コンパイルのみの場合はNone

    def __init__(self, tasknumber: str, testcases: list[Testcase] | None):
        self.tasknumber = tasknumber
        self.testcases = testcases

    def content(self, offset: int = 0) -> str:
        s = str_indent(f"課題番号: {self.tasknumber}\n", offset)
        if self.testcases is None:
            s += str_indent("コンパイルのみ\n", offset + 1)
        else:
            for i, testcase in enumerate(self.testcases, 1):
                s += str_indent(f"[{i}]: {testcase.content()}\n", offset + 1)
        return s.rstrip("\n")


class CompileResult:
    result: bool = True  # コンパイル成功時True, 失敗時False
    reason: None | str = None  # コンパイル成功時None，失敗時失敗理由
    stdout: str = ""  # コンパイラ出力．ソースコードなし，エンコードエラー等の場合は空文字

    def content(self, offset: int = 0) -> str:
        return str_indent(
            f"result: {self.result}, reason: {self.reason}, stdout: {self.stdout}",
            offset)


class RunResult:
    result: RunResultState = RunResultState.SKIP  # テスト結果がテストケースと一致時OK，テスト失敗時NG，スキップ時SKIP
    reason: str | None = None  # テスト失敗時はその理由．テスト成功時はNone
    stdout: str | None = None  # 実行時の標準出力．実行失敗時はNone
    ratio: float | None = None  # 一致率

    def content(self, offset: int = 0) -> str:
        return str_indent(
            f"result: {self.result.value}, reason: {self.reason}, stdout: {repr(self.stdout)}, ratio: {self.ratio}",
            offset)


class TaskResult:
    tasknumber: str  # 課題番号
    compile_result: CompileResult
    run_results: list[RunResult] | None = None  # コンパイルエラー等でテスト実行しないならNone

    def __init__(self, tasknumber: str):
        self.tasknumber = tasknumber

    def content(self, offset: int = 0) -> str:
        s = str_indent(f"課題番号: {self.tasknumber}\n", offset)
        s += str_indent(f"コンパイル結果: {self.compile_result.content()}\n", offset + 1)
        if self.run_results is not None:
            for i, run_result in enumerate(self.run_results):
                s += str_indent(f"[{i}]: {run_result.content()}\n", offset + 2)
        return s.rstrip("\n")


class Student:
    student_number: str  # 学籍番号
    task_results: list[TaskResult]

    def __init__(self, student_number: str):
        self.student_number = student_number
        self.task_results = []

    def content(self, offset: int = 0) -> str:
        s = str_indent(f"学籍番号: {self.student_number}\n", offset)
        for task_result in self.task_results:
            s += str_indent(f"{task_result.content()}\n", offset + 1)
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


def file2list(filename: str) -> list[str]:
    """テキストファイルをUTF-8で読み込み，各行を要素とするlist[str]を返す

    :param str filename: テキストファイル名
    :return: テキストファイルの中身
    :rtype: list[str]
    """
    with open(filename, 'r', encoding=Encode.UTF8) as f:
        try:
            l = f.readlines()
        except UnicodeDecodeError:
            error(f"{filename}の読み込みでエンコードエラー．UTF-8のBOM無で記述してください．", True)
    for i in range(len(l)):
        if l[i].strip() == "":
            l.pop(i)
        else:
            l[i] = l[i].rstrip("\n")
    return l


def file2str(filename: str) -> str:
    """テキストファイルをUTF-8で読み込み，strとして返す

    :param str filename: テキストファイル名
    :return: テキストファイルの中身
    :rtype: str
    """
    with open(filename, 'r', encoding=Encode.UTF8) as f:
        try:
            s = f.read()
        except UnicodeDecodeError:
            error(f"{filename}の読み込みでエンコードエラー．UTF-8のBOM無で記述してください．", True)
    return s
