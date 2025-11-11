import os
import openpyxl

import common as c


def write_xl(res):
    #[{student:str,
    #  result:[{task:str,
    #           compile:{result:bool, reason:None|str, stdout:str|None},
    #           run:[{result:bool|None, reason:None|str, output:str|None, ratio:float|None} | None]
    #         }]
    #}]
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
    for res_student in res:
        ws.cell(row=row, column=1).value = res_student["student"]
        for task in res_student["result"]:
            ws.cell(row=row, column=2).value = task["task"]
            ws.cell(row=row, column=3).value = valconv(task["compile"]["result"], bool, t = "OK", f = "NG")
            cellfill(ws.cell(row=row, column=3), [("OK", "00b050"),("NG", "e09694")])
            ws.cell(row=row, column=4).value = valconv(task["compile"]["reason"], str, none="")
            ws.cell(row=row, column=5).value = valconv(task["compile"]["stdout"], str, none="")
            if task["run"] is None:
                ws.cell(row=row, column=6).value = "　" #コンパイルログが右のセルにはみ出さないように
                row += 1
                continue
            for i, run in enumerate(task["run"]):
                ws.cell(row=row, column=6).value = task["task"] + "_" + str(i + 1)
                ws.cell(row=row, column=7).value = valconv(run["result"], bool, t="OK", f="NG", none="SKIP")
                cellfill(ws.cell(row=row, column=7), [("OK", "00b050"),("NG", "e09694"),("SKIP", "c5d9f1")])
                ws.cell(row=row, column=8).value = valconv(run["reason"], str, none="")
                ws.cell(row=row, column=9).value = valconv(run["ratio"], float, none="")
                ws.cell(row=row, column=10).value = valconv(run["output"], str, none="")
                row += 1
    path = os.path.join(c.RESULT_PATH, "result.xlsx")
    wb.save(path)


def valconv(data, type, t = "True", f = "False", none = "None"):
    if data is None: return none
    elif type == bool:
        if data: return t
        else: return f
    else: return data


def cellfill(cell, conditions):
    #conditionsは(文字列, 色)のリスト
    for s, color in conditions:
        if cell.value == s:
            cell.fill = openpyxl.styles.PatternFill(patternType='solid', fgColor=color)
            return