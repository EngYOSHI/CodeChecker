import subprocess
import os
import sys
import re
import pprint
import difflib

DEBUG = True
PRINT_SCORE = True
GCC_PATH = "./mingw64/bin/"
SRC_PATH = "./src/"
WORK_PATH = "./work/"
CASE_PATH = "./case/"
TIMEOUT = 10


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



def compile(src: str) -> (bool, str):
	src_abs = os.path.abspath(SRC_PATH) + "/" +src
	exe_abs = os.path.abspath(WORK_PATH) + "/" + src + ".exe"
	res = {"result":True, "reason":None, "stdout":None}
	if not os.path.isfile(src_abs):
		res["result"] = False
		res["reason"] = "No File"
		return res
	cmd = ["gcc.exe", src_abs, "-o", exe_abs]
	r = subprocess.run(cmd, cwd=GCC_PATH, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,shell=True, encoding="utf8", text=True)
	res["stdout"] = r.stdout
	if r.returncode != 0:
		#コンパイル失敗
		res["result"] = False
		res["reason"] = "Compile Error"
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
	res = {"result":None, "output":"", "ratio":None}
	proc = subprocess.Popen(cmd, cwd=WORK_PATH, stdout=subprocess.PIPE, shell=True, encoding="utf8", text=True)
	try:
		r = proc.communicate(timeout=TIMEOUT)
	except subprocess.TimeoutExpired:
		#タイムアウトの時はratioが-1
		proc.kill()
		debug("Time Out.", "run")
		res["result"] = False
		res["ratio"] = -1
		return res
	res["output"] = r[0]
	if case["out"] is not None:
		res["ratio"] = difflib.SequenceMatcher(None, r[0], case["out"], False).ratio()
		if r[0] == case["out"]:
			res["result"] = True
		else:
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
					if r["run"][i]["ratio"] == -1:
						output += f" (TimeOut)"
					else:
						output += f" (Ratio: {round(r["run"][i]["ratio"], 2)})"
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


def bool2str(b, t, f, none = None):
	if b is None:
		return "\033[46m" + none + "\033[0m"
	elif b:
		return "\033[44m" + t + "\033[0m"
	else:
		return "\033[41m" + f + "\033[0m"


def error(msg, e=True):
	print("\033[31mError: " + str(msg) + "\033[0m")
	if e:
		sys.exit(1)


def debug(msg, title = None):
	if DEBUG:
		if title is not None:
			print("\033[42m" + str(title) + ":\033[0m\033[32m " + str(msg) + "\033[0m")
		else:
			print("\033[32m" + str(msg) + "\033[0m")


if __name__ == "__main__":
	chkpath()
	main()