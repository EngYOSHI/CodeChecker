import subprocess
import os
import sys

DEBUG = True
GCC_PATH = r".\mingw64\bin"
SRC_PATH = r".\src"
WORK_PATH = r".\work"
STUDENT_PATH = r".\student_list.txt"
TASK_PATH = r".\task_list.txt"


def main():
	students = file2list(STUDENT_PATH)
	print("Number of Students: " + str(len(students)))
	debug(students)
	tasks = file2list(TASK_PATH)
	print("Number of tasks: " + str(len(tasks)))
	debug(tasks)
	eval_loop(students, tasks)


def eval_loop(students, tasks):
	for s in students:
		for t in tasks:
			eval(s + "_" + t + ".c")


def eval(src):
	debug("\neval(" + src + ")\n--------------------")
	res_compile = compile(src)
	debug(res_compile)



def compile(src: str) -> (bool, str):
	src_abs = os.path.abspath(SRC_PATH) + "\\" + src
	work_abs = os.path.abspath(WORK_PATH) + "\\" + src + ".exe"
	if not os.path.isfile(src_abs):
		return (False, "No File.")
	cmd = ["gcc.exe", src_abs, "-o", work_abs]
	res = subprocess.run(cmd, cwd=GCC_PATH, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,shell=True,universal_newlines=True)
	if res.returncode == 0:
		#コンパイル成功
		return (True, res.stdout)
	else:
		#コンパイル失敗
		return (False, res.stdout)
	
	
def chkpath():
	if not os.path.isdir(GCC_PATH):
		error("No gcc directory found.")
	if not os.path.isdir(SRC_PATH):
		error("No source directory found.")
	if not os.path.isdir(WORK_PATH):
		error("No work directory found.")
	if not os.path.isfile(STUDENT_PATH):
		error("No student list file found.")
	if not os.path.isfile(TASK_PATH):
		error("No task list file found.")


def file2list(filename):
	f = open(filename, 'r')
	l = f.readlines()
	f.close()
	for i in range(len(l)):
		l[i] = l[i].rstrip("\n")
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