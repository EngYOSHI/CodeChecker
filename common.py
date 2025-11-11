import sys

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


class Color:
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"
    BG_CYAN = "\033[46m"


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


def byte2str(byte) -> tuple[str | None, str]:
    try:
        # UTF8でデコードする
        s = byte.decode("utf-8")
        s = s.replace("\r\n","\n")
        return s, "utf-8"
    except:
        pass
    try:
        # SJISでデコードする
        s = byte.decode("cp932")
        s = s.replace("\r\n","\n")
        return s, "cp932"
    except:
        pass
    debug("サポートされていないエンコード", "byte2str")
    return None, "Encode error"


def error(msg: str, need_exit: bool = True):
    print(str_color(Color.RED, msg))
    if need_exit:
        sys.exit(1)


def debug(msg: str, title: str = None):
    if DEBUG:
        if title is not None:
            print(str_color(Color.BG_GREEN, title + ":") + str_color(Color.GREEN, " " + msg))
        else:
            print(str_color(Color.GREEN, msg))


def file2list(filename) -> str:
    with open(filename, 'r', encoding="utf-8") as f:
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


def file2str(filename) -> str:
    with open(filename, 'r', encoding="utf-8") as f:
        try:
            s = f.read()
        except UnicodeDecodeError:
            error(f"{filename}の読み込みでエンコードエラー．UTF-8のBOM無で記述してください．", True)
    return s
