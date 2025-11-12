import os
import openpyxl
from openpyxl.styles import Alignment, PatternFill, Font
import re

import common as c


_ILLEGAL_CHARACTERS_RE = re.compile(r"[\000-\010]|[\013-\014]|[\016-\037]")


def write_xl(students: list[c.Student]):
    wb = openpyxl.Workbook()
    wb.properties.creator = 'CodeChecker'
    wb.properties.lastModifiedBy = 'CodeChecker'
    ws = wb["Sheet"]
    ws.append(["学籍番号", "課題番号", "ｺﾝﾊﾟｲﾙ\n結果", "コンパイル備考", "コンパイルログ",
               "ﾃｽﾄｹｰｽ", "テスト\n結果", "テスト結果備考", "ﾃｽﾄｹｰｽ\n一致率", "標準出力"])
    ws.row_dimensions[1].height = 27
    # 先頭行にスタイル適用
    for cell in ws[1]:
        cell.alignment = Alignment(horizontal = "center",
                                   vertical = "center", wrapText = True)
        cell.font = Font(bold = True)
    # 列幅を設定
    column_width = {"A":11, "B":10, "C":10, "D":20, "E":20,
                    "F":10, "G":10, "H":20, "I":10, "J":30}
    for column, width in column_width.items():
        ws.column_dimensions[column].width = width
    ws.freeze_panes = "A2" #先頭行を固定
    ws.auto_filter.ref = "A1:J1"  # フィルタを設定
    wraptext = ["D", "E", "H", "J"]
    row = 2
    for student in students:
        for task in student.task_results:
            ws["A" + str(row)].value = student.student_number
            ws["B" + str(row)].value = task.tasknumber
            ws["C" + str(row)].value = valconv(task.compile_result.result, bool, "OK", "NG")
            cellfill(ws["C" + str(row)], [("OK", "00b050"),("NG", "e09694")])
            ws["C" + str(row)].alignment = Alignment(horizontal = "center")
            ws["D" + str(row)].value = valconv(task.compile_result.reason, str, none="")
            ws["E" + str(row)].value = task.compile_result.stdout
            if task.run_results is None:
                row += 1
                continue
            for i, run_result in enumerate(task.run_results):
                ws["F" + str(row)].value = task.tasknumber + f" [{str(i + 1)}]"
                ws["G" + str(row)].value = run_result.result.value
                cellfill(ws["G" + str(row)],
                         [(c.RunResultState.OK, "00b050"),
                          (c.RunResultState.NG, "e09694"),
                          (c.RunResultState.SKIP, "c5d9f1"),
                          (c.
                          RunResultState.UNRATED, "a2a2a2")]
                        )
                ws["G" + str(row)].alignment = Alignment(horizontal = "center")
                ws["H" + str(row)].value = valconv(run_result.reason, str, none="")
                ws["I" + str(row)].value = valconv(run_result.ratio, float, none="")
                ws["I" + str(row)].number_format = "0.000"
                if run_result.stdout is None:
                    ws["J" + str(row)].value = ""
                else:
                    # 不正な文字が含まれているとIllegalCharacterError例外を出して止まるので?に置き換え
                    stdout = _ILLEGAL_CHARACTERS_RE.sub("?", run_result.stdout)
                    ws["J" + str(row)].value = valconv(stdout, str, none="")
                # 折り返して全体を表示
                for column in wraptext:
                    ws[column + str(row)].alignment = Alignment(wrapText = True,
                                                                vertical = 'top')
                ws.row_dimensions[row].height = 13.5
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
            cell.fill = PatternFill(patternType='solid', fgColor=color)
            return
