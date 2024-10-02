import subprocess
import os
import sys
import re
import pprint
import difflib

DEBUG = True
GCC_PATH = "./mingw64/bin/"
SRC_PATH = "./src/"
WORK_PATH = "./work/"
CASE_PATH = "./case/"


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
	r = subprocess.run(cmd, cwd=GCC_PATH, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,shell=True,text=True)
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
	r = subprocess.run(cmd, cwd=WORK_PATH, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,shell=True,text=True)
	res = {"result":None, "output":r.stdout, "ratio":None}
	if case["out"] is not None:
		res["ratio"] = difflib.SequenceMatcher(None, r.stdout, case["out"], False).ratio()
		if r.stdout == case["out"]:
			res["result"] = True
		else:
			res["result"] = False
	return res


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