#!/bin/bash

# default config
CWD=
SOURCES=
INC=false
NGUARDED=8
NKEEPS=8
FPREFIX=bak-
FPOSTFIX=-snap
IPREFIX=bak-
IPOSTFIX=-rinc
XPOSTFIX=-xinc
MAXDELETE=
LISTDELTAS=false
INFOMSG=true
FAKERUN=false

# die with descriptive error messages
SCRIPTNAME=`basename $0`
function die  { e="$1"; shift; [ -n "$*" ] && echo "$SCRIPTNAME: $*" >&2; exit "$e" ; }
function warn { [ -n "$*" ] && echo "$SCRIPTNAME: warning: $*" >&2; }
function msg  { $INFOMSG && echo "$*"; }

# usage and help
function usagedie { # exitcode message...
  e="$1"; shift;
  [ -n "$*" ] && echo "$SCRIPTNAME: $*" >&2
  echo "Usage: $SCRIPTNAME [options] sources..."
  echo "OPTIONS:"
  echo "  --inc         merge incremental backups"
  echo "  -g <nguarded> recent files to guard (8)"
  echo "  -k <nkeeps>   non-recent to keep (8)"
  echo "  -d <maxdelet> maximum number of deletions"
  echo "  -C <dir>      backup directory"
  echo "  -o <prefix>   output directory name (default: 'bak')"
  echo "  -q, --quiet   suppress progress information"
  echo "  --fake        only simulate deletions or merges"
  echo "  -L            list all backup files with delta times"
  echo "DESCRIPTION:"
  echo "  Delete candidates from a set of aging backups to spread backups most evenly"
  echo "  over time, based on time stamps embedded in directory names."
  echo "  Backups older than <nguarded> are purged, so that only <nkeeps> backups"
  echo "  remain. In other words, the number of backups is reduced to <nguarded>"
  echo "  + <nkeeps>, where <nguarded> are the most recent backups."
  echo "  The puring logic will always pick the backup with the shortest time"
  echo "  distance to other backups. Thus, the number of <nkeeps> remaining"
  echo "  backups is most evenly distributed across the total time period within"
  echo "  which backups have been created."
  echo "  Purging of incremental backups happens via merging of newly created"
  echo "  files into the backups predecessor. Thus merged incrementals may"
  echo "  contain newly created files from after the incremental backups creation"
  echo "  time, but the function of reverse incremental backups is fully"
  echo "  preserved. Merged incrementals use a different file name ending (-xinc)."
  exit "$e"
}

# parse options
[ -z "$*" ] && usagedie 0
parse_options=1
while test $# -ne 0 -a $parse_options = 1; do
  case "$1" in
    --inc)              INC=true ;;
    -L)                 LISTDELTAS=true ; NGUARDED=1 ; NKEEPS=1 ;;
    -q|--quiet)         INFOMSG=false ;;
    --help)             usagedie 0 ;;
    -C)                 CWD="$2" ; shift ;;
    -o)                 IPREFIX="$2"- ; FPREFIX="$2"- ; shift ;;
    -d)                 MAXDELETE="$2" ; shift ;;
    -g)                 NGUARDED="$2" ; shift ;;
    -k)                 NKEEPS="$2" ; shift ;;
    --fake)             FAKERUN=true ;;
    --)                 parse_options=0 ;;
    -*|*)               usagedie 1 "option not supported: $1" ;;
    #*)                  parse_options=0 ; break ;;
  esac
  shift
done

# operate in backup directory
[ -n "$CWD" ] && { cd "$CWD"/. || die 2 "Invalid CWD: $CWD" ; }
[ -z "$CWD" -a / = "`pwd`" ] && die 2 "Refusing to purge in / - invoked from cron without -C?"

# setup definitions
if $INC ; then
  PREFIX="$IPREFIX"
  POSTFIX="$IPOSTFIX"
  POSTFIX2="$XPOSTFIX"
else
  PREFIX="$FPREFIX"
  POSTFIX="$FPOSTFIX"
  POSTFIX2="$FPOSTFIX"
fi

# handle backup deletion and merging
# new_successor=`delete_merge tobedeleted successor`
function delete_merge() {
  # successor files take precedence over tobedeleted files when merging
  if $INC ; then
    # determine merge name
    xname=`echo " $2" | sed "s/^ // ; s,\($POSTFIX\)$,$XPOSTFIX,"`
    $FAKERUN && { echo "(FAKEMERGE:$2)" >&2 ; echo "$xname" ; return ; }
    # merge incrementals into new temporary
    TMPDIR=`mktemp -d "./sayebackup_tmpXXXXXX"` || die 7 "$0: Failed to create temporary dir"
    # refer to source dirs without colons
    ln -s ../"$2" "$TMPDIR"/main || die 7 "Failed to create links in target dir: $TMPDIR"
    ln -s ../"$1" "$TMPDIR"/plus || die 7 "Failed to create links in target dir: $TMPDIR"
    # merge target, rsync gives precedence to files in first source arg
    rsync -axH --link-dest=../../"$TMPDIR"/main/ --link-dest=../../"$TMPDIR"/plus/ \
      "$TMPDIR"/main/ "$TMPDIR"/plus/ "$TMPDIR"/dest || \
      die 7 "Error during rsync - retaining temporary: $TMPDIR"
    # remove sources, because possibly $2 == $xname
    chmod +rwX -R "$1" "$2" && rm -rf "$1" "$2" || \
      die 7 "Failed to purge incrementals: $1 $2 (remains: $tname)"
    mv "$TMPDIR"/dest "$xname" || die 7 "Failed to rename incremental dir: $TMPDIR/dest -> $xname"
    rm "$TMPDIR"/main "$TMPDIR"/plus && rmdir "$TMPDIR" || \
      warn "Failed to cleanup temporary: $TMPDIR"
    echo "$xname"
  else
    $FAKERUN && { echo "(FAKEDELETE:$1)" >&2 ; echo "$2" ; return ; }
    # non-incremental deletion
    rm -rf "$1"
    echo "$2"
  fi
}

# create temporary file for file list
TMPFILEL=`mktemp "/tmp/sayepurge_ltmpXXXXXX"` || die 5 "$0: Failed to create temporary file"
trap 'rm -rf "$TMPFILEL"' 0 HUP QUIT TRAP USR1 PIPE TERM
TMPFILES=`mktemp "/tmp/sayepurge_stmpXXXXXX"` || die 5 "$0: Failed to create temporary file"
trap 'rm -rf "$TMPFILEL" "$TMPFILES"' 0 HUP QUIT TRAP USR1 PIPE TERM

# list backup names, sort recent first
find . -maxdepth 1 -name "$PREFIX*$POSTFIX" -o -name "$PREFIX*$POSTFIX2" | sort -r | uniq > "$TMPFILEL"

# extract time stamps by matching YYYY-MM-DD-hh:mm:ss
sed "s/\.\/$PREFIX\([0-9]\+-[0-9]\+-[0-9]\+\)-\([0-9]\+:[0-9]\+:[0-9]\+\).*/\1 \2/" < "$TMPFILEL" > "$TMPFILES"

# parse names and stamps [0..nfiles]
nfiles=$[1 - $NGUARDED]
unset filelist stamplist
while read file && read stamp <&3 ; do
  [ $nfiles -le 0 ] && msg "Ignore: $file"
  [ $nfiles -ge 0 ] && {
    filelist[$nfiles]="$file"
    stamplist[$nfiles]=`date +%s -d "$stamp" 2>/dev/null`
    [ -z "stamplist[$nfiles]" ] && die 2 "Failed to extract time stamp from file: $file ($stamp)"
  }
  nfiles=$[$nfiles + 1]
done < "$TMPFILEL" 3< "$TMPFILES"
nfiles=$[$nfiles - 1] # undo last increment

# calculate seconds delta (delte[i] is delta between i and its predecessor)
unset deltalist
maxdelta=0
for i in `seq 1 $nfiles` ; do
  y=$[${stamplist[$[$i - 1]]} - ${stamplist[$i]}]
  # y=$[$y + ($nfiles - $i) * 1]	# apply preserving weight to more recent files
  deltalist[$i]=$y
  [ ${deltalist[$i]} -gt $maxdelta ] && maxdelta=${deltalist[$i]}
done

# list files and deltas
$LISTDELTAS && {
  deltalist[0]=0
  for i in `seq 0 $nfiles` ; do
    echo "${filelist[$i]} $[(${deltalist[$i]} + 1800) / 3600]h (${deltalist[$i]}s)"
  done
  exit
}

# constrain and check for deletions
ndeletions=$[$nfiles - $NKEEPS]
[ -n "$MAXDELETE" ] && [ "$MAXDELETE" -lt $ndeletions ] && ndeletions="$MAXDELETE"

# loop over required deletions
for j in `seq 1 $ndeletions` ; do
  # find smallest delta (last among equals)
  minscore=$[1 + $maxdelta * 2 + $nfiles]
  minindex=-1
  for i in `seq 2 $nfiles` ; do
    #deltascore=$[(${deltalist[$i]} + ${deltalist[$[$i + 1]]}) / 2]
    deltascore=${deltalist[$i]}
    [ -n "${filelist[$i]}" -a $deltascore -le $minscore ] && {
      minscore=$deltascore
      minindex=$i
    }
  done
  [ $nfiles -lt 2 ] && minindex=1
  # deletion stamp is deltalist[$minindex], decide between minindex and predecessor
  if [ $minindex -gt 1 -a $minindex -lt $nfiles ] ; then
    [ ${deltalist[$[$minindex - 1]]} -lt ${deltalist[$[$minindex + 1]]} ] && \
      minindex=$[$minindex - 1]	# predecessor has closer neighbour
  else
    # protect oldest backup
    [ $minindex = $nfiles -a $nfiles -gt 1 ] && minindex=$[$minindex - 1]
  fi
  [ $minindex -lt 1 ] && die 3 "Internal prune logic failed ($minindex), aborting..."
  # delete candidate
  candidate="${filelist[$minindex]}"
  filelist[$minindex]=""
  if $INC ; then
    msg "Merge:  $candidate"
  else
    msg "Purge:  $candidate"
  fi
  filelist[$[$minindex + 1]]=`delete_merge "$candidate" "${filelist[$[$minindex + 1]]}"`
  # propagate time stamp to next undeleted neighbour
  k=$[$minindex + 1]
  deltalist[$k]=$[${deltalist[$k]} + ${deltalist[$minindex]}]	# undeleted
  [ ${deltalist[$k]} -gt $maxdelta ] && maxdelta=${deltalist[$k]}
  # shrink list by closing deleted file gap
  last=$minindex
  for next in `seq $[$last + 1] $nfiles` ; do
    filelist[$last]=${filelist[$next]}
    stamplist[$last]=${stamplist[$next]}
    deltalist[$last]=${deltalist[$next]}
    last=$next
  done
  nfiles=$[$nfiles - 1]
done

# list kept files
for j in `seq 1 $nfiles` ; do
  file="${filelist[$j]}"
  msg "Keep:   $file"
done


## creating test dirs:
false && {
  chmod +rwX -R . ; \
  rm -rf * ; \
  for i in $(seq -f %0.0f 1235862000 3600 1238536800) ; do \
    mkdir bak-`echo $i | gawk '{ print strftime ("%F-%T", $1) }'`-rinc ; \
  done ; \
  for i in * ; do echo $i >"$i"/origin ; done ; \
  for i in * ; do echo touch >"$i"/touch-$i ; done ; \
  for i in * ; do \
    mkdir -p $i/xa/xb $i/222 ; \
    date > $i/xa/xb/$RANDOM ; \
    touch $i/xa/empty ; \
    echo foo >$i/222/foo ; \
  done ; \
}
