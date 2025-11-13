import os
import re

import common as c


def main():
    srclist = c.get_filelist(c.SRC_PATH)  # ソースファイル一覧取得
    rename(srclist)


def rename(srclist: list[str]):
    pattern = re.compile(
        r"(?P<student_number>[0-9]+)"
        r"_(?P<kadai_number>[1-9][0-9]*-(?:A[1-9]|[1-9][a-z]*))"
        r" - (?P<student_name>.+)\.c"
    )
    for old_filename in srclist:
        match = pattern.fullmatch(old_filename)
        if match:
            student_number = match["student_number"]
            kadai_number = match["kadai_number"]
            new_filename = f"{student_number}_{kadai_number}.c"
            old_filename = os.path.join(c.SRC_PATH, old_filename)
            new_filename = os.path.join(c.SRC_PATH, new_filename)
            os.rename(old_filename, new_filename)
            print(f"リネーム完了: {old_filename} -> {new_filename}")
        else:
            print(f"リネーム不可: {old_filename}")


if __name__ == "__main__":
    os.system("")
    main()