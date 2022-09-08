#!/usr/bin/env python3
# This Source Code Form is licensed MPL-2.0: http://mozilla.org/MPL/2.0
import sys, getopt, re, os

# V1: -k, -d, -p works for `no|<number>{y|m|w|d|h}|latest|all`

from enum import Enum
class Classification(Enum):
  # id, multi-valued-slot-flag
  UNKNOWN = (0, False)
  DISCARD = (1, False)
  NONE    = (2, False)
  ALL     = (3, False)
  LATEST  = (4, False)
  HOUR    = (5, True)
  DAY     = (6, True)
  WEEK    = (7, True)
  MONTH   = (8, True)
  YEAR    = (10, True)

import datetime
now = datetime.datetime.now()

# Parser for retention configuration
# Syntax: no|<number>{y|m|w|d|h}|latest|all
class Retention:
  def asint (self, string):
    if string == '*':
      return 9999
    return int (string)
  def __init__ (self, string):
    self.none = False
    self.latest = False
    self.all = False
    self.yearly = 0
    self.monthly = 0
    self.weekly = 0
    self.daily = 0
    self.hourly = 0
    self.dayofweek = 6
    for word in string.split():
      m = re.match (r'(\d+y)|(\d+m)|(\d+w)|(\d+d)|(\d+h)|(latest)|(all)|(no)', word)
      if not m:         continue
      elif m[1]:        self.yearly = self.asint (m[1][:-1])
      elif m[2]:        self.monthly = self.asint (m[2][:-1])
      elif m[3]:        self.weekly = self.asint (m[3][:-1])
      elif m[4]:        self.daily = self.asint (m[4][:-1])
      elif m[5]:        self.hourly = self.asint (m[5][:-1])
      elif m[6]:        self.latest = True
      elif m[7]:        self.all = True
      elif m[8]:        self.none = True
  def __repr__ (self):
    s = []
    if self.all:      s += [ 'all' ]
    if self.latest:   s += [ 'latest' ]
    if self.hourly:   s += [ str (self.hourly) + 'h' ]
    if self.daily:    s += [ str (self.daily) + 'd' ]
    if self.weekly:   s += [ str (self.weekly) + 'w' ]
    if self.monthly:  s += [ str (self.monthly) + 'm' ]
    if self.yearly:   s += [ str (self.yearly) + 'y' ]
    if self.none:     s += [ 'no' ]
    return ' '.join (s)

# Extract date & time from a filename
def namedatetime (name):
  bname = os.path.basename (name)
  # ignore partial backups
  ignores = ('.part', '.tmp', '.temp')
  for pat in ignores:
    if bname.find (pat) >= 0:
      return None
  # match 19991231T2359
  digits = re.search (r'(?<!\d)(\d\d\d\d)(\d\d)(\d\d)[^\d]?(\d\d)(\d\d)(?!\d)', bname)
  if digits:
    yyyy, mm, dd, hh, ii = digits[1], digits[2], digits[3], digits[4], digits[5]
    return datetime.datetime (int (yyyy), int (mm), int (dd), int (hh), int (ii))
  # match 19991231
  digits = re.search (r'(?<!\d)(\d\d\d\d)(\d\d)(\d\d)(?!\d)', bname)
  if digits:
    yyyy, mm, dd = digits[1], digits[2], digits[3]
    return datetime.datetime (int (yyyy), int (mm), int (dd), 12, 0)
  return None

# Filename with datetime if any was recognized
class Backup:
  def __init__ (self, name):
    self.name = name
    self.filetime = namedatetime (name)
  def __repr__ (self):
    return 'Backup' + str ((self.filetime, self.name))

# Backup age, possibly with associated backup filename
class Slot:
  def __init__ (self, bound):
    self.bound = bound;
    self.backup = None
  def __repr__ (self):
    return 'Slot' + str ((self.bound, self.backup))

# Helper to for month-=1 in a datetime object
def subtract_month (dtime):
  if dtime.month == 1:
    next = dtime.replace (year = dtime.year - 1, month = 12)
  else:
    next = dtime.replace (month = dtime.month - 1)
  return next

# Sort backups into slots according to a retention policy
class BackupCollector:
  def __init__ (self, retention):
    # prepare slots
    self.latestb = None
    self.hours = []
    self.days = []
    self.weeks = []
    self.months = []
    self.years = []
    self.retention = retention
    self.collection = set()
    self.configure()
  def add_to_slots (self, slotlist, backup):
    for slot in slotlist:
      if backup.filetime >= slot.bound and (not slot.backup or backup.filetime < slot.backup.filetime):
        slot.backup = backup
  def find_in_slots (self, slotlist, name):
    for slot in slotlist:
      if slot.backup and name == slot.backup.name:
        return True
    return False
  def configure (self):
    dtime_now = datetime.datetime.now()
    # hour slots
    if self.retention.hourly:
      bound = datetime.datetime (now.year, now.month, now.day, now.hour, 0)
      for i in range (self.retention.hourly + 1):
        self.hours += [ Slot (bound) ]
        bound -= datetime.timedelta (hours = 1)
    # day slots
    if self.retention.daily:
      bound = datetime.datetime (now.year, now.month, now.day, 0, 0)
      for i in range (self.retention.daily + 1):
        self.days += [ Slot (bound) ]
        bound -= datetime.timedelta (days = 1)
    # week slots
    if self.retention.weekly:
      dayofweek = self.retention.dayofweek
      #bound = datetime.datetime (now.year, now.month, now.day - now.weekday() + dayofweek, 0, 0)
      bound = datetime.datetime (now.year, now.month, now.day, 0, 0)
      bound += datetime.timedelta (days = - now.weekday() + dayofweek)
      if dayofweek > now.weekday(): # shift date out of the future
        bound -= datetime.timedelta (days = 7)
      for i in range (self.retention.weekly + 1):
        self.weeks += [ Slot (bound) ]
        bound = bound - datetime.timedelta (days = 7)
    # month slots
    if self.retention.monthly:
      bound = datetime.datetime (now.year, now.month, 1, 0, 0)
      for i in range (self.retention.monthly + 1):
        self.months += [ Slot (bound) ]
        bound = subtract_month (bound)
    # year slots
    for i in range (self.retention.yearly + 1):
      bound = datetime.datetime (now.year - i, 1, 1, 0, 0)
      self.years += [ Slot (bound) ]
  def feed (self, name):
    b = Backup (name)
    if not b.filetime:
      return False
    self.collection.add (name)
    if not self.latestb or b.filetime > self.latestb.filetime:
      self.latestb = b
    self.add_to_slots (self.hours, b)
    self.add_to_slots (self.days, b)
    self.add_to_slots (self.weeks, b)
    self.add_to_slots (self.months, b)
    self.add_to_slots (self.years, b)
    return True
  def collect (self, nlist):
    for name in nlist:
      self.feed (name)
  def classify (self, name, slotprefix = ''):
    if not name in self.collection:                     return Classification.UNKNOWN
    if self.retention.all:                              return Classification.ALL
    if self.retention.none:                             return Classification.NONE
    if self.latestb and self.latestb.name == name:      return Classification.LATEST
    if self.find_in_slots (self.hours, name):           return Classification.HOUR
    if self.find_in_slots (self.days, name):            return Classification.DAY
    if self.find_in_slots (self.weeks, name):           return Classification.WEEK
    if self.find_in_slots (self.months, name):          return Classification.MONTH
    if self.find_in_slots (self.years, name):           return Classification.YEAR
    else:                                               return Classification.DISCARD

# Arguments
usage0 = 'Usage: aging.py [Options] [pathnames...]'
usage1 = '''
Use the `--keep` or `--discard` arguments to filter a given set of
`pathnames` according to a retention policy.
OPTIONS:
'''
argdefs = (
  ('-h', '--help',    '',            'Print usage information'),
  ('-d', '--discard', '<RETENTION>', 'List all filenames to be discarded'),
  ('-k', '--keep',    '<RETENTION>', 'List all filenames to be kept'),
  ('-p', '--print',   '<RETENTION>', 'Print retention reason'),
)
usage2 = '''
RETENTION:
Specify retention filters in terms of year/month/week/day/hour file ages
using a single letter postfix, and via the keywords `none`, `latest`, `all`.
Multiple policies can be combined by using space as a separator. Detailed
policy syntax: `no|<number>{y|m|w|d|h}|latest|all`
'''

def usage (short = False):
  print (usage0.strip())
  if short:
    return
  if usage1:
    print (usage1.strip())
  for arg in argdefs:
    opt = ''
    if arg[0]: opt += arg[0]
    if arg[1]: opt += (', ' if opt else '') + arg[1]
    if arg[2]: opt += ' ' + arg[2]
    opt = '  ' + opt
    col = 20 - 1
    if len (opt) > col:
      print (opt)
      print (' ' * col, arg[3])
    else:
      print ('%-{col}s'.format (col = col) % opt, arg[3])
  if usage2:
    print (usage2.strip())

def process_args (args):
  short_options, long_options = '', []
  for arg in argdefs:
    if arg[0]: short_options +=   arg[0].lstrip ('-') + (':' if arg[2] else '')
    if arg[1]: long_options  += [ arg[1].lstrip ('-') + ('=' if arg[2] else '') ]
  options, arguments = getopt.gnu_getopt (args, short_options, long_options)
  config = { 'keep': '', 'discard': '', 'print': '' }
  for k,v in options:
    if   k in ('-h', '--help'):         usage(); sys.exit (0)
    elif k in ('-k', '--keep'):         config['keep'] = v
    elif k in ('-d', '--discard'):      config['discard'] = v
    elif k in ('-p', '--print'):        config['print'] = v
  config['filenames'] = arguments
  return config

# Arguments
config = process_args (sys.argv[1:])

# --keep
if config['keep']:
  retention = Retention (config['keep'])
  collector = BackupCollector (retention)
  collector.collect (config['filenames'])
  for name in sorted (config['filenames']):
    cls = collector.classify (name)
    if cls in (Classification.UNKNOWN, Classification.DISCARD, Classification.NONE):
      continue
    print (name)

# --discard
if config['discard']:
  retention = Retention (config['discard'])
  collector = BackupCollector (retention)
  collector.collect (config['filenames'])
  for name in sorted (config['filenames']):
    cls = collector.classify (name)
    if cls in (Classification.DISCARD, Classification.NONE):
      print (name)

# --print
if config['print']:
  retention = Retention (config['print'])
  collector = BackupCollector (retention)
  collector.collect (config['filenames'])
  print ('%-15s' % 'Retaining:', str (retention))
  for name in sorted (config['filenames']):
    cls = collector.classify (name)
    print ('%-15s' % (('first of ' if cls._value_[1] else '') + cls._name_), name)

# fallback
if not config['keep'] + config['discard'] + config['print']:
  usage (short = True)
