#!/usr/bin/env python
# Copyright (C) 2008,2011 Lanedo GmbH
#
# Author: Tim Janik
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
import sys, os, re, urllib, csv
pkginstall_configvars = {
  'VERSION' : '0.0'
  #@PKGINSTALL_CONFIGVARS_IN24LINES@ # configvars are substituted upon script installation
}

# TODO:
# - support mixing in comments.txt which has "bug# person: task"

bugurls = (
  ('gb',        	'http://bugzilla.gnome.org/buglist.cgi?bug_id='),
  ('gnome',     	'http://bugzilla.gnome.org/buglist.cgi?bug_id='),
  ('fd',        	'https://bugs.freedesktop.org/buglist.cgi?bug_id='),
  ('freedesktop',	'https://bugs.freedesktop.org/buglist.cgi?bug_id='),
  ('mb',        	'https://bugs.maemo.org/buglist.cgi?bug_id='),
  ('maemo',     	'https://bugs.maemo.org/buglist.cgi?bug_id='),
  ('nb',        	'https://projects.maemo.org/bugzilla/buglist.cgi?bug_id='),
  ('nokia',     	'https://projects.maemo.org/bugzilla/buglist.cgi?bug_id='),
  ('gcc',       	'http://gcc.gnu.org/bugzilla/buglist.cgi?bug_id='),
  ('libc',      	'http://sources.redhat.com/bugzilla/buglist.cgi?bug_id='),
  ('moz',       	'https://bugzilla.mozilla.org/buglist.cgi?bug_id='),
  ('mozilla',   	'https://bugzilla.mozilla.org/buglist.cgi?bug_id='),
  ('xm',                'http://bugzilla.xamarin.com/buglist.cgi?id='),
  ('xamarin',           'http://bugzilla.xamarin.com/buglist.cgi?id='),
)

# URL authentication handling
def auth_urls():
  import ConfigParser, os, re
  cp = ConfigParser.SafeConfigParser()
  cp.add_section ('authentication-urls')
  cp.set ('authentication-urls', 'urls', '')
  cp.read (os.path.expanduser ('~/.urlrc'))
  urlstr = cp.get ('authentication-urls', 'urls') # space separated url list
  urls = re.split ("\s*", urlstr.strip())         # list urls
  urls = [u for u in urls if u]                   # strip empty urls
  global auth_urls; auth_urls = lambda : urls     # cache result for the future
  return urls
def add_auth (url):
  for ai in auth_urls():
    prefix = re.sub ('//[^:/@]*:[^:/@]*@', '//', ai)
    if url.startswith (prefix):
      pl = len (prefix)
      return ai + url[pl:]
  return url

# carry out online bug queries
def bug_summaries (buglisturl):
  if not buglisturl:
    return []
  # Bugzilla query to use
  query = buglisturl + '&ctype=csv' # buglisturl.replace (',', '%2c')
  query = add_auth (query)
  f = urllib.urlopen (query)
  csvdata = f.read()
  f.close()
  # read CSV lines
  reader = csv.reader (csvdata.splitlines (1))
  # parse head to interpret columns
  col_bug_id = -1
  col_description = -1
  header = reader.next()
  i = 0
  for col in header:
    col = col.strip()
    if col == 'bug_id':
      col_bug_id = i
    if col == 'short_short_desc':
      col_description = i
    elif col_description < 0 and col == 'short_desc':
      col_description = i
    i = i + 1
  if col_bug_id < 0:
    print >>sys.stderr, 'Failed to identify bug_id from CSV data'
    sys.exit (11)
  if col_description < 0:
    print >>sys.stderr, 'Failed to identify description columns from CSV data'
    sys.exit (12)
  # parse bug list
  result = []
  summary = ''
  for row in reader:
    bug_number = row[col_bug_id]
    description = row[col_description]
    result += [ (bug_number, description) ]
  return result

# parse bug numbers and list bugs
def read_handle_bugs (config, url):
  lines = sys.stdin.read()
  # print >>sys.stderr, 'Using bugzilla URL: %s' % (bz, url)
  for line in [ lines ]:
    # find all bug numbers
    bugs = re.findall (r'\b[0-9]+\b', line)
    # int-convert, dedup and sort bug numbers
    ibugs = []
    if bugs:
      bught = {}
      for b in bugs:
        b = int (b)
        if not b or bught.has_key (b): continue
        bught[b] = True
        ibugs += [ b ]
    del bugs
    if config.get ('sort', False):
      ibugs.sort()
    # construct full query URL
    fullurl = url + ','.join ([str (b) for b in ibugs])
    # print fullurl
    if len (ibugs) and config.get ('show-query', False):
      print fullurl
    # print bug summaries
    if len (ibugs) and config.get ('show-list', False):
      bught = {}
      for bug in bug_summaries (fullurl):
        bught[int (bug[0])] = bug[1] # bug summaries can have random order
      for bugid in ibugs: # print bugs in user provided order
        iid = int (bugid)
        if bught.has_key (iid):
          desc = bught[iid]
          if len (desc) >= 70:
            desc = desc[:67].rstrip() + '...'
          print "% 7u - %s" % (iid, desc)
        else:
          print "% 7u (NOBUG)" % iid

def help (version = False, verbose = False):
  print "buglist %s" % pkginstall_configvars['VERSION']
  print "Redistributable under GNU GPLv3 or later: http://gnu.org/licenses/gpl.html"
  if version: # version *only*
    return
  print "Usage: %s [options] <BUG-TRACKER> " % os.path.basename (sys.argv[0])
  print "List or download bugs from a bug tracker. Bug numbers are read from stdin."
  if not verbose:
    print "Use the --help option for verbose usage information."
    return
  #      12345678911234567892123456789312345678941234567895123456789612345678971234567898
  print "Options:"
  print "  -h, --help                 Print verbose help message."
  print "  -v, --version              Print version information."
  print "  -U                         Keep bug list unsorted."
  print "  --bug-tracker-list         List supported bug trackers."
  print "Authentication:"
  print "  An INI-style config file is used to associate bugzilla URLs with account"
  print "  authentication for secured installations. The file should be unreadable"
  print "  by others to keep passwords secret, e.g. with: chmod 0600 ~/.urlrc"
  print "  A sample ~/.urlrc might look like this:"
  print "\t# INI-style config file for URLs"
  print "\t[authentication-urls]"
  print "\turls =\thttps://USERNAME:PASSWORD@projects.maemo.org/bugzilla"
  print "\t\thttp://BLOGGER:PASSWORD@blogs.gnome.org/BLOGGER/xmlrpc.php"

def main ():
  import getopt
  # default configuration
  config = {
    'sort' :            True,
    'show-query' :      True,
    'show-list' :       True,
  }
  # parse options
  try:
    options, args = getopt.gnu_getopt (sys.argv[1:], 'vhU', [ 'help', 'version', 'bug-tracker-list' ])
  except getopt.GetoptError, err:
    print >>sys.stderr, "%s: %s" % (os.path.basename (sys.argv[0]), str (err))
    help()
    sys.exit (126)
  for arg, val in options:
    if arg == '-h' or arg == '--help': help (verbose=True); sys.exit (0)
    if arg == '-v' or arg == '--version': help (version=True); sys.exit (0)
    if arg == '-U': config['sort'] = False
    if arg == '--bug-tracker-list':
      print "Bug Tracker:"
      for kv in bugurls:
        print "  %-20s %s" % kv
      sys.exit (0)
  if len (args) < 1:
    print >>sys.stderr, "%s: Missing bug tracker argument" % os.path.basename (sys.argv[0])
    help()
    sys.exit (126)
  trackerdict = dict (bugurls)
  if not trackerdict.has_key (args[0]):
    print >>sys.stderr, "%s: Unknown bug tracker: %s" % (os.path.basename (sys.argv[0]), args[0])
    sys.exit (10)
  # handle bugs
  read_handle_bugs (config, trackerdict[args[0]])

if __name__ == '__main__':
  main()
