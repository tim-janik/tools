#!/usr/bin/python
# Copyright (C) 2011 Tim Janik
# Redistributable under GNU GPLv3 or later: http://www.gnu.org/licenses/gpl.html
import re, sys, time
from xml import etree
from xml.etree import ElementTree

MYPACKAGE, MYVERSION = 'Testbit.eu/Tools', '0.1'

# === Utilities ===
dbg = None
def dbg_print (*args):
  o = ' '.join (args)
  if len (o) and o[-1] != '\n': o += '\n'
  print >>sys.stderr, o
def die (*args):
  print >>sys.stderr, 'ERROR:', ' '.join (args)
  exit (-1)
def qq (string):        # man-page quoting of special characters
  s = re.sub (r'([.\\-])', r'\\\1', string)
  s = re.sub ('\n', ' ', s)
  return s
def dq (string):        # double quotes around qq()
  s = re.sub (r'([".\\-])', r'\\\1', string)
  s = re.sub ('\n', ' ', s)
  return '"' + s + '"'
def textr (node):       # retrieve plain text from node recursively
  def childtext (node, withtail):
    s = node.text if isinstance (node.text, basestring) else ''
    for c in node:
      s += childtext (c, True)
    if withtail:
      s += node.tail if isinstance (node.tail, basestring) else ''
    return s
  return childtext (node, False)

# === Heuristics ===
# Man page information guessed by heuristics.
gman_name_parent = None
gman_name_node = None
gman_name_def = ('', '')
gman_pagetitle = ''
gman_section = '?'
gman_updated = time.strftime ('%Y-%m-%d')
gman_origin = ''
gman_manual = ''
gman_server_path = ''

# === gman_heuristics ===
# Use heuristics to guess several man page bits:
# * Find the 'NAME' section to identify a manual page.
# * Find 'NAME' section parent, assuming all relevant HTML sections are its ancestors.
# * Try to match man page title and section from a header preceeding 'NAME'.
# * Try to parse Updated, Release, Manual bits from title header section.
def gman_heuristics (node):
  capture = [] # title section contents
  gman_script_path = ''
  def recurse (node, parent):
    global gman_name_parent, gman_name_node, gman_name_def
    global gman_pagetitle, gman_section, gman_updated, gman_origin, gman_manual
    headings = ('h1', 'h2', 'h3', 'h4', 'h5', 'h6')
    tag = node.tag if isinstance (node.tag, basestring) else '!--'
    text = textr (node)
    start_capture = False
    if capture:
      capture[0] += node.text if isinstance (node.text, basestring) else ''
    if tag.lower() in headings:
      if capture and gman_name_node: # previous heading was NAME section
        # match ' EXECUTABLE - DESCRIPTIVE BLURB '
        m = re.match (r'\s*([_a-zA-Z0-9][_a-zA-Z0-9-]+)\s+-\s+([^\s].*?)\s*$', capture[0])
        if m:
          gman_name_def = m.groups()
      elif capture and gman_pagetitle:   # previous heading was title section
        capture[0] += '\n'
        m = re.search ('\nUpdated:\s+([^\n]+?)\s*\n', capture[0])
        gman_updated = m.group (1) if m else gman_updated
        m = re.search ('\n(Resource|Release):\s+([^\n]+?)\s*\n', capture[0])
        gman_origin = m.group (2) if m else gman_origin
        m = re.search ('\nManual:\s+([^\n]+?)\s*\n', capture[0])
        gman_manual = m.group (1) if m else gman_manual
        capture.pop()
      text = re.sub (r'\[edit\]', '', text)
      if text.upper().strip() == 'NAME' and not gman_name_node:
        gman_name_node = node
        gman_name_parent = parent
        start_capture = True
      elif not gman_pagetitle and not gman_name_node:
        # match ' PageName([0-9]) - Manual Page Title '
        m = re.match (r'\s*([_a-zA-Z0-9-]+)\(([0-9][a-zA-Z]*)\)(\s+-\s.*)?\s*$', text)
        if m:
          gman_pagetitle = m.group (1)
          gman_section = m.group (2)
          start_capture = True
    elif tag.lower() == 'br' and capture:
      capture[0] += '\n'
    for c in node.getchildren():
      recurse (c, node)
    if start_capture:   # capture tail, but not children contents
      capture.insert (0, '\n')
    if capture:
      capture[0] += node.tail if isinstance (node.tail, basestring) else ''
    if tag == 'script' and text:
      global gman_server_path, gman_script_path
      m = re.search (r'\bwgScriptPath\s*=\s*"([^"]*)"\s*[,;]', text)
      if m:     gman_script_path = m.group (1)
      m = re.search (r'\bwgServer\s*=\s*"([^"]*)"\s*[,;]', text)
      if m:     gman_server_path = m.group (1)
  recurse (node, None)
  # some polishing
  global gman_updated, gman_server_path
  gman_updated = re.sub (r'(\b[0-9]\b)', r'0\1', gman_updated)
  if gman_server_path and gman_script_path:
    gman_server_path += gman_script_path


# === xml2events ===
# Generate start/data/end events for man generation from XML tree
# Discard most unrelated HTML bits, by filtering nodes out that
# don't contain the 'NAME' section.
def xml2events (node, o):
  unignore = [ -1 ]
  def noder (node):
    if gman_name_parent == node: unignore[0] += 1
    if gman_name_node == node: unignore[0] += 1
    txt = node.tag if isinstance (node.tag, basestring) else '!--'
    if unignore[0] > 0 and txt != '!--':
      o.start (txt, node.attrib)
      txt = node.text if isinstance (node.text, basestring) else ''
      if txt: o.data (unicode (txt))
    for c in node.getchildren():
      noder (c)
    txt = node.tag if isinstance (node.tag, basestring) else '--'
    if unignore[0] > 0 and txt != '--':
      o.end (txt, node.attrib)
    if gman_name_parent == node: unignore[0] -= 1
    if unignore[0] > 0:
      txt = node.tail if isinstance (node.tail, basestring) else ''
      if txt: o.data (unicode (txt))
  noder (node)
  o.close()
class XmlEventDebug:
  def start (self, tag, attrib):        print '<%s ...>' % tag,
  def end (self, tag):                  print '</%s>' % tag,
  def data (self, data):
    # print type (data), repr (data)
    print data.encode ('utf8', 'ignore'),
  def close (self):                     pass
#xml2events (root, XmlEventDebug()); exit (-1)


# === ManEvents ===
# Generate roff markup from XML events by matching corresponding
# HTML elements.
HEADINGS = ('h1', 'h2')
SUBHEADS = ('h3', 'h4', 'h5', 'h6')
PREFORMS = ('pre')
ITALICS = ('i')
BOLDS = ('b')
class ManEvents:
  def __init__ (self):
    self.out = u''
    self.transforms = []
    self.nest = 0
    self.list = 'bullet'
    self.listn = 0
    self.ignore = 0
    self.preserve = 0
    self.sstart = 0
    self.sname = '' # section name
  def push (self, transform):
    self.transforms += [ transform ]
  def pop (self):
    self.transforms.pop()
  def tupper (self, s, i):      return s.upper()
  def tnop (self, s, i):        return s
  def tlstrip (self, s, i):
    q = s.lstrip()
    if q: self.transforms[i] = self.tnop # finished stripping up to first text
    return q
  def rstrip (self):            return self.rstripa()
  def rstripa (self, append = ''):
    self.out = self.out.rstrip() + append
  def nlappend (self, append):
    if not self.out or self.out[-1] != '\n':
      self.out += '\n'
    self.out += append
  def nesting (self, delta):
    self.nest += delta
    if delta > 0 and self.nest > 1:
      self.rstripa ('\n.RS\n')
    elif delta < 0 and self.nest >= 1:
      self.rstripa ('\n.RE\n')
  def listitem (self):
    self.listn += 1
    if self.list == 'number':
      self.nlappend ('.IP "%2u." 4\n' % self.listn)
    else: # if self.list == 'bullet':
      self.nlappend ('.IP \\(bu 2\n')
  def uselink (self, attrib):
    url = attrib.get ('href', '')
    link_section = re.match ('SEE\s*ALSO', self.sname.strip(), re.IGNORECASE)
    abslink = '://' in url[:9]
    return url and link_section and abslink
  def start (self, tag, attrib):        # opening tag
    if self.ignore:                                                     self.ignore += 1
    elif re.search (r'\beditsection\b', attrib.get ('class', '')):      self.ignore += 1
    elif re.search (r'\bprintfooter\b', attrib.get ('class', '')):      self.ignore = 9999999 # done
    if self.ignore:                     return
    elif tag.lower() in HEADINGS:       self.nlappend ('\n.SH '); self.push (self.tupper); self.sstart = len (self.out)
    elif tag.lower() in SUBHEADS:       self.nlappend ('.SS '); self.sstart = len (self.out)
    elif tag.lower() == BOLDS:          self.out += r'\fB'
    elif tag.lower() == ITALICS:        self.out += r'\fI'
    elif tag.lower() == PREFORMS:       self.rstripa ('\n.EX\n'); self.preserve += 1
    elif tag.lower() == 'dt':           self.rstripa ('\n.TP\n'); self.push (self.tlstrip)
    elif tag.lower() == 'dd':           self.rstripa ('\n'); self.push (self.tlstrip)
    elif tag.lower() == 'br':           self.out += '\n.br\n'
    elif tag.lower() == 'dl':           self.nesting (+1)
    elif tag.lower() == 'ul':           self.list = 'bullet'; self.listn = 0
    elif tag.lower() == 'ol':           self.list = 'number'; self.listn = 0
    elif tag.lower() == 'li':           self.listitem(); self.push (self.tlstrip)
    elif tag.lower() == 'p' and not self.out.endswith('\n\n'): self.nlappend ('\n')
    elif tag.lower() == 'a':
      if self.uselink (attrib):         pass # self.nlappend ('.UR ' + attrib['href'] + '\n')
      else:                             self.out += r'\fI'
  def end (self, tag, attrib):          # closing tag
    if self.ignore:                     self.ignore -= 1; return
    elif tag.lower() in HEADINGS:       self.rstripa ('\n'); self.pop(); self.sname = self.out[self.sstart:]
    elif tag.lower() in SUBHEADS:       self.rstripa ('\n'); self.sname = self.out[self.sstart:]
    elif tag.lower() == BOLDS:          self.out += r'\fR'
    elif tag.lower() == ITALICS:        self.out += r'\fR'
    elif tag.lower() == PREFORMS:       self.nlappend ('.EE\n'); self.preserve -= 1
    elif tag.lower() == 'dt':           self.rstripa ('\n'); self.pop()
    elif tag.lower() == 'dd':           self.rstripa ('\n.PP\n'); self.pop()
    elif tag.lower() == 'dl':           self.nesting (-1)
    elif tag.lower() == 'li':           self.pop()
    elif tag.lower() == 'a':
      if self.uselink (attrib):         self.out += ' <%s>' % attrib['href'] # self.nlappend ('.UE\n')
      else:                             self.out += r'\fR'
  def data (self, data):                # text?
    if self.ignore: return
    s = unicode (data)
    i = 0
    while i < len (self.transforms):
      s = self.transforms[i] (s, i)
      i += 1
    if self.preserve:
      self.out += s
    else:
      self.compressa (s)
  def compressa (self, s):
    s = re.sub (r'[ \t]+', ' ', s)
    s = re.sub (r'[ \t]*\n+[ \t]*', r'\n', s)
    if len (self.out) and self.out[-1] in ' \t\n':
      s = s.lstrip()
    self.out += s
  def close (self):                     # XMLParser.close
    pass

# === gen_man_title ===
# Generate man page title string;
# Syntax: .TH <title> <section> <updated> <release> <manual>
def gen_man_title (title, section, updated, release, manual):
  s = '.TH ' + dq (title).upper() + ' ' + dq (section)
  s += ' ' + dq (updated) + ' ' + dq (release) + ' ' + dq (manual)
  return s

# === help page ===
def help_page (topic):
  import os
  try:
    os.execvp ('man', ('man', topic))
  except:
    die ('Failed to execute help browser for:', topic)
def print_version (topic):
  print topic, "(%s)" % MYPACKAGE, MYVERSION
  print "Copyright (C) 2011 Tim Janik"
  print "Redistributable under GNU GPLv3 or later: http://www.gnu.org/licenses/gpl.html"
  sys.exit (0)

# === main ===
# Main function for manual page genration. The process works as follows:
# * Parse HTML to XML.
# * Use heuristics on XML to detect man page content.
# * Process XML events, thereby generating man page roff source
# * Output of roff source.
def main (argv = ()):
  # some arg parsing
  import getopt
  th = [ None, None, None, None, None ]
  so = 'hgt:s:u:r:m:'
  lo = ['help', 'debug', 'version']
  options,args = getopt.gnu_getopt (argv[1:], so, lo)
  for arg,val in options:
    if arg == '-h' or arg == '--help': help_page ('wikihtml2man')
    if arg == '--version': print_version ('wikihtml2man')
    if arg == '-g' or arg == '--debug': global dbg; dbg = dbg_print
    if arg == '-t': th[0] = val
    if arg == '-s': th[1] = val
    if arg == '-u': th[2] = val
    if arg == '-r': th[3] = val
    if arg == '-m': th[4] = val
  if not args:
    die ("Missing input file")
  input_name = args[0]
  # load HTML
  if re.match ('\w+:', input_name):
    import urllib2
    req = urllib2.Request (args[0])
    req.add_header ('User-Agent', 'wikihtml2man/0.1')
    try:
      f = urllib2.urlopen (req)
    except IOError, ex:
      die ("Failed to access URL: " + input_name + ": " + str (ex))
  else:
    try:
      f = open (input_name)
    except IOError, ex:
      die ("Failed to read input: " + input_name + ": " + str (ex))
  # parse HTML into XML tree
  import html5lib
  from html5lib import treebuilders
  tbuilder = treebuilders.getTreeBuilder ("etree", ElementTree)
  parser = html5lib.HTMLParser (tree = tbuilder, namespaceHTMLElements = False)
  root = parser.parse (f)
  if dbg: dbg ("XML-DUMP:\n", etree.ElementTree.tostring (root))
  # run heuristics on XML nodes
  gman_heuristics (root)
  if not gman_name_node:
    die ("Failed to detect required manual page section: NAME")
  # generate man roff
  mev = ManEvents()
  xml2events (root, mev)
  if th[0] == None: th[0] = gman_name_def[0] or gman_pagetitle
  if th[1] == None: th[1] = gman_section
  if th[2] == None: th[2] = gman_updated
  if th[3] == None: th[3] = gman_origin
  if th[4] == None: th[4] = gman_manual
  mpage = gen_man_title (*th) + mev.out
  # output
  print unicode (mpage).encode ('utf8', 'ignore')
  return 0

if __name__ == '__main__':
  import sys
  sys.exit (main (sys.argv))

###
# TODO:
# - add base url option
# - concatenate consequtive <dd/> tags
# - convert xxxx.1 man-page URLs to xxxx(1) (discard link target)
# - test hyphenation and backslash uses that required qq()
# - table? see man -7
# - render links as italics if not in "SEE ALSO", add option to
# - option: to match NAME
# - option: to match "SEE ALSO"
# - show links only for section matches (SEE ALSO) else italic
# - discard hrefs for manual page links
