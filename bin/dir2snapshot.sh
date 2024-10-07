#!/bin/bash
# This Source Code Form is licensed MPL-2.0: http://mozilla.org/MPL/2.0
set -Eeuo pipefail #-x
SCRIPTNAME=`basename $0` && function die  { [ -n "$*" ] && echo "$SCRIPTNAME: $*" >&2; exit 127 ; }

# Given a directory on a btrfs FS, move its contents into a newly created snapshot

test $# == 1 || die "Usage: $0 <directory>"

DIR=$(readlink -f "$1")
test ! -e "$DIR"2_ -a ! -e "$DIR"3_ || die "Usage: temp dirs exist already"

set -x

btrfs subvolume create "$DIR"2_
chmod --reference="$DIR"/ "$DIR"2_
chown --reference="$DIR"/ "$DIR"2_

mv -iv "$DIR" "$DIR"3_
mv -iv "$DIR"2_ "$DIR"

find "$DIR"3_/ -maxdepth 1 -mindepth 1 -exec mv -iv -t "$DIR"/ -- {} \;

rmdir "$DIR"3_/
