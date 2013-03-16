#!bash
#
# Copyright (c) 2012-2013 Adrien LELONG
#
# gitfeature completion file
# This file must be sourced from bash or it can be
# put in /etc/bash_completion.d system directory

__git_localfeat ()
{
	local dir="$(__gitdir)"
	if [ -d "$dir" ]; then
		git --git-dir="$dir" for-each-ref --format='%(refname:short)' \
			refs/heads/draft refs/heads/final
		return
	fi
}

_git_featmove ()
{
    __gitcomp_nl "$(__git_localfeat)"
}

_git_featclose ()
{
    __gitcomp_nl "$(__git_localfeat)"
}

_git_featpush ()
{
    __gitcomp_nl "$(__git_localfeat)"
}

_git_featreview ()
{
    __gitcomp_nl "$(__git_localfeat)"
}

_git_featupdate ()
{
    __gitcomp_nl "$(__git_localfeat)"
}

_git_featview ()
{
    __gitcomp_nl "$(__git_remotes)"
}

_git_featlist ()
{
    __gitcomp_nl "$(__git_remotes)"
}

_git_feature ()
{
	__gitcomp_nl "$(__git_refs)"
}


