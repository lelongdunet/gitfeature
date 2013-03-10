from featcache import load_cache

if __name__ == '__main__':
    from sys import argv
    repo_cache = load_cache()

    if len(argv) < 2:
        repo_cache.sync()

    elif argv[1] == 'featdetail':
        for f in repo_cache.features.itervalues():
            print '%r' % f
        #l=[f for f in repo_cache.features.itervalues() if f.mainbranch is None]


