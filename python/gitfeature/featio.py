from featcache import load_cache, NotFoundFeature

def process(argv, repo_cache):
    if argv[0] == 'sync':
        repo_cache.sync()
        return ''
    elif argv[0] == 'featdetail':
        lines = []
        for f in repo_cache.features.itervalues():
            lines.append('%r' % f)

        return '\n'.join(lines)
        #l=[f for f in repo_cache.features.itervalues() if f.mainbranch is None]

    elif argv[0] == 'featlist':
        lines = []
        for feat in repo_cache.listfeat():
            lines.append(str(feat))
        return '\n'.join(lines)
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
                var, cmd = cmd.split('=', 1)
            except:
                var = None
            sub_argv = cmd.split(';')
            out = process(sub_argv, repo_cache)
            if var is not None:
                list_out.append("%s='%s'" % (var, out))

        print '\n'.join(list_out)
    else:
        print process(argv[1:], repo_cache)

