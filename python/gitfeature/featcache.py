import cPickle
from binascii import a2b_hex, b2a_hex
from posixpath import join, basename, dirname
from os.path import exists, join as join_file


_GITDIR = '.git'
_GITROOT = '.'
_DEVREF = 'heads/devel'
_MYREPO = 'mine'

def load_cache():
    pickle_file = join_file(_GITDIR, 'featcache')
    if exists(pickle_file):
        repo_cache = cPickle.load(open(pickle_file))
    else:
        repo_cache = RepoCache()

    return repo_cache


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
        self.integrated = False

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
        if self.repo_cache.check_integrated(self.name):
            self.integrated = True

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
        return '%50s : %s : %s' % (self.mainbranch, self.integrated, self.branches)

class CommitStore(object):
    def __init__(self):
        self.commits = {}
        self.devrefs = {}
        self.fixedfeat = {}

    def _mapnewcommits(self, sha, index = 0):
        sha_bin = a2b_hex(sha)
        max_index = 0
        while sha_bin is not None and not self.commits.has_key(sha_bin):
            commit = self.repo.commit(sha)
            if self.newcommits.has_key(sha_bin):
                if index > self.newcommits[sha_bin]:
                    self.newcommits[sha_bin] = index
                else:
                    index = self.newcommits[sha_bin]
            else:
                #TODO Check message to scan integrated features (instead of tag)
                self.newcommits[sha_bin] = index
            index += 1

            l = len(commit.parents)
            if l > 1:
                for sha in commit.parents:
                    tmp = self._mapnewcommits(sha, index)
                    if tmp > max_index:
                        max_index = tmp

                sha_bin = None
            elif l == 0:
                sha_bin = None
            else:
                sha = commit.parents[0]
                sha_bin = a2b_hex(sha)

        if sha_bin is not None:
            index += self.commits[sha_bin]
        if index > max_index:
            max_index = index

        return max_index

    def mapnewcommits(self, refheads, repo):
        """Record new integrated commits after devref update """
        self.repo = repo
        self.newcommits = {}
        self.integrated = {}

        max_index = 0
        #First count commit in reverse order using _mapnewcommits
        for refhead, sha in refheads.iteritems():
            if self.devrefs.has_key(refhead):
                committocheck = self.devrefs[refhead]
            else:
                committocheck = None
            #TODO Detect rebase (use committocheck)
            tmp = self._mapnewcommits(sha)
            if tmp > max_index:
                max_index = tmp

            self.devrefs[refhead] = sha

        #Now reverse commit count
        for sha, count in self.newcommits.iteritems():
            count = max_index - count
            verbose('Reverse count : %s : %d' % (b2a_hex(sha), count))
            self.commits[sha] = count

        #TODO To remove when tags will be replaced by commit message
        tags = {ref[11:] : h
                for ref, h in repo.get_refs().iteritems()
                if ref.startswith('refs/tags/@')}

        for tag, sha in tags.iteritems():
            sha = a2b_hex(sha)
            if self.newcommits.has_key(sha):
                tag = tag.rsplit('_', 1)[0]
                verbose('New feature integration detected : %s' % tag)
                self.integrated[tag] = sha

        del(self.newcommits)
        del(self.repo)

    def __str__(self):
        return '\n'.join(['%s : %s' % (count, b2a_hex(sha))
            for sha, count in self.commits.iteritems()])

class RepoCache(object):
    def __init__(self):
        self.features = {}
        self.commits = {}
        self.branches = {}
        self.featusers = []
        self.devrefs = {}

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

    def _load_commitstore(self):
        if not hasattr(self, 'commitstore') or self.commitstore is None:
            pickle_file = join_file(_GITDIR, 'featstore')
            if exists(pickle_file):
                self.commitstore = cPickle.load(open(pickle_file))
            else:
                self.commitstore = CommitStore()

    def _save_cache(self):
        if hasattr(self, 'commitstore') and self.commitstore is not None:
            print 'Save commitstore : %s' % self.commitstore.devrefs
            f = open('out', 'w')
            f.write(str(self.commitstore))
            f.close()
            pickle_file = join_file(_GITDIR, 'featstore')
            cPickle.dump(self.commitstore, open(pickle_file, 'wb', -1))
            del(self.commitstore)
        else:
            print 'No save commitstore'

        pickle_file = join_file(_GITDIR, 'featcache')
        cPickle.dump(self, open(pickle_file, 'wb'), -1)

    def check_integrated(self, featname):
        self._load_commitstore()

        if not hasattr(self.commitstore, 'integrated'):
            return 0
        if not self.commitstore.integrated.has_key(featname):
            return 0

        sha = self.commitstore.integrated[featname]
        return self.commitstore.commits[sha]

    def isindevref(self, sha):
        self._load_commitstore()
        if not self.commitstore.commits.has_key(sha):
            return 0
        return self.commitstore.commits.has_key(sha)

    def sync(self):
        """ Sync cache with real state of the repository """
        from dulwich.repo import Repo

        repo = Repo(_GITROOT)

        #TODO Manage multiple devref
        devref = _DEVREF
        basedevref = basename(devref)

        sha_hex = repo.ref('refs/%s' % devref)
        sha = a2b_hex(sha_hex)
        devref_tocheck = {}
        if (not self.devrefs.has_key(basedevref)
                or sha != self.devrefs[basedevref]):
            devref_tocheck[basedevref] = sha_hex
        if len(devref_tocheck) > 0:
            verbose('Changes on devrefs : %s' % devref_tocheck)
            self._load_commitstore()
            self.commitstore.mapnewcommits(devref_tocheck, repo)

            for name, sha in devref_tocheck.iteritems():
                self.devrefs[name] = a2b_hex(sha)
            all_check = True
        else:
            all_check = False

        count = 0
        changed = []
        created = []
        for ref in repo.refs.subkeys('refs/heads/'):
            nameparts = ref.split('/')
            if len(nameparts) > 1 and nameparts[-2] in _featstates:
                count += 1
                sha = a2b_hex(repo.ref('refs/heads/%s' % ref))
                if self.branches.has_key(ref):
                    if sha != self.branches[ref].commit.sha or all_check:
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
                    if sha != self.branches[ref].commit.sha or all_check:
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
            self.sethead(sha, branch)
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
        verbose('Save...')
        self._save_cache()

    def listfeat(self, local = None, featuser = None, active = True):
        listout = []
        print 'active %s ' % active
        for feature in self.features.itervalues():
            hide = False
            if local is not None and feature.haslocal() != local:
                hide = True

            if featuser is not None and not feature.hasuser(featuser):
                hide = True

            if active and feature.integrated:
                hide = True

            if not hide:
                listout.append(feature.mainbranch)

        return listout


