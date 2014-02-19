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

#This is the old implementation of __gitcomp_nl that use compgen.
#Using compgen is necessary to handle quotes in completion
__gitcompgen_nl ()
{
	local IFS=$'\n'
	COMPREPLY=($(compgen -P "${2-}" -S "${4- }" -W "$1" -- "${3-$cur}"))
}


_git_feat ()
{
    local subcommands="
    close clear cherry checkout devref files
    diff finalize init merge update show syncall view version
    "
	local subcommand="$(__git_find_on_cmdline "$subcommands")"
	if [ -z "$subcommand" ]; then
        __gitcomp "$subcommands"
    else
        __gitcompgen_nl "$(__git_allfeat)"
    fi
}

_git_featmove ()
{
    __gitcompgen_nl "$(__git_refs)"
}

_git_featclose ()
{
    __gitcompgen_nl "$(__git_localfeat)"
}

_git_featco ()
{
    __gitcompgen_nl "$(__git_allfeat)"
}

_git_featpush ()
{
    __gitcompgen_nl "$(__git_localfeat)"
}

_git_featreview ()
{
    __gitcompgen_nl "$(__git_localfeat)"
}

_git_featupdate ()
{
    __gitcompgen_nl "$(__git_localfeat)"
}

_git_featintegrate ()
{
    __gitcompgen_nl "$(__git_finalfeat)"
}

_git_featfinalize ()
{
    __gitcompgen_nl "$(__git_draftfeat)"
}

_git_featview ()
{
    __gitcompgen_nl "$(__git_remotes)"$'\n'"$(__git_allfeat)"
}

_git_featlist ()
{
    __gitcompgen_nl "$(__git_remotes)"
}

_git_feature ()
{
	__gitcompgen_nl "$(__git_featnamebranches)"
}

_git_branchmove ()
{
    __gitcompgen_nl "$(__git_heads)"
}

_git_branchdel ()
{
    __gitcompgen_nl "$(__git_heads)"
}

