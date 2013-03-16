from featcache import load_cache, NotFoundFeature

def argdict(allargs, argin):
    outdict = {}
    for arg in argin:
        try:
            argname, argval = arg.split('=')
        except ValueError:
            argname = arg
            argval = None

        try:
            argtype = allargs[argname]
        except KeyError:
            raise NameError('Unsupported argument %s' % argname)

        if argval is None:
            if argtype == bool:
                argval = True
            else:
                argval = argtype('')
        else:
            argval = argtype(argval)
        outdict[argname] = argval

    return outdict

def featstat(repo_cache, markpush = 'ox ', markupdate = '* ', **args):
    listout = []
    for feat in repo_cache.listfeat(**args):
        if (not feat.mainbranch.local) or feat.pushupdated:
            pushed = markpush[2]
        elif feat.pushed:
            pushed = markpush[1]
        else:
            pushed = markpush[0]

        if feat.mainbranch.updated:
            updated = markupdate[1]
        else:
            updated = markupdate[0]

        listout.append('%s %s %s' % (pushed, updated, feat.mainbranch))
    return listout

def featlist(repo_cache, **args):
    return map(str, repo_cache.listfeat(**args))

listfunc_dict = {
        'featlist' : featlist,
        'featstat' : featstat
        }

def process(argv, repo_cache):
    listoptargs = {
            'integrated' : bool,
            'featuser' : str,
            'state' : str,
            'sort' : str,
            'reverse' : bool,
            'local' : bool,
            'markpush' : str
            }
    if argv[0] == 'sync':
        repo_cache.sync()
        return None
    elif argv[0] == 'featdetail':
        lines = []
        for f in repo_cache.features.itervalues():
            lines.append('%r' % f)

        return '\n'.join(lines)
        #l=[f for f in repo_cache.features.itervalues() if f.mainbranch is None]

    elif listfunc_dict.has_key(argv[0]):
        func = listfunc_dict[argv[0]]
        return '\n'.join(func(repo_cache, **argdict(listoptargs, argv[1:]) ))
    elif hasattr(repo_cache, 'get_%s' % argv[0]):
        func = getattr(repo_cache, 'get_%s' % argv[0])
        try:
            return str(func(argv[1]))
        except NotFoundFeature:
            exit(1)

    return ''

if __name__ == '__main__':
    from sys import argv
    repo_cache = load_cache()
    if len(argv) < 2:
        repo_cache.sync()
    elif argv[1] == 'parse':
        list_out = []
        for cmd in argv[2:]:
            try:
                var, cmdlist = cmd.split('=', 1)
                if not var.isalnum():
                    raise ValueError
                cmd = cmdlist
            except ValueError:
                var = None
            sub_argv = cmd.split(';')
            out = process(sub_argv, repo_cache)
            if var is not None:
                list_out.append("%s='%s'" % (var, out))
            elif out is not None:
                list_out.append(out)

        print '\n'.join(list_out)
    else:
        print process(argv[1:], repo_cache)

