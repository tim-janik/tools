#!/bin/bash
# CC0 Public Domain: http://creativecommons.org/publicdomain/zero/1.0/

_yyhelp_complete_branch() {
  local cur branches
  cur=${COMP_WORDS[COMP_CWORD]}
  COMPREPLY=()	# Array variable storing the possible completions.
  branches=$( git for-each-ref --format='%(refname:short)' refs/heads )
  if test "$1" == "$3" ; then # completing first arg
    COMPREPLY=( $(compgen -W "$branches" -- "$cur") )
  fi
}

complete -F _yyhelp_complete_branch yymerge yywarp

# install -m 644 -T yyhelp-completion.bash ${_sysconfdir}/bash_completion.d/yyhelp-completion.bash
