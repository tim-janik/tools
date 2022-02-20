# Redistributable under GNU GPLv3 or later: http://www.gnu.org/licenses/gpl.html

all:
Q		 = $(if $(findstring 1, $(V)) ,, @)
QGEN		 = @echo '  GEN     ' $@
COMMIT_STAMPS	 = ../.git/HEAD  ../.git/packed-refs
GIT_DESCRIBE	!= git describe
ALL_TARGETS	 = $(CLEAN_TARGETS)
CLEAN_TARGETS	 =
PYCONFIGVARS	 = "GIT_DESCRIBE" : "${GIT_DESCRIBE}"
CHECKSTATUS	 = e=$$?; echo '  CHECK   ' $@ : `test 0 = $$e && echo OK || echo FAIL` ; exit $$e

# == wikihtml2man.py ==
wikihtml2man: wikihtml2man.py $(COMMIT_STAMPS)
	$(QGEN)
	$(Q) sed <$< >xgen-$(@F)                        \
	  -e '1,1s|#!/usr/bin/env python\([0-9]\+\(\.[0-9]\+\)\?\)\?|#!${PYTHON}|' \
	  -e '1,24s|^ *#@PKGINSTALL_CONFIGVARS_IN24LINES@|  ${PYCONFIGVARS}|'
	$(Q) chmod +x xgen-$(@F)
	$(Q) cp -p xgen-$(@F) $@ && rm -f xgen-$(@F)
	$(Q) ./wikihtml2man --version | grep -qF wikihtml2man ; $(CHECKSTATUS)
CLEAN_TARGETS += wikihtml2man

# == wikihtml2man.1 ==
wikihtml2man.1: wikihtml2man.1.mwhtml wikihtml2man
	$(QGEN)
	$(Q) ./wikihtml2man.py $< >xgen-$@
	$(Q) mv xgen-$@ $@ ; rm -f xgen-$@
	$(Q) grep -q '\.TH.*WIKIHTML2MAN' ./wikihtml2man.1 ; $(CHECKSTATUS)
CLEAN_TARGETS += wikihtml2man.1

# == clean ==
clean:
	rm -f $(CLEAN_TARGETS) $(CLEANFILES)

# == all ==
all:		$(ALL_TARGETS)
