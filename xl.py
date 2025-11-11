import os
import openpyxl
import re

import common as c


_ILLEGAL_CHARACTERS_RE = re.compile(r"[\000-\010]|[\013-\014]|[\016-\037]")


def write_xl(students: list[c.Student]):
    wb = openpyxl.Workbook()
    wb.properties.creator = 'CodeChecker'
    wb.properties.lastModifiedBy = 'CodeChecker'
    ws = wb["Sheet"]
    ws.append(["学籍番号", "課題番号", "ｺﾝﾊﾟｲﾙ結果", "コンパイル備考", "コンパイルログ", "ﾃｽﾄｹｰｽ", "テスト結果", "テスト結果備考", "ﾃｽﾄｹｰｽ一致率", "標準出力"])
    for char in list("ABDEHJ"):
        ws.column_dimensions[char].width = 20
    ws.column_dimensions["C"].width = 10
    ws.column_dimensions["F"].width = 7
    ws.column_dimensions["G"].width = 11
    ws.column_dimensions["I"].width = 13
    ws.freeze_panes = "A2" #先頭行を固定
    row = 2
    for student in students:
        ws.cell(row=row, column=1).value = student.student_number
        for task in student.task_results:
            ws.cell(row=row, column=2).value = task.tasknumber
            ws.cell(row=row, column=3).value = valconv(task.compile_result.result, bool, "OK", "NG")
            cellfill(ws.cell(row=row, column=3), [("OK", "00b050"),("NG", "e09694")])
            ws.cell(row=row, column=4).value = valconv(task.compile_result.reason, str, none="")
            ws.cell(row=row, column=5).value = task.compile_result.stdout
            if task.run_results is None:
                ws.cell(row=row, column=6).value = "　" #コンパイルログが右のセルにはみ出さないように
                row += 1
                continue
            for i, run_result in enumerate(task.run_results):
                ws.cell(row=row, column=6).value = task.tasknumber + f" [{str(i + 1)}]"
                ws.cell(row=row, column=7).value = run_result.result.value
                cellfill(ws.cell(row=row, column=7),
                         [(c.RunResultState.OK, "00b050"),
                          (c.RunResultState.NG, "e09694"),
                          (c.RunResultState.SKIP, "c5d9f1"),
                          (c.RunResultState.UNRATED, "a2a2a2")]
                        )
                ws.cell(row=row, column=8).value = valconv(run_result.reason, str, none="")
                ws.cell(row=row, column=9).value = valconv(run_result.ratio, float, none="")
                if run_result.stdout is None:
                    ws.cell(row=row, column=10).value = ""
                else:
                    # 不正な文字が含まれているとIllegalCharacterError例外を出して止まるので排除
                    stdout = _ILLEGAL_CHARACTERS_RE.sub("", str(run_result.stdout))
                    ws.cell(row=row, column=10).value = valconv(stdout, str, none="")
                row += 1
    path = os.path.join(c.RESULT_PATH, "result.xlsx")
    wb.save(path)


def valconv(data, type, str_true = "True", str_false = "False", none = "None"):
    if data is None: return none
    elif type == bool:
        if data: return str_true
        else: return str_false
    else: return data


def cellfill(cell, conditions):
    #conditionsは(文字列, 色)のリスト
    for s, color in conditions:
        if cell.value == s:
            cell.fill = openpyxl.styles.PatternFill(patternType='solid', fgColor=color)
            return