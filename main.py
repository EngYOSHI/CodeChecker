import subprocess
import os
import sys
import re
import pprint
import difflib
import argparse

DEBUG = False
PRINT_SCORE = True
GCC_PATH = "mingw64/bin/"
SRC_PATH = "src/"
WORK_PATH = "work/"
CASE_PATH = "case/"
TIMEOUT = 5
NOCOLOR = False


def main():
	students = file2list(CASE_PATH + "students.txt")
	print("Number of Students: " + str(len(students)))
	debug(students)
	tasks = readTaskFile(CASE_PATH + "tasks.txt")
	print("Number of tasks: " + str(len(tasks)))
	tasks = readCaseFile(tasks)
	debug(pprint.pformat(tasks, sort_dicts=False))
	eval_loop(students, tasks)
	


def eval_loop(students, tasks):
	for s in students:
		res_student = []
		for t in tasks:
			r = {"task": t["name"], "compile": None, "run":None}
			r["compile"], r["run"] = eval(s, t)
			res_student += [r]
		if PRINT_SCORE:
			printScore(s, res_student)
		#pprint.pprint(res_student, sort_dicts=False)
		#ここでcsv書き出し関数を呼び出す
			


def eval(s, t):
	src = s + "_" + t["name"] + ".c"
	debug("\neval(" + src + ")\n--------------------")
	res_compile = compile(src)
	debug(res_compile, "compile")
	res_run = None
	if res_compile["result"]:
		res_run = run_loop(src, t)
		debug(pprint.pformat(res_run, sort_dicts=False), "res_run")
	return res_compile, res_run



def compile(src: str):
	src_abs = os.path.abspath(SRC_PATH) + "/" +src
	exe_abs = os.path.abspath(WORK_PATH) + "/" + src + ".exe"
	res = {"result":True, "reason":None, "stdout":None}
	if not os.path.isfile(src_abs):
		res["result"] = False
		res["reason"] = "No File"
		return res
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


def run_loop(src, task):
	res = []
	taskfn = task["name"] + "_" + str(task["count"]) + "_"
	for case in task["case"]:
		res += [run(src, taskfn, case)]
	return res


def run(src, taskfn, case):
	cmd = src + ".exe"
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
		res["ratio"] = difflib.SequenceMatcher(None, res["output"], case["out"], False).ratio()
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
						output += f" (Ratio: {round(r['run'][i]['ratio'], 2)})"
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
	if not os.path.isfile(CASE_PATH + "students.txt"):
		error("No student list file found.")
	if not os.path.isfile(CASE_PATH + "tasks.txt"):
		error("No task list file found.")


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
			file_arg = CASE_PATH + l[i]["name"] + "_" + str(j) + "_arg.txt"
			file_out = CASE_PATH + l[i]["name"] + "_" + str(j) + "_out.txt"
			file_in = CASE_PATH + l[i]["name"] + "_" + str(j) + "_in.txt"
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
			print(strcolor(Color.BG_GREEN, title + ":") + strcolor(Color.GREEN, str(msg)))
		else:
			print(strcolor(Color.GREEN, str(msg)))


def chkarg():
	global DEBUG, SRC_PATH, WORK_PATH, CASE_PATH, TIMEOUT, NOCOLOR
	parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
	parser.add_argument("--debug", help="enable debug output", action='store_true')
	parser.add_argument('--src', help="specify source folder", type=str, default=SRC_PATH)
	parser.add_argument('--work', help="specify work folder", type=str, default=WORK_PATH)
	parser.add_argument('--case', help="specify case folder", type=str, default=CASE_PATH)
	parser.add_argument('--timeout', help="specify timeout period for one program execution in seconds.", type=int, default=TIMEOUT)
	parser.add_argument('--nocolor', help="disable colored output", action='store_true')
	args = parser.parse_args()
	DEBUG = args.debug
	SRC_PATH = adddelimiter(args.src)
	WORK_PATH = adddelimiter(args.work)
	CASE_PATH = adddelimiter(args.case)
	TIMEOUT = args.timeout
	NOCOLOR = args.nocolor
	debug(f"Source directory: {SRC_PATH}", "chkarg")
	debug(f"Work directory: {WORK_PATH}", "chkarg")
	debug(f"Case directory: {CASE_PATH}", "chkarg")
	debug(f"Timeout: {TIMEOUT}s", "chkarg")


def adddelimiter(s: str):
	if "/" in s and s[-1] != "/":
		s += "/"
	elif "\\" in s and s[-1] != "\\":
		s += "\\"
	elif "\\" not in s and "/" not in s:
		s += "/"
	return s


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