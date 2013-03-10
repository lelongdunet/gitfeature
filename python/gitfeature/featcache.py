import cPickle
from binascii import a2b_hex, b2a_hex


_GITDIR = '.git'
_GITROOT = '.'
_DEVREF = 'devel'
_MYREPO = 'mine'

def load_cache():
    from os.path import exists, join

    pickle_file = join(_GITDIR, 'featcache')
    if exists(pickle_file):
        repo_cache = cPickle.load(open(pickle_file))
    else:
        repo_cache = RepoCache()

    return repo_cache

def _save_cache(repo_cache):
    from os.path import exists, join

    pickle_file = join(_GITDIR, 'featcache')
    cPickle.dump(repo_cache, open(pickle_file, 'wb'), -1)

#States are in priority order
_featstates = ('start', 'tmp', 'save', 'draft', 'final')

def verbose(string):
    print string

class Error(Exception):
    pass

class InvalidUnique(Error):
    pass

class UniqueViolation(Error):
    pass

class Unique(object):
    def __init__(self, name):
        if not hasattr(self, 'inst'):
            raise InvalidUnique

        if self.inst.has_key(name):
            raise UniqueViolation

        self.inst[name] = self
        self.name = name

class UniqueTest(Unique):
    inst = {}
    def __init__(self, name, data):
        Unique.__init__(self, name)
        self.data = data

class Commit(object):
    def __init__(self, repo_cache, sha, head = None, branch = None):
        if repo_cache.commits.has_key(sha):
            raise InvalidUnique
        repo_cache.commits[sha] = self

        if head is not None:
            self.heads = [head]
        else:
            self.heads = None

        self.branch = branch
        if branch is not None:
            self.feature = branch.feature

        self.sha = sha
        self.parent = None
        self.repo_cache = repo_cache

    def sethead(self, branch):
        """ Add a head corresponding to this commit """
        if self.heads is None:
            self.heads = [branch]
        else:
            self.heads.append(branch)

    def unsethead(self, branch):
        """ Remove the reference to the specified head """
        try:
            self.heads.remove(branch)
        except ValueError:
            #TODO Handle this error
            pass

    def setbranch(self, branch):
        """ Set the branch in which this commit is supposed to be """
        #Not used now
        self.branch = branch
        #Check feature change and conflict
        self.feature = branch.feature

    def delbranch(self, branch):
        """ Notify this commit that a related branch is deleted """
        if self.branch == branch:
            self.branch = None
        #TODO Report in parent commits if needed

        if self.heads is not None:
            try:
                self.heads.remove(branch)
            except ValueError:
                pass

    def __str__(self):
        return b2a_hex(self.sha)

class Branch(object):
    def __init__(self, repo_cache, name, local):
        if repo_cache.branches.has_key(name):
            raise InvalidUnique
        repo_cache.branches[name] = self

        nameparts = name.split('/')
        if local:
            state, featname = nameparts[-2:]
            self.extraname = nameparts[:-2]
            self.featuser = None
        else:
            featuser, state, featname = nameparts[-3:]
            self.extraname = nameparts[:-3]
            self.featuser = repo_cache.get_username(featuser)

        self._stateid = _featstates.index(state)
        self.repo_cache = repo_cache
        self.name = name
        self.commit = None
        self.local = local
        self.feature = repo_cache.featupdate(featname, self)
        self.start = None
        self.time = None
        self.updated = None
        self.parent = None
        self.trash = []     # List of old commits to delete
        self.deleted = False

    def isstart(self):
        return self._stateid == 0

    def isfinal(self):
        return _featstates[self._stateid] == 'final'

    def fullname(self):
        """ Return the full name of the branch """
        state = _featstates[self._stateid]
        if self.local:
            return '/'.join(self.extraname + (
                _featstates[self._stateid],
                self.feature.name
                ))
        else:
            return '/'.join(self.extraname + (
                self.featuser,
                _featstates[self._stateid],
                self.feature.name
                ))

    def unsethead(self):
        """ Remove the reference to this branch as a head in related commit """
        if self.commit is not None:
            self.commit.unsethead(self)

    def updatecommits(self, repo, sha):
        """ Update branch info using repo (called from sync) """
        try:
            self.commit = self.repo_cache.commits[sha]
        except KeyError:
            self.commit = Commit(self.repo_cache, sha, head = self)
            self.repo_cache.commits[sha] = self.commit

        #TODO Get commit time
        self.time = 0

        #TODO Walk through commit and get start point(s)

    def delete(self):
        self.deleted = True
        self.feature.delbranch(self)

    def state(self):
        return _featstates[self._stateid]

    def __str__(self):
        return self.name

    def __repr__(self):
        return '%s (%s)' % (self.name, self.commit)


class Feature(object):
    def __init__(self, repo_cache, name, branch):
        if repo_cache.features.has_key(name):
            raise InvalidUnique
        repo_cache.features[name] = self

        self.name = name
        self.branches = set((branch,))
        self.mainbranch = branch
        self.pushed = False
        self.repo_cache = repo_cache

    def addbranch(self, branch):
        """ Update data of a branch related to this feature """
        if not branch in self.branches:
            self.branches.add(branch)

    def delbranch(self, branch):
        """ Notify the feature that a related branch is deleted """
        try:
            self.branches.remove(branch)
        except KeyError:
            pass

    def update(self):
        """ Update the feature data by reading the list of branches """
        stateid = 0
        branchlocal = None
        myremotebranch = None
        selectremote = None
        for branch in self.branches:
            verbose('Get %s' % branch)
            if not branch.local and branch.featuser == _MYREPO:
                verbose('My remote : %s' % branch)
                myremotebranch = branch
                self.pushed = True

            if branch._stateid > stateid:
                stateid = branch._stateid
                verbose('State to %s (%d)' % (_featstates[stateid], stateid))

            if branch.local and (
                    branchlocal is None
                    or branch._stateid > branchlocal._stateid):
                verbose('My local : %s' % branch)
                branchlocal = branch

            if not branch.local and branch._stateid >= stateid:
                if selectremote is None:
                    selectremote = branch
                elif selectremote._stateid < stateid:
                    selectremote = branch
                elif branch.time > selectremote.time:
                    selectremote = branch

        verbose('> %s selectremote : %s' % (self, selectremote))
        verbose('> %s branchlocal : %s' % (self, branchlocal))
        if branchlocal is not None:
            self.mainbranch = branchlocal
        else:
            self.mainbranch = selectremote

    def haslocal(self):
        return self.mainbranch.local

    def hasuser(self, featuser):
        for branch in self.branches:
            if branch.featuser == featuser:
                return True

        return False

    def heads(self):
        if self.mainbranch.local:
            return [self.mainbranch.local]
        else:
            return [branch for branch in self.branches
                    if branch._stateid == self.mainbranch._stateid]

    def __str__(self):
        return self.name

    def __repr__(self):
        return '%s %s' % (self.mainbranch, self.branches)


class RepoCache(object):
    def __init__(self):
        self.features = {}
        self.commits = {}
        self.branches = {}
        self.featusers = []

    def featupdate(self, featname, branch):
        if self.features.has_key(featname):
            feature = self.features[featname]
            feature.addbranch(branch)
        else:
            feature = Feature(self, featname, branch)

        return feature

    def get_username(self, featuser):
        try:
            return self.featusers[self.featusers.index(featuser)]
        except ValueError:
            self.featusers.append(featuser)
            return featuser

    def sethead(self, sha, branch):
        branch.unsethead()
        if self.commits.has_key(sha):
            self.commits[sha].sethead(branch)
        else:
            Commit(self, sha, head = branch)

    def _cleandeleted(self, repo):
        """ Check branches that must be removed from branches """
        return []

    def sync(self):
        """ Sync cache with real state of the repository """
        from dulwich.repo import Repo

        repo = Repo(_GITROOT)
        count = 0
        changed = []
        created = []

        #TODO Check DEVREF state

        for ref in repo.refs.subkeys('refs/heads/'):
            nameparts = ref.split('/')
            if len(nameparts) > 1 and nameparts[-2] in _featstates:
                count += 1
                sha = a2b_hex(repo.ref('refs/heads/%s' % ref))
                if self.branches.has_key(ref):
                    if sha != self.branches[ref].commit.sha:
                        changed.append((ref, sha, True))
                else:
                    created.append((ref, sha, True))

        #TODO Improve : only do this if some fetch or pull were performed
        for ref in repo.refs.subkeys('refs/remotes/'):
            nameparts = ref.split('/')
            if len(nameparts) > 1 and nameparts[-2] in _featstates:
                count += 1
                sha = a2b_hex(repo.ref('refs/remotes/%s' % ref))
                if self.branches.has_key(ref):
                    if sha != self.branches[ref].commit.sha:
                        changed.append((ref, sha, False))
                else:
                    created.append((ref, sha, False))

        branchlist = []
        featlist = []

        #Check deleted branches (except when new ones are detected)
        if len(created) == 0 and count < len(self.branches):
            featlist = self._cleandeleted(repo)

        #Nothing more to do if there are no created nor changed branches
        if len(created) == 0 and len(changed) == 0 and len(featlist) == 0:
            return

        #Create new branch object and set heads (just in commits)
        for branch_data in created:
            branchname, sha, local = branch_data
            branch = Branch(self, branchname, local)
            self.sethead(sha, branch)
            branchlist.append((branch, sha))
            if not branch.feature in featlist:
                featlist.append(branch.feature)

        for branch_data in changed:
            branchname, sha, local = branch_data
            branch = self.branches[branchname]
            self.sethead(branch)
            branchlist.append((branch, sha))
            if not branch.feature in featlist:
                featlist.append(branch.feature)

        #Update all commit datas related to branches (use heads previously set)
        for branch_data in branchlist:
            branch = branch_data[0]
            sha = branch_data[1]
            branch.updatecommits(repo, sha)

        for feature in featlist:
            feature.update()

        #Finally save newly updated cache
        print 'Save...'
        _save_cache(self)

    def listfeat(self, local = None, featuser = None):
        listout = []
        for feature in self.features.itervalues():
            hide = False
            if local is not None and feature.haslocal() != local:
                hide = True

            if featuser is not None and not feature.hasuser(featuser):
                hide = True

            if not hide:
                listout.append(feat)
            



