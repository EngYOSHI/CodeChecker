import subprocess
import os
import sys
import re
import time
import pprint
import difflib
import argparse
import openpyxl

DEBUG = False
PRINT_SCORE = True
GCC_PATH = "mingw64\\bin\\"
SRC_PATH = "src\\"
WORK_PATH = "work\\"
CASE_PATH = "case\\"
RESULT_PATH = "result\\"
TIMEOUT = 5
NOCOLOR = False


srclist = []


def main():
	students = file2list(os.path.join(CASE_PATH, "students.txt"))
	print("Number of Students: " + str(len(students)))
	debug(students)
	tasks = readTaskFile(os.path.join(CASE_PATH, "tasks.txt"))
	print("Number of tasks: " + str(len(tasks)))
	tasks = readCaseFile(tasks)
	makeSrcFileList()
	debug(srclist)
	print("Number of files in source directory: " + str(len(srclist)))
	debug(pprint.pformat(tasks, sort_dicts=False))
	res = eval_loop(students, tasks)
	#pprint.pprint(res, sort_dicts=False)
	print("Number of Unevaluated files: " + str(len(srclist)))
	print("Writing the results as xlsx...")
	writexl(res)


def writexl(res):
	#[{student:str,
	#  result:[{task:str,
	#           src:str|None,
	#           compile:{result:bool, reason:None|str, stdout:str|None},
	#           run:[{result:bool|None, reason:None|str, output:str|None, ratio:float|None} | None]
	#         }]
	#}]
	global RESULT_PATH
	wb = openpyxl.Workbook()
	wb.properties.creator = 'CodeChecker'
	wb.properties.lastModifiedBy = 'CodeChecker'
	ws = wb["Sheet"]
	ws.append(["学籍番号", "課題番号", "ソースコード名", "ｺﾝﾊﾟｲﾙ結果", "コンパイル備考", "コンパイルログ", "ﾃｽﾄｹｰｽ", "実行結果", "実行結果備考", "ﾃｽﾄｹｰｽ一致率", "標準出力"])
	for c in list("ABCEFIK"):
		ws.column_dimensions[c].width = 20
	ws.column_dimensions["D"].width = 10
	ws.column_dimensions["G"].width = 7
	ws.column_dimensions["H"].width = 11
	ws.column_dimensions["J"].width = 13
	ws.freeze_panes = "A2" #先頭行を固定
	row = 2
	for res_student in res:
		ws.cell(row=row, column=1).value = res_student["student"]
		for task in res_student["result"]:
			ws.cell(row=row, column=2).value = task["task"]
			if task["src"] is not None:
				ws.cell(row=row, column=3).value = task["src"]
			ws.cell(row=row, column=4).value = valconv(task["compile"]["result"], bool, t = "OK", f = "NG")
			cellfill(ws.cell(row=row, column=4), [("OK", "00b050"),("NG", "e09694")])
			ws.cell(row=row, column=5).value = valconv(task["compile"]["reason"], str, none="")
			ws.cell(row=row, column=6).value = valconv(task["compile"]["stdout"], str, none="")
			if task["run"] is None:
				ws.cell(row=row, column=7).value = "　" #コンパイルログが右のセルにはみ出さないように
				row += 1
				continue
			for i, run in enumerate(task["run"]):
				ws.cell(row=row, column=7).value = task["task"] + "_" + str(i + 1)
				ws.cell(row=row, column=8).value = valconv(run["result"], bool, t="OK", f="NG", none="SKIP")
				cellfill(ws.cell(row=row, column=8), [("OK", "00b050"),("NG", "e09694"),("SKIP", "c5d9f1")])
				ws.cell(row=row, column=9).value = valconv(run["reason"], str, none="")
				ws.cell(row=row, column=10).value = valconv(run["ratio"], float, none="")
				ws.cell(row=row, column=11).value = valconv(run["output"], str, none="")
				row += 1
	path = os.path.join(RESULT_PATH, "result.xlsx")
	while True:
		try:
			wb.save(path)
		except PermissionError:
			print(strcolor(Color.RED, f'File "{path}" is open! Please close the file.'))
			print("Retry in 5 seconds...")
			time.sleep(5)
			continue
		break


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


def eval_loop(students, tasks):
	res = []
	for s in students:
		res_student = []
		for t in tasks:
			r = eval(s, t)
			res_student += [r]
		res += [{"student":s, "result":res_student}]
		if PRINT_SCORE:
			printScore(s, res_student)
	return res


def eval(student, task):
	r = {"task":task["name"], "src":None, "compile":None, "run":None}
	exe = f"{student}_{task["name"]}"
	debug("\n")
	debug(exe, "eval")
	debug("----------------------")
	r["src"] = findLatestSrc(student, task["name"])
	debug(r["src"], "srcfile")
	#コンパイル
	r["compile"] = compile(r["src"], exe)
	debug(r["compile"], "compile")
	if r["compile"]["result"]:
		#実行
		r["run"] = run_loop(exe, task)
		debug(pprint.pformat(r["run"], sort_dicts=False), "run_loop")
	return r


def findLatestSrc(student, taskname):
	#命名条件に合致するファイルが一つもなければNone
	#命名条件に合致するファイルがあれば，評価対象のファイル名
	global srclist
	r = student + "_" + taskname + r"(\([1-9][0-9]*\))?" + ".c"
	src = [x for x in srclist if re.match(r, x)]
	#命名条件に合致するファイルが一つもない -> None
	if len(src) == 0:
		return None
	#チェックしたファイルをソースファイルリストから削除する
	for s in src:
		srclist.remove(s)
	#チェックすべきソースファイルを識別
	if len(src) == 1:
		#候補が一つしかないときは，それがチェックすべきソースファイル
		return src[0]
	else:
		maxnum = 0
		#複数候補がある場合，必ずファイル名に丸括弧が含まれている
		for i in range(len(src)):
			if "(" in src[i]:
				num = int(re.search(r"(\([1-9][0-9]*\))", src[i]).group()[1:-1])
				maxnum = max(num, maxnum)
		return f"{student}_{taskname}({maxnum}).c"


def compile(src, exe):
	res = {"result":True, "reason":None, "stdout":None}
	if src is None:
		res["result"] = False
		res["reason"] = "No File"
		return res
	src_abs = os.path.join(os.path.abspath(SRC_PATH), src)
	exe_abs = os.path.join(os.path.abspath(WORK_PATH), exe + "exe")
	cmd = ["gcc.exe", src_abs, "-o", exe_abs]
	r = subprocess.run(cmd, cwd=GCC_PATH, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,shell=True)
	res["stdout"] = byte2str(r.stdout)
	if r.returncode != 0:
		#コンパイル失敗
		res["result"] = False
		res["reason"] = "Compile Error"
		if res["stdout"] is None:
			res["reason"] += " + Not supported encoding"
	return res


def run_loop(exe, task):
	res = []
	taskfn = task["name"] + "_" + str(task["count"]) + "_"
	for case in task["case"]:
		res += [run(exe, taskfn, case)]
	return res


def run(exe, taskfn, case):
	cmd = exe + ".exe"
	if case["arg"] is not None:
		debug(case["arg"], "arg")
		cmd = cmd + " " + case["arg"]
	res = {"result":None, "reason":None, "output":None, "ratio":None}
	proc = subprocess.Popen(cmd, cwd=WORK_PATH, stdout=subprocess.PIPE, shell=True)
	try:
		r = proc.communicate(timeout=TIMEOUT)
	except subprocess.TimeoutExpired:
		#タイムアウト
		proc.kill()
		debug("Time Out.", "run")
		res["result"] = False
		res["reason"] = "Timeout"
		return res
	res["output"] = byte2str(r[0])  #標準出力のバイトストリームを文字列に変換
	if case["out"] is not None:
		if res["output"] is None:
			res["result"] = False
			res["reason"] = "Stdout encoding error"
			return res
		res["ratio"] = round(difflib.SequenceMatcher(None, res["output"], case["out"], False).ratio(), 3)
		if res["output"] == case["out"]:
			res["result"] = True
		else:
			res["reason"] = "Not matched"
			res["result"] = False
	return res


def printScore(s, res_student):
	output = "Student No.: " + s
	for r in res_student:
		output += "\n\tTask: " + r["task"]
		if r["src"] is not None:
			output += "\n\t\tSourceFile: " + r["src"]
		output += "\n\t\tCompile: " + bool2str(r["compile"]["result"], "OK", "NG")
		if r["compile"]["result"]:
			correct = 0
			failed = 0
			skip = 0
			for i in range(len(r["run"])):
				output += "\n\t\t[" + str(i) + "] -> Result: " + bool2str(r["run"][i]["result"], "OK", "NG", "SKIP")
				if r["run"][i]["result"] is None:
					skip += 1
				elif r["run"][i]["result"] == True:
					correct += 1
				else:
					failed += 1
					if r["run"][i]["reason"] is not None:
						output += f" (Reason: {r['run'][i]['reason']})"
					if r["run"][i]["ratio"] is not None:
						output += f" (Ratio: {r['run'][i]['ratio']})"
			output += f"\n\t\tSummary: {correct}/{correct + failed}  (skip:{skip})"
		else:
			output += " (" + r["compile"]["reason"] + ")"
	print(output + "\n")
	


def chkpath():
	if not os.path.isdir(GCC_PATH):
		error("No gcc directory found.")
	if not os.path.isdir(SRC_PATH):
		error("No source directory found.")
	if not os.path.isdir(WORK_PATH):
		error("No work directory found.")
	if not os.path.isfile(os.path.join(CASE_PATH, "students.txt")):
		error("No student list file found.")
	if not os.path.isfile(os.path.join(CASE_PATH, "tasks.txt")):
		error("No task list file found.")
	if not os.path.isdir(RESULT_PATH):
		error("No result directory found.")


def file2list(filename):
	f = open(filename, 'r', encoding="utf-8")
	l = f.readlines()
	f.close()
	for i in range(len(l)):
		if l[i].strip() == "":
			l.pop(i)
		else:
			l[i] = l[i].rstrip("\n")
	return l


def file2str(filename):
	f = open(filename, 'r', encoding="utf-8")
	s = f.read()
	f.close()
	return s


def readTaskFile(filename):
	l = file2list(filename)
	for i in range(len(l)):
		if re.fullmatch(r'[1-9][0-9]*-((A[1-9])|([1-9][a-z]*)) [1-9]', l[i]):
			temp = l[i].split(" ")
			l[i] = {"name" : temp[0], "count" : int(temp[1]), "case" : []}
		else:
			error("Syntax error in 'tasks.txt'")
	return l


def readCaseFile(l):
	for i in range(len(l)):
		count = l[i]["count"]
		for j in range(count):
			d = {"arg":None, "out":None, "in":None}
			file_arg = os.path.join(CASE_PATH, l[i]["name"] + "_" + str(j) + "_arg.txt")
			file_out = os.path.join(CASE_PATH, l[i]["name"] + "_" + str(j) + "_out.txt")
			file_in = os.path.join(CASE_PATH, l[i]["name"] + "_" + str(j) + "_in.txt")
			if os.path.isfile(file_arg):
				d["arg"] = file2list(file_arg)[0]
			if os.path.isfile(file_out):
				d["out"] = file2str(file_out)
			if os.path.isfile(file_in):
				d["in"] = file2str(file_in)
			l[i]["case"] += [d]
	return l


def byte2str(byte) -> str:
	try:
		#UTF8でデコードする
		s = byte.decode("utf-8")
		s = s.replace("\r\n","\n")
		debug("utf-8", "byte2str")
		return s
	except:
		pass
	try:
		#SJISでデコードする
		s = byte.decode("cp932")
		s = s.replace("\r\n","\n")
		debug("cp932", "byte2str")
		return s
	except:
		pass
	debug("Not supported encoding", "byte2str")
	return None


def bool2str(b, t, f, none = None):
	if b is None:
		return strcolor(Color.BG_CYAN, none)
	elif b:
		return strcolor(Color.BG_BLUE, t)
	else:
		return strcolor(Color.BG_RED, f)


def error(msg, e=True):
	print(strcolor(Color.RED, str(msg)))
	if e:
		sys.exit(1)


def debug(msg, title = None):
	if DEBUG:
		if title is not None:
			print(strcolor(Color.BG_GREEN, title + ":") + strcolor(Color.GREEN, " " + str(msg)))
		else:
			print(strcolor(Color.GREEN, str(msg)))


def chkarg():
	global DEBUG, SRC_PATH, WORK_PATH, CASE_PATH, RESULT_PATH, TIMEOUT, NOCOLOR
	parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
	parser.add_argument("--debug", help="enable debug output", action='store_true')
	parser.add_argument('--src', help="specify source folder", type=str, default=SRC_PATH)
	parser.add_argument('--work', help="specify work folder", type=str, default=WORK_PATH)
	parser.add_argument('--case', help="specify case folder", type=str, default=CASE_PATH)
	parser.add_argument('--result', help="specify result folder", type=str, default=RESULT_PATH)
	parser.add_argument('--timeout', help="specify timeout period for one program execution in seconds.", type=int, default=TIMEOUT)
	parser.add_argument('--nocolor', help="disable colored output", action='store_true')
	args = parser.parse_args()
	DEBUG = args.debug
	SRC_PATH = args.src
	WORK_PATH = args.work
	CASE_PATH = args.case
	RESULT_PATH = args.result
	TIMEOUT = args.timeout
	NOCOLOR = args.nocolor
	debug(f"Source directory: {SRC_PATH}", "chkarg")
	debug(f"Work directory: {WORK_PATH}", "chkarg")
	debug(f"Case directory: {CASE_PATH}", "chkarg")
	debug(f"Result directory: {RESULT_PATH}", "chkarg")
	debug(f"Timeout: {TIMEOUT}s", "chkarg")


def makeSrcFileList():
	global SRC_PATH, srclist
	srclist = [
		f for f in os.listdir(SRC_PATH) if os.path.join(os.path.join(SRC_PATH, f))
	]
	return srclist


class Color:
	RESET = "\033[0m"
	RED = "\033[31m"
	GREEN = "\033[32m"
	YELLOW = "\033[33m"
	BG_RED = "\033[41m"
	BG_GREEN = "\033[42m"
	BG_BLUE = "\033[44m"
	BG_CYAN = "\033[46m"


def strcolor(c, s: str):
	global NOCOLOR
	if NOCOLOR:
		return s
	else:
		return c + s + Color.RESET


if __name__ == "__main__":
	chkarg()
	chkpath()
	main()