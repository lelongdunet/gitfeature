from sys import argv
from gitfeature.featio import process
from gitfeature.featcache import load_cache

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

