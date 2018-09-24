import os, sys, tarfile, zipfile, struct, stat, shutil, subprocess
from GradeReport import GradeReport as GR
from Differ import Differ as Differ

def main():
  if len(sys.argv) < 2:
    invalid_arguments()
    return
  config = read_config_file(sys.argv[1])
  if sys.argv[2] == 'open':
    open_submissions(config)
  elif sys.argv[2] == 'open_student':
    open_student(sys.argv[3], sys.argv[4], config)
  elif sys.argv[2] == 'eval_all':
    eval_all(config)
  elif sys.argv[2] == 'eval_student':
    eval_single_student(sys.argv[3], config)
  else:  # invalid
    invalid_arguments()


def invalid_arguments():
  print('Invalid argument passed in. This program expects 2-3 arguments: (1) the config file; (2) the opration')
  print('Possible operations: open')
  print('\teval_all')
  print('\teval_student <studentname>')


def open_submissions(config):
  # check input paramaters
  expected_files = read_expected_files(config['file_structure'])
  if os.path.exists(config['destination']):
    print('It looks like the folder ' + config['destination'] + ' already exists. Aborting.')
    return
  grade_report = unzip(config['zipfile'], config['destination'], config['total_grade'], config['gold_grade'])
  # check folder structure
  students = get_students('.')
  for student in students:
    os.chdir(student)
    points_off = check_for_nesting(grade_report, student)
    check_for_expected_files(grade_report, student, expected_files, '.', points_off)
    check_for_carriage_returns(grade_report, student, config)
    os.chdir('..')
  # write errors to file
  os.chdir('..')
  write_evaluation(grade_report, config['report'])
  # prepare for running
  sh_files = find_sh_files(expected_files)
  for student in students:
    for sh_file in sh_files:
      if os.path.isfile(student + '/' + sh_file):
        os.chmod(student + '/' + sh_file, stat.S_IXUSR)


def open_student(student_name, student_tar, config): #foldername, file_structure, total_grade, gold_grade, reportname):
  # check input parameters
  expected_files = read_expected_files(config['file_structure'])
  if not os.path.exists(config['destination']):
    print('It looks like the folder ' + config['destination'] + ' doesn\'t exist. Aborting.')
    return
  grade_report = GR.from_file(config['report'])
  # move tar file to student directory and untar
  # if the student directory exists, delete it
  if os.path.exists(config['destination'] + '/' + student_name):
    shutil.rmtree(config['destination'] + '/' + student_name)
  os.mkdir(config['destination'] + '/' + student_name)
  shutil.copyfile(student_tar, config['destination'] + '/' + student_name + '/' + student_tar)
  os.chdir(config['destination'] + '/' + student_name)
  # if student grade exists, remove it
  grade_report.remove_student(student_name)
  grade_report.add_student(student_name, config['total_grade'], config['gold_grade'])
  untar(student_name, grade_report)
  # run normal checks
  points_off = check_for_nesting(grade_report, student_name)
  check_for_expected_files(grade_report, student_name, expected_files, '.', points_off)
  check_for_carriage_returns(grade_report, student_name, config)
  # write to file
  os.chdir('../..')
  write_evaluation(grade_report, config['report'])
  # prepare for running
  for sh_file in find_sh_files(expected_files):
    if os.path.isfile(student_name + '/' + sh_file):
      os.chmod(student_name + '/' + sh_file, stat.S_IXUSR)
  print('I cannot tell if the student submitted a readme separately. Please verify the student\'s readme score.')


# ends up in the unzipped file
def unzip(zipname, foldername, grade_total, gold_grade):
  # unzip canvas file
  zipped = zipfile.ZipFile(zipname, 'r')
  zipped.extractall(foldername)
  zipped.close()
  # reorganize student submissions
  os.chdir(foldername)
  students = set()
  allfiles = os.listdir('.')
  for file in allfiles:
    students.add(file[:file.index('_')])
  for student in students:
    os.mkdir(student)
  for file in allfiles:
    os.rename(file, get_student_name(file) + '/' + get_turnin_name(file))
  # initialize student grades
  grade_report = GR.new(students, grade_total, gold_grade)
  # untar student submissions
  for student in students:
    os.chdir(student)
    untar(student, grade_report)
    os.chdir('..')
  return grade_report


def untar(student, grade_report):
  # check for readme
  readme = None
  for file in os.listdir('.'):
    if 'readme' in file.lower():
      readme = file
  if readme == None:  # no readme
    grade_report.add_error(student, GR.FILES_MODULE_STR, 2, 'No readme found.')
  elif readme[-3:] != 'pdf' and readme[-3:] != 'txt':
    grade_report.add_error(student, GR.FILES_MODULE_STR, 1, 'Readme extension is incorrect: ' + readme)
  # check for tar
  tarname = None
  for file in os.listdir('.'):
    if '.tar' in file:
      tarname = file
      break
  if tarname == None:  # no tar file
    grade_report.add_error(student, GR.FILES_MODULE_STR, 2, 'No tar or gzip file found.')
    return
  if tarname[:2] == 'hw' and tarname[-3:] == '.gz':
    # note: If the readme is also within the tar file, the tar readme will overwrite the original!
    try:
      tar = tarfile.open(tarname)
      tar.extractall('.')
    except (tarfile.TarError, struct.error) as e:
      grade_report.add_error(student, GR.FILES_MODULE_STR, 2,
                             'Tar file was corrupted. Please try a manual open: ' + tarname)
    except (OSError) as e:
      grade_report.add_error(student, GR.FILES_MODULE_STR, 2,
                             'Tar file was corrupted or unopenable. Please try manually opening: ' + tarname)
  elif tarname[-3:] == '.gz' or tarname[-4:] == '.tar':  # this is a tar or gz file
    grade_report.add_error(student, GR.FILES_MODULE_STR, 1, 'Misnamed tar file: ' + tarname)
    try:
      tar = tarfile.open(tarname)
      tar.extractall('.')
    except (tarfile.TarError, struct.error) as e:
      grade_report.add_error(student, GR.FILES_MODULE_STR, 1,
                             'Tar file was corrupted: ' + tarname)  # 1 pt already docked
  else:  # no extractable tar file
    grade_report.add_error(student, GR.FILES_MODULE_STR, 2, 'Tar file not found.')


# returns the # of points taken off
def check_for_nesting(grade_report, student):
  empty_dir = False
  top_directory = '.'
  contents = os.listdir(top_directory)
  # first time is different: there may be a readme file and will definitely be a tar file
  if len(contents) == 2 or len(contents) == 3:
    for file_or_dir in os.listdir(top_directory):
      if os.path.isdir(file_or_dir):
        top_directory = file_or_dir
        empty_dir = True
  while (empty_dir):
    contents = os.listdir(top_directory)
    if len(contents) == 1 and os.path.isdir(top_directory + '/' + contents[0]):
      top_directory = top_directory + '/' + contents[0]
      empty_dir = True
    else:
      empty_dir = False
  # only if we ever recursed
  if top_directory != '.':
    grade_report.add_error(student, GR.FILES_MODULE_STR, 2, 'Incorrectly nested structure inside ' + top_directory)
    for content in contents:
      os.rename(top_directory + '/' + content, content)
    return 2
  return 0


def check_for_expected_files(grade_report, student, expected_structure, actual_dir, points_off):
  errors_list = check_for_expected_files_helper([], expected_structure, actual_dir)
  penalty = float(6) * 1 / count_daughter_files(expected_structure)
  error_sum = points_off
  for error in errors_list:
    if error_sum + penalty > 6:  # max points off for files is 6
      penalty = 6 - error_sum
      error += ' (max points off for file structure reached)'
    error_sum += penalty
    grade_report.add_error(student, GR.FILES_MODULE_STR, penalty, error)
  return


def check_for_expected_files_helper(errors_list, expected_structure, actual_dir):
  pwd_name = actual_dir
  if pwd_name == '.':
    pwd_name = ''
  elif pwd_name[0:2] == './':
    pwd_name = pwd_name[2:] + '/'
  for file_or_dir in expected_structure.keys():
    if expected_structure[file_or_dir] == None:  # file
      if file_or_dir not in os.listdir(actual_dir):
        errors_list.append("File missing or in wrong location: '" + pwd_name + file_or_dir + "'")
    else:  # folder
      if file_or_dir not in os.listdir(actual_dir):  # folder doesn't exist
        num_files_missing = count_daughter_files(expected_structure[file_or_dir])
        errors_list.append("Folder missing or in wrong location: '" + pwd_name + file_or_dir + "' not found.")
      else:  # folder exists
        check_for_expected_files_helper(errors_list, expected_structure[file_or_dir], actual_dir + "/" + file_or_dir)
  return errors_list


# returns a dict view of the dir structure of expected files:
# files are modeled as name -> None
# directories are modeled as name -> dict()
def read_expected_files(fileloc):
  expected_contents = [line.strip() for line in open(fileloc).readlines()]
  expected_contents = [x for x in expected_contents if x != '']  # robust against empty lines
  filelist = dict()
  for content in expected_contents:
    by_directory = content.split('/')
    curr_directory = filelist
    while len(by_directory) > 1:
      next_directory = by_directory[0]
      if next_directory not in curr_directory:
        curr_directory[next_directory] = dict()
      curr_directory = curr_directory[next_directory]
      by_directory = by_directory[1:]
    curr_directory[by_directory[0]] = None
  return filelist


def count_daughter_files(expected_file_structure):
  count = 0
  for file_or_dir in expected_file_structure.keys():
    if expected_file_structure[file_or_dir] == None:
      count += 1
    else:
      count += count_daughter_files(expected_file_structure[file_or_dir])
  return count


def get_student_name(filename):
  return filename[:filename.index('_')]


def get_turnin_name(filename):
  return filename[len(filename) - filename[::-1].index('_'):]


def find_sh_files(expected_file_structure):
  sh_files = []
  for file_or_dir in expected_file_structure.keys():
    if expected_file_structure[file_or_dir] == None:  # file
      if file_or_dir[-3:] == '.sh':  # is an sh file
        sh_files.append(file_or_dir)
    else:  # folder
      sh_files += find_sh_files(expected_file_structure[file_or_dir])
  return sh_files

def write_evaluation(grade_report, reportname):
  outfile = open(reportname, 'w')
  outfile.write(grade_report.pprint())
  outfile.close()


# expected_files a list of tuples [(filename sorted|unsorted) ..]
# test_files a list of tuples [(gold_file test_file sorted|unsorted) ..]
def eval_all(config): #foldername, expected_files, test_files, reportname, gold_grade, ignore_newlines, ignore_whitespace, fuzzy_match):
  grade_report = GR.from_file(config['report'])
  for student in grade_report.get_students():
    eval_student(grade_report, student, config)
  write_evaluation(grade_report, config['report'])


def eval_single_student(student, config):
  grade_report = GR.from_file(config['report'])
  eval_student(grade_report, student, config)
  write_evaluation(grade_report, config['report'])


def eval_student(grade_report, student, config): #grade_report, foldername, student, expected_files, test_files, gold_grade, ignore_newlines, ignore_whitespace, fuzzy_match):
  grade_report.clear_student_modules_except_files(student, config['gold_grade'])
  check_expected_files_ran(grade_report, student, config)
  check_test_files(grade_report, student, config)


def get_students(folder_name):
  return set(os.listdir(folder_name))


def read_config_file(filename):
  config_file = open(filename).readlines()
  config = dict()
  config['cmd'] = 'hw.cmd'
  config['gold_comparison'] = []
  config['repro_comparison'] = []
  gold_comparison_points = 0
  for line in config_file:
    if line == '':
      continue
    elif '=' not in line:
      print("The following line is formatted incorrectly:\n" + line)
      return False
    line_split = [a.strip() for a in line.split('=')]
    attribute = line_split[0]
    value = line_split[1].split()
    if attribute == 'zipfile':
      if not len(value) == 1:
        print("The following line is formatted incorrectly:\n" + line)
        return False
      config['zipfile'] = value[0]
    elif attribute == 'destination':
      if not len(value) == 1:
        print("The following line is formatted incorrectly:\n" + line)
        return False
      config['destination'] = value[0]
    elif attribute == 'report':
      if not len(value) == 1:
        print("The following line is formatted incorrectly:\n" + line)
        return False
      config['report'] = value[0]
    elif attribute == 'cmd':
      if not len(value) == 1:
        print("The following line is formatted incorrectly:\n" + line)
        return False
      config['cmd'] = value[0]
    elif attribute == 'run_script':
      if not len(value) == 1:
        print("The following line is formatted incorrectly:\n" + line)
        return False
      config['run_script'] = value[0]
    elif attribute == 'gold_comparison':
      if not len(value) == 4:
        print("The following line is formatted incorrectly:\n" + line)
        return False
      config['gold_comparison'].append((value[0], value[1], value[2], int(value[3])))
      gold_comparison_points += int(value[3])
    elif attribute == 'repro_comparison':
      if not len(value) == 2:
        print("The following line is formatted incorrectly:\n" + line)
        return False
      config['repro_comparison'].append((value[0], value[1]))
    elif attribute == 'file_structure':
      if not len(value) == 1:
        print("The following line is formatted incorrectly:\n" + line)
        return False
      config['file_structure'] = value[0]
    elif attribute == 'ignore_whitespace':
      if value[0] == 'False' or value[0] == 'false':
        config['ignore_whitespace'] = False
      elif value[0] == 'True' or value[0] == 'true':
        config['ignore_whitespace'] = True
      else:
        print("I don't understand the value for 'ignore_whitespace' " + value[0])
    elif attribute == 'ignore_newlines':
      if value[0] == 'False' or value[0] == 'false':
        config['ignore_newlines'] = False
      elif value[0] == 'True' or value[0] == 'true':
        config['ignore_newlines'] = True
      else:
        print("I don't understand the value for 'ignore_newlines' " + value[0])
    elif attribute == 'fuzzy_match':
      try:
        config['fuzzy_match'] = float(value[0])
      except ValueError:
        print("The value for 'fuzzy_match' is non-numeric: " + value[0] + "\nSkipping this line.")
    else:
      print("I don't understand the following line in from " + filename + ":\n" + line + "Skipping this line.")
      continue
  #set defaults
  if 'ignore_whitespace' not in config:
    config['ignore_whitespace'] = True
    print("Setting ignore_whitespace to default value of True.")
  if 'ignore_newlines' not in config:
    config['ignore_newlines'] = True
    print("Setting ignore_newlines to default value of True.")
  if 'fuzzy_match' not in config:
    config['fuzzy_match'] = 0
    print("Setting fuzzy_match to default value of 0.")
  if 'report' not in config:
    config['report'] = config['destination'] + '_report.txt'  # default is foldername_report.txt
  config['total_grade'] = 25 + gold_comparison_points
  config['gold_grade'] = gold_comparison_points
  return config


def check_for_carriage_returns(grade_report, student, config):
  # really, this only matters for output files -- only go through the output files and check
  expected_files = list()
  for file_tuple in config['repro_comparison']:
    expected_files.append(file_tuple[0])
  for file_tuple in config['gold_comparison']:
    expected_files.append(file_tuple[1])
  carriage_returns = list()
  for expected_file in expected_files:
    if os.path.isfile(expected_file):
      if 'CRLF' in subprocess.check_output('file ' + expected_file, shell=True):
        carriage_returns.append(expected_file)
        os.system('cp ' + expected_file + ' ' + expected_file + '.orig') #preserve file
        os.system('dos2unix ' + expected_file)
  if len(carriage_returns) != 0:
    grade_report.add_error(student, GR.FILES_MODULE_STR, 2, 'Carriage returns found in file(s): ' + ' '.join(carriage_returns))
  return

def check_expected_files_ran(grade_report, student, config): #folder_name, expected_files, ignore_newlines, ignore_whitespace, fuzzy_match):
  number_files = len(config['repro_comparison'])
  for file_tuple in config['repro_comparison']:
    file = config['destination'] + '/' + student + '/' + file_tuple[0]
    if not os.path.isfile(file):
      program_matches_penalty = float(5) / number_files
      grade_report.add_error(student, GR.RUN_MODULE_STR, program_matches_penalty,
                             'No file to match against for file: ' + file_tuple[0])
    if not os.path.isfile(file + '.out'):
      program_runs_penalty = float(10) / number_files
      grade_report.add_error(student, GR.RUN_MODULE_STR, program_runs_penalty,
                             'Program did not run when trying to generate file: ' + file_tuple[0])
    if os.path.isfile(file) and os.path.isfile(file + '.out'):
      sort_file = False
      if file_tuple[1] == 'sorted':
        sort_file = True
      differ = Differ.new(file, file + '.out', file + '.out.diff', config['ignore_newlines'], \
                          config['ignore_whitespace'], sort_file, config['fuzzy_match'])
      diff_lines = differ.compare()
      # take off points and report # of lines different
      program_matches_penalty = float(5) / number_files
      if diff_lines != 0:
        if type(diff_lines) is str:
          grade_report.add_error(student, GR.RUN_MODULE_STR, program_matches_penalty, diff_lines)
        else:
          grade_report.add_error(student, GR.RUN_MODULE_STR, program_matches_penalty, \
          'There are ' + str(diff_lines) + \
          ' lines different between the turned in and locally run versions of ' + \
          file_tuple[0] + '. See ' + file + '.out.diff')


def check_test_files(grade_report, student, config): #folder_name, tested_files, ignore_newlines, ignore_whitespace, fuzzy_match):
  for file_tuple in config['gold_comparison']:
    test_file_path = config['destination'] + '/' + student + '/' + file_tuple[1]
    if not os.path.isfile(file_tuple[0]):
      print("ERROR, gold file " + file_tuple[0] + " does not exist!")
      break
    if not os.path.isfile(test_file_path):
      grade_report.add_error(student, 'Gold Standard Grading', file_tuple[3], 'Did not find output ' + file_tuple[1])
      continue
    # we can assume both files exist now
    sort_file = False
    out_file_ending = '.unsorted.diff'
    if file_tuple[2] == 'sorted':
      sort_file = True
      out_file_ending = '.sorted.diff'
    differ = Differ.new(file_tuple[0], test_file_path, test_file_path + out_file_ending, config['ignore_newlines'], \
                        config['ignore_whitespace'], sort_file, config['fuzzy_match'])
    diff_lines = differ.compare()
    if diff_lines == 0:
      grade_report.add_error(student, 'Gold Standard Grading', 0, file_tuple[1] + ' looks good')
    else:
      if type(diff_lines) is str:
        grade_report.add_error(student, 'Gold Standard Grading', file_tuple[3], diff_lines)
      else:
        grade_report.add_error(student, 'Gold Standard Grading', file_tuple[3], \
                             str(diff_lines) + ' lines different from the gold file for ' + \
                             file_tuple[1] + ': see ' + test_file_path + out_file_ending)

if __name__ == "__main__":
  main()
