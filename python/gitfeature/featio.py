from featcache import load_cache, NotFoundFeature

if __name__ == '__main__':
    from sys import argv
    repo_cache = load_cache()
    if len(argv) < 2:
        repo_cache.sync()

    elif argv[1] == 'featdetail':
        for f in repo_cache.features.itervalues():
            print '%r' % f
        #l=[f for f in repo_cache.features.itervalues() if f.mainbranch is None]

    elif argv[1] == 'featlist':
        for feat in repo_cache.listfeat():
            print feat
    elif hasattr(repo_cache, 'get_%s' % argv[1]):
        func = getattr(repo_cache, 'get_%s' % argv[1])
        try:
            print func(argv[2])
        except NotFoundFeature:
            exit(1)


