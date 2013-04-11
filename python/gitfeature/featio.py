from featcache import load_cache, NotFoundFeature
from itertools import imap, chain

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

def featbranches(repo_cache, uptodate = False, **args):
    if not uptodate:
        featheads = lambda feature: feature.heads()
    else:
        featheads = lambda feature: feature.heads(True)
    return imap(str, chain(*imap(featheads, repo_cache.listfeat(**args))))

def featdetail(repo_cache, markpush = 'ox ', markupdate = '* ', **args):
    lines = []
    for feat in repo_cache.listfeat(**args):
        if (not feat.mainbranch.local) or feat.pushuptodate:
            pushed = markpush[2]
        elif feat.pushed:
            pushed = markpush[1]
        else:
            pushed = markpush[0]

        uptodate = markupdate[1] if feat.uptodate() else markupdate[0]

        yield ('%d:%s:%s:%s:%d' % (
            feat.mainbranch.local,
            uptodate,
            pushed,
            feat.mainbranch,
            feat.mainbranch.time
            ))


def featstat(repo_cache, markpush = 'ox ', markupdate = '* ', **args):
    listout = []
    for feat in repo_cache.listfeat(**args):
        if (not feat.mainbranch.local) or feat.integrated or feat.pushuptodate:
            pushed = markpush[2]
        elif feat.pushed:
            pushed = markpush[1]
        else:
            pushed = markpush[0]

        uptodate = markupdate[1] if feat.uptodate() else markupdate[0]
        if feat.error is not None or feat.mainbranch.error is not None:
            uptodate = '!'
            pushed = '!'

        yield ('%s %s %s' % (pushed, uptodate, feat.mainbranch))

def featlist(repo_cache, **args):
    return imap(str, repo_cache.listfeat(**args))

def featmainbranch(repo_cache, **args):
    strmainbranch = lambda feature: str(feature.mainbranch)
    return imap(strmainbranch, repo_cache.listfeat(**args))

listfunc_dict = {
        'featlist' : featlist,
        'featstat' : featstat,
        'featdetail' : featdetail,
        'featbranches' : featbranches,
        'featmainbranch' : featmainbranch
        }

def process(argv, repo_cache):
    listoptargs = {
            'integrated' : bool,
            'featuser' : str,
            'state' : str,
            'sort' : str,
            'reverse' : bool,
            'local' : bool,
            'uptodate' : bool,
            'markpush' : str
            }
    if argv[0] == 'sync':
        repo_cache.sync()
        return None
    elif argv[0] == '_featdetail':
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
    else:
        return 'Unknown command %s' % argv[0]

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

