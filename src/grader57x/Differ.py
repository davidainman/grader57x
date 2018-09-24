import os

class Differ:
  ACTUAL = ''
  GOLD = ''
  OUTPUT = ''
  IGNORE_NEWLINES = True
  SPLIT_SPACING = True
  SORT_FILE = False
  FUZZY_MATCH = float(0)
  LOOKAHEAD_VALUE = 10
  #TODO do something with sort_file

  def __init__(self, gold_loc, actual_loc, output_loc, ignore_newlines, split_spacing, sort_file, fuzzy_match):
    self.ACTUAL = actual_loc
    self.GOLD = gold_loc
    self.OUTPUT = output_loc
    self.IGNORE_NEWLINES = ignore_newlines
    self.SPLIT_SPACING = split_spacing
    self.SORT_FILE = sort_file
    self.FUZZY_MATCH = fuzzy_match

  @classmethod
  def new(cls, gold_loc, actual_loc, output_loc, ignore_newlines, split_spacing, sort_file, fuzzy_match):
    differ = cls(gold_loc, actual_loc, output_loc, ignore_newlines, split_spacing, sort_file, fuzzy_match)
    return differ

  def compare(self):
    # if this is the second run, blow away the previous output
    if os.path.isfile(self.OUTPUT):
      os.remove(self.OUTPUT)
    # check to see if expected file exists
    if not os.path.isfile(self.ACTUAL):
      return(self.ACTUAL + ' not found')
    # check to see if expected file is non-zero
    if os.path.getsize(self.ACTUAL) == 0:
      return(self.ACTUAL + ' is empty')
    # file is nonzero
    gold_file = self.GOLD
    actual_file = self.ACTUAL
    if self.SORT_FILE:
      actual_file = self.ACTUAL + '.sorted'
      #don't call unix sort multiple times on rerun
      if not os.path.isfile(actual_file):
        os.system('sort ' + self.ACTUAL + ' > ' + actual_file)
      #if it's still not there something went wrong, probably permissions
      if not os.path.isfile(actual_file): #there was an error in creating the sorted file
        return('ERROR: Was unable to sort the file ' + self.ACTUAL)
    gold_buffer = list()
    actual_buffer = list()
    compare_memory = dict()
    gold_counter = 1
    actual_counter = 1
    different_lines = 0
    with open(self.GOLD, 'r') as g, open(self.ACTUAL, 'r') as a, open(self.OUTPUT, 'w') as w:
      #pre-populate buffer
      for i in range(self.LOOKAHEAD_VALUE):
        gold_buffer.append(g.readline())
        actual_buffer.append(a.readline())
      #when the buffer is empty, we're done (readline() returns '' at EOF, bool('') is false)
      while gold_buffer[0] or actual_buffer[0]:
        if self.IGNORE_NEWLINES:
          while gold_buffer[0] is '\n' or gold_buffer[0].isspace():
            gold_buffer.append(g.readline())
            gold_buffer.pop(0)
            gold_counter += 1
          while actual_buffer[0] is '\n' or actual_buffer[0].isspace():
            actual_buffer.append(a.readline())
            actual_buffer.pop(0)
            actual_counter += 1
        #check compare_memory first
        diffed = compare_memory.get(str(gold_counter)+'-'+str(actual_counter))
        if diffed is None:
          diffed = self.compare_line(gold_buffer[0], actual_buffer[0], gold_counter, actual_counter)
          compare_memory[str(gold_counter)+'-'+str(actual_counter)] = diffed
        if diffed is not False: 
          #check buffer to see if the lines match later
          #first check by advancing the gold
          gold_matches = False
          actual_matches = False
          for i in range(1,len(gold_buffer)):
            #check compare_memory first
            compare = compare_memory.get(str(gold_counter)+'-'+str(actual_counter))
            if compare == None:
              compare = self.compare_line(gold_buffer[i], actual_buffer[0], gold_counter + i, actual_counter)
              compare_memory[str(gold_counter)+'-'+str(actual_counter)] = compare
            if not compare:
              gold_matches = i
              break
          if gold_matches is not False: #by advancing gold_buffer we get back on track, gold_counter + gold_matches matches
            w.write("EXPECTED LINES MISSING: " + self.GOLD + ":" + str(gold_counter) + "-" + str(gold_counter+gold_matches-1) + "\n" + \
             "EXPECTED LOCATION: " + self.ACTUAL + ":" + str(actual_counter) + "\n" + \
             "\n++++++++++++\n" + ''.join(gold_buffer[0:gold_matches]) + "\n------------------------\n")
            for i in range(gold_matches):
              gold_buffer.append(g.readline())
              gold_buffer.pop(0)
            gold_counter += gold_matches #now they match
            different_lines += gold_matches-1
            continue # TODO remove this line after testing
          #now check by advancing the actual
          else: #don't do this if gold_matches worked
            for i in range(1, len(actual_buffer)):
              #check compare_memory first
              compare = compare_memory.get(str(gold_counter)+'-'+str(actual_counter))
              if compare == None:
                compare = compare_line(gold_buffer[0], actual_buffer[i], gold_counter, actual_counter + i)
                compare_memory[str(gold_counter)+'-'+str(actual_counter)] = compare
              if not compare:
                actual_matches = i
                break
            if actual_matches is not False: #by advancing actual_buffer we get back on track, actual_counter + actual_matches matches
              w.write("ADDITIONAL LINES INSERTED: " + self.ACTUAL + ":" + str(actual_counter) + "-" + str(actual_counter+actual_matches-1) + "\n" + \
               "\n++++++++++++\n" + ''.join(actual_buffer[0:actual_matches]) + "\n------------------------\n")
              for i in range(actual_matches):
                actual_buffer.append(a.readline())
                actual_buffer.pop(0)
              actual_counter += actual_matches #now they match
              different_lines += actual_matches-1
              continue # TODO remove this line after testing
          #this if statement should be superfluous but just in case
          if gold_matches == False and actual_matches == False:
            w.write(diffed)
            different_lines += 1
        #increment the buffer
        gold_buffer.append(g.readline())
        gold_buffer.pop(0)
        gold_counter += 1
        actual_buffer.append(a.readline())
        actual_buffer.pop(0)
        actual_counter += 1
      return different_lines   
    
  def compare_line(self, gold_line, actual_line, gold_line_number, actual_line_number):
    if self.SPLIT_SPACING:
      return self.compare_line_ignore_spacing(gold_line, actual_line, gold_line_number, actual_line_number)
    else:
      return self.compare_line_with_spacing(gold_line, actual_line, gold_line_number, actual_line_number) 

  def compare_line_with_spacing(self, gold_line, actual_line, gold_line_number, actual_line_number):
    if gold_line != actual_line:
      if not self.SORT_FILE:
        return "EXPECTED (" + self.GOLD + ":" + str(gold_line_number) + "): " + gold_line.strip() + "\n" + \
               "ACTUAL (" + self.ACTUAL + ":" + str(actual_line_number) + "): " + actual_line.strip() + "\n"
      else: #need to let the user know the files have been sorted
        return "EXPECTED (" + self.GOLD + "): " + gold_line.strip() + "\n" + \
               "ACTUAL (" + self.ACTUAL + "): " + actual_line.strip() + "\n" + \
               "(Files were sorted prior to the comparison)\n"
    else:
      return False

  def compare_line_ignore_spacing(self, gold_line, actual_line, gold_line_number, actual_line_number):
    gold_compare = gold_line.split()
    actual_compare = actual_line.split()
    while ('' in gold_compare):
      gold_compare.remove('')
    while('' in actual_compare):
      actual_compare.remove('')
    diff = False
    expected = ""
    actual = ""
    longest_len = len(gold_compare)
    if len(actual_compare) > longest_len:
      longest_len = len(actual_compare)
    for x in range(0, longest_len):
      this_is_diff = False
      g_c = ''
      a_c = ''
      if x < len(gold_compare):
        g_c = gold_compare[x]
      if x < len(actual_compare):
        a_c = actual_compare[x]
      if is_number(g_c) and is_number(a_c): #numerical compare
        # edge case where the expected value is 0
        if float(a_c) == 0:
          if float(g_c) == 0: #0 = 0
            this_is_diff = False
          elif abs(float(g_c) - float(a_c)) / float(g_c) > self.FUZZY_MATCH: #safe for g_c to be denominator
            diff = True
            this_is_diff = True
        elif abs(float(a_c) - float(g_c))/float(a_c) > self.FUZZY_MATCH: #safe for a_c to be the denominator
          diff = True
          this_is_diff = True
      elif g_c != a_c: #non-numerical compare
        diff = True
        this_is_diff = True
      if this_is_diff:
        expected += " " + g_c
        actual += " " + a_c
    if diff:
      if not self.SORT_FILE:
        return "EXPECTED: (" + self.GOLD + ":" + str(gold_line_number) + "): " + expected + "\n" + \
               "ACTUAL: (" + self.ACTUAL + ":" + str(actual_line_number) + "): " + actual + "\n++++++++++++\n" + \
             self.GOLD + ":" + str(gold_line_number) + ": " + gold_line.strip() + "\n" + \
             self.ACTUAL + ":" + str(actual_line_number) + ": " + actual_line.strip() + "\n------------------------\n"
      else: #need to let the grader know the files were sorted
        return "EXPECTED: (" + self.GOLD + "): " + expected + "\n" + \
               "ACTUAL: (" + self.ACTUAL + "): " + actual + "\n++++++++++++\n" + \
             self.GOLD + ":" + str(gold_line_number) + ": " + gold_line.strip() + "\n" + \
             self.ACTUAL + ":" + str(actual_line_number) + ": " + actual_line.strip() + "\n" + \
             "(Files were sorted prior to comparison)\n------------------------\n"
    else:
      return False


def is_number(s):
  try:
    float(s)
    return True
  except ValueError:
    return False