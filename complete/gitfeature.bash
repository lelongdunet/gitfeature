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
		git --git-dir="$dir" feature _featcache featlist local
		return
	fi
}

__git_allfeat ()
{
	local dir="$(__gitdir)"
	if [ -d "$dir" ]; then
		git --git-dir="$dir" feature _featcache featlist
		return
	fi
}

__git_finalfeat ()
{
	local dir="$(__gitdir)"
	if [ -d "$dir" ]; then
		git --git-dir="$dir" feature _featcache featlist state=final
		git --git-dir="$dir" feature _featcache featbranches state=final
		return
	fi
}

__git_draftfeat ()
{
	local dir="$(__gitdir)"
	if [ -d "$dir" ]; then
		git --git-dir="$dir" feature _featcache featlist state=draft
		git --git-dir="$dir" feature _featcache featbranches state=draft
		return
	fi
}

__git_featbranches ()
{
	local dir="$(__gitdir)"
	if [ -d "$dir" ]; then
		git --git-dir="$dir" feature _featcache featbranches
		return
	fi
}

__git_featnamebranches ()
{
	local dir="$(__gitdir)"
	if [ -d "$dir" ]; then
		git --git-dir="$dir" feature _featcache featlist
		git --git-dir="$dir" feature _featcache featbranches
		return
	fi
}

_git_featmove ()
{
    __gitcomp_nl "$(__git_refs)"
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

_git_featintegrate ()
{
    __gitcomp_nl "$(__git_finalfeat)"
}

_git_featfinalize ()
{
    __gitcomp_nl "$(__git_draftfeat)"
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
	__gitcomp_nl "$(__git_featnamebranches)"
}


