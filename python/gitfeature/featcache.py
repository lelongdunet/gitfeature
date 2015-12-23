import cPickle
import sys
from binascii import a2b_hex, b2a_hex
from posixpath import join, basename, dirname
from os.path import exists, join as join_file
from itertools import imap, chain, ifilterfalse
from util import verbose, debug, initlog, print_err
from config import Config
import error

_CACHEVER = 11

initlog(join_file(Config.FEATDIR, 'featcache.log'))

def load_cache():
    pickle_file = join_file(Config.FEATDIR, 'featcache')
    if exists(pickle_file):
        try:
            repo_cache = cPickle.load(open(pickle_file))
        except AttributeError:
            verbose("AttributeError while loading cache. Re initialize!")
            repo_cache = RepoCache()
    else:
        if not exists(Config.FEATDIR):
            return None

        repo_cache = RepoCache()

    return repo_cache


#States are in priority order
_featstates = ('start', 'tmp', 'save', 'draft', 'final', 'archive')
_activestates = (3, 4)
_featsort = {
        'name' : lambda feature: feature.name,
        'fullname' : lambda feature: feature.mainbranch.name,
        'time' : lambda feature: feature.mainbranch.time
        }


def get_sha(obj):
    if isinstance(obj, Branch):
        return obj.commit.sha
    elif isinstance(obj, Commit):
        return obj.sha
    elif isinstance(obj, Feature):
        return obj.mainbranch.commit.sha
    else:
        return obj

class Commit(object):
    def __init__(self, repo_cache, sha, head = None, branch = None):
        if repo_cache.commits.has_key(sha):
            raise error.InvalidUnique
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
            if len(self.heads) == 0 and self.branch is None:
                del self.repo_cache.commits[self.sha]
        elif self.branch is None:
            del self.repo_cache.commits[self.sha]

    def __str__(self):
        return b2a_hex(self.sha)

class Branch(object):
    """ This class represent a git branch with its feature properties

    Branches represented by this class is either a start point or
    corresponds to a state of the feature.
    Following properties are available :
        - name : The name of the branch (this is also given by str())
        - commit : Commit object at head of this branch
        - error : if not None, this branch is in a bad state
        - local : True if this branch is local
        - stat : SHA or Branch instance of the related start point
        - time : Date of last modification of last commit
        - uptodate : True if this branch is above its base
        - parent : NC
        - delete : This branch is pending for deletion
    Other informations can be get through functions
    """

    def __init__(self, repo_cache, name, local):
        if repo_cache.branches.has_key(name):
            raise error.InvalidUnique
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
        self.error = None
        self.depend = False
        self.children = set()
        self.local = local
        self.feature = repo_cache.featupdate(featname, self)
        self.start = None
        self.root = None
        self.time = None
        self.uptodate = False
        self.parent = None
        self.trash = []     # List of old commits to delete

        if self.featuser == Config.MYREPO:
            #If it results from a pending commit, remove it
            localname = self.localname()
            localbranch = filter(
                    lambda branch: branch.name == localname,
                    repo_cache.pendingpush
                    )
            if len(localbranch) > 0:
                repo_cache.pendingpush.remove(localbranch[0])

    def isstart(self):
        """ Return True if this is a start point branch """
        return self._stateid == 0

    def isactive(self):
        """ Return True if this is an active branch to work on """
        return self._stateid in _activestates

    def isfinal(self):
        """ Return True if this is a final branch """
        return _featstates[self._stateid] == 'final'

    def isdraft(self):
        """ Return True if this is a draft branch """
        return _featstates[self._stateid] == "draft"

    def get_start(self):
        """ Return SHA of the start point """
        if isinstance(self.start, Branch):
            return self.start.commit.sha
        return self.start

    def get_startbranch(self):
        """ Return Branch instance of start point of None """
        if isinstance(self.start, Branch):
            return self.start
        return None

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

    def localname(self):
        """ Return local name of the branch (without repository name) """
        nameparts = list(chain(self.extraname, (
            self.featuser,
            _featstates[self._stateid],
            self.feature.name)
            ))
        if self.local:
            return '/'.join(nameparts)
        else:
            return '/'.join(nameparts[1:])

    def pushname(self):
        if self.local:
            return str(self)
        elif self.featuser == Config.MYREPO:
            return ':%s' % self.localname()
        elif self.isstart():
            return '%s:refs/heads/%s' % (
                    b2a_hex(self.commit.sha),
                    self.localname()
                    )
        else:
            print_err('%s != %s' % (self.featuser, Config.MYREPO))
            raise error.NoPushAllowedError

    def unsethead(self):
        """ Remove the reference to this branch as a head in related commit """
        if self.commit is not None:
            self.commit.unsethead(self)

    def relatedupdates(self):
        if self.isstart():
            return self.feature.branches
        else:
            return self.feature.relatedupdates()

    def _switch_depend(self, new_depend):
        if new_depend != self.depend:
            if self.depend:
                try:
                    self.depend.children.remove(self)
                except KeyError:
                    pass
            self.depend = new_depend
            if new_depend:
                new_depend.children.add(self)

    def recursechildren(self, localonly = True, get_starts = False):
        branches = set()

        for feat in self.feature.relatedfeatures():
            branch = feat.mainbranch
            if localonly and not branch.local:
                continue
            branches.add(branch)
            startbranch = branch.get_startbranch()
            if(get_starts and startbranch is not None):
                branches.add(startbranch)

            branches.update(branch.recursechildren(localonly, get_starts))

        return branches

    def updatecommits(self, repo):
        """ Update branch info using repo (called from sync) """
        if(hasattr(self, 'pending_sha')):
            sha = self.pending_sha
            del(self.pending_sha)

            try:
                self.commit = self.repo_cache.commits[sha]
            except KeyError:
                self.commit = Commit(self.repo_cache, sha, head = self)
                self.repo_cache.commits[sha] = self.commit
        else:
            sha = self.commit.sha

        try:
            commit = repo.get_object(b2a_hex(sha))

        except KeyError as e:
            self.error = e
            return

        self.time = commit.commit_time

        #Reset related errors
        self.error = None

        #Walk until start point
        start = None
        depend = None
        commit_count = 0
        while not self.repo_cache.isindevref(sha):
            if self.repo_cache.commits.has_key(sha):
                branches = self.repo_cache.commits[sha].heads
                #TODO Detect start points in commit message
                if start is None:
                    depend_set = set()
                    start_set = set()

                for branch in branches:
                    if (branch.isstart() and branch.feature == self.feature):
                        #Prefer local starts over remotes
                        if (start is None
                                or (branch.local and not start.local)):
                            start = branch
                    elif branch.isstart() and depend is None:
                        start_set.add(branch.feature)
                    elif(depend is None
                            and branch.isactive()
                            and branch.feature != self.feature):
                        depend_set.add(branch)

                if start is not None and depend is None:
                    #Select a depend feature which is not empty
                    for depend in depend_set:
                        if depend.feature not in start_set:
                            break

                    if depend is not None and depend.feature in start_set:
                        depend = None

                #TODO : Ensure depend is a local branch if one is available.
                if start is None:   depend = None
                elif depend is None: depend = self.depend

            #Get next commit
            if len(commit.parents) < 1:
                self.error = error.FeatureDetachedError(self)
                raise self.error

            if len(commit.parents) > 1:
                self.error = error.FeatureMergeError(self)
                raise self.error

            if start is None: commit_count += 1

            sha_hex = commit.parents[0]
            sha = a2b_hex(sha_hex)
            commit = repo.get_object(sha_hex)

        if not self.repo_cache.isindevref(sha):
            self.error = error.FeatureStartError(self)
            raise self.error

        #TODO Make local starts for local working branches
        #TODO The feature create command should also fork existing remotes
        #Make local start branch for local branches
        #if self.local and not start.local:
        #    local_start = Branch(self.repo_cache, start)


        if start is not None:
            self.start = start
            if depend:
                self._switch_depend(depend)
            else:
                print_err('No real depend > floating : %s' % self)
        else:
            self.start = sha
            self.depend = None
        self.root = sha
        self.commit_count = commit_count

    def check_depend(self):
        """ Check if depend branch is a valid one according to its state
            (must be called after feature update) """
        if self.error is not None:
            return

        if self.depend:
            depend_featbranch = self.depend.feature.mainbranch
            #update the parent branch if :
            #  - state of the parent feature changed
            #  - or parent branch does not exist any more
            if (self.depend._stateid != depend_featbranch._stateid
                    or (hasattr(self.depend, 'deleted')
                        and self.depend.deleted)
                    ):
                self.depend = depend_featbranch
            elif (not self.depend.local and depend_featbranch.local):
                self.depend = depend_featbranch

        #Branch is up to date if its start corresponds to its dependency
        if self.depend is not None and not self.depend:
            self.uptodate = False
        elif self.depend is None or self.depend.feature.integrated:
            #TODO in multiple devref check devref is coherent when integrated
            self.uptodate = self.repo_cache.isatdevref(self.start)
        else:
            self.uptodate = (get_sha(self.depend) == get_sha(self.start))

    def fulluptodate(self, checkthisuptodate = True):
        if checkthisuptodate and not self.uptodate:
            return False

        depend = self.depend
        if depend and isinstance(depend, Branch):
            return depend.fulluptodate()
        return True

    def dependnotuptodate(self):
        """ Get the first dependancy that is not up to date. """
        if not self.depend:
            return None
        if self.depend.feature.integrated:
            return None
        if not self.depend.uptodate:
            return self.depend
        return self.depend.dependnotuptodate()

    def delete(self):
        """ Set this branch to be deleted """
        self.feature.delbranch(self)
        self.commit.delbranch(self)
        self.deleted = True
        if self.depend:
            try:
                self.depend.children.remove(self)
            except KeyError:
                pass
        del self.repo_cache.branches[self.name]

    def state(self):
        """ Return current state of this branch """
        return _featstates[self._stateid]

    def samestate(self, branch):
        return self._stateid == branch._stateid

    def ismaxstate(self):
        return self.samestate(self.feature.mainbranch)

    def __str__(self):
        return self.name

    def __repr__(self):
        return '%s (%s)' % (self.name, self.commit)


class Feature(object):
    """ This class represent a feature.

    A feature can be associated with severall git branches and
    has severall states until it is integrated in one of 
    DEVREF branches.

    Following properties are available:
        - name : The name of the branch (this is also given by str())
        - error : if not None, this branch is in a bad state
        - pushed : True if the local branch of this feature has been pushed
        - pushuptodate : True if there are no changes since last push
        - integrated : True if this feature is integrated in one DEVREF
    Other informations can be get through functions
    """
    def __init__(self, repo_cache, name, branch):
        if repo_cache.features.has_key(name):
            raise error.InvalidUnique
        repo_cache.features[name] = self

        self.name = name
        self.error = None
        self.branches = set((branch,))
        self.mainbranch = branch
        self.pushed = False
        self.pushuptodate = False
        self.repo_cache = repo_cache
        self.integrated = False

    def addbranch(self, branch):
        """ Update data of a branch related to this feature """
        if not branch in self.branches:
            verbose('%s : New feature branch : %s' % (self, branch))
            self.branches.add(branch)

    def delbranch(self, branch):
        """ Notify the feature that a related branch is deleted """
        try:
            self.branches.remove(branch)
        except KeyError:
            pass

    def update(self):
        """ Update the feature data by reading the list of branches """
        if len(self.branches) == 0:
            verbose("Feature %s totally deleted" % self.name)
            del self.repo_cache.features[self.name]
            return None

        stateid = 0
        localbranch = None
        myremotebranch = None
        selectremote = None
        self.pushed = False
        for branch in self.branches:
            if not branch.local and branch.featuser == Config.MYREPO and (
                    myremotebranch is None or (
                        branch._stateid >= myremotebranch._stateid)
                    ):
                debug('My remote : %s' % branch)
                myremotebranch = branch
                self.pushed = True

            if branch._stateid > stateid:
                stateid = branch._stateid

            if branch.local and (
                    localbranch is None
                    or branch._stateid > localbranch._stateid):
                debug('My local : %s' % branch)
                localbranch = branch

            if (
                    not branch.local
                    and branch._stateid >= stateid
                    and branch.featuser != Config.MYREPO
                    ):
                if selectremote is None:
                    selectremote = branch
                elif selectremote._stateid < stateid:
                    selectremote = branch
                elif branch.time > selectremote.time:
                    selectremote = branch

        debug('%s : selectremote : %s' % (self, selectremote))
        if self.repo_cache.check_integrated(self.name):
            self.integrated = True
            self.pushuptodate = True
        #else:
        #    self.integrated = False

        #Local branch has priority only if it the highest state
        if (localbranch is not None
                and (selectremote is None
                    or selectremote._stateid <= localbranch._stateid)):
            self.mainbranch = localbranch
            self.pushuptodate = self.integrated or (self.pushed
                    and localbranch.commit == myremotebranch.commit
                    and localbranch.samestate(myremotebranch))
        else:
            self.mainbranch = selectremote

        if self.mainbranch is None:
            #This is a non regulare case : get a random mainbranch
            self.error = error.FeatureBadMain()
            self.mainbranch = self.branches.pop()
            self.branches.add(self.mainbranch)
        elif isinstance(self.error, error.FeatureBadMain):
            self.error = None

        if self.mainbranch.depend is not None and not self.mainbranch.depend:
            #Try to get the dependancy of any other branch
            for branch in self.branches:
                if branch.depend is None or branch.depend:
                    self.mainbranch.depend = branch.depend

        verbose('Main branch : %s' % self.mainbranch)

        #Check push consistency
        self.repo_cache.pendingpush.update(self.pushclean())

    def pushclean(self, rmlower = False):
        """ Return an iterable object of remote branches to be removed """
        if not self.pushed:
            return ()

        localbranches = {b._stateid:b for b in self.branches if b.local}
        myremotebranches = {b._stateid:b for b in self.branches
                if b.featuser == Config.MYREPO}

        #If there is no local branches for it remove everything
        if not self.mainbranch.local:
            return myremotebranches.itervalues()

        myremotebranch = myremotebranches[max(myremotebranches)]
        rmbranches = []

        if isinstance(self.error, error.FeaturePushError):
            self.error = None

        #Local feature start point can either be a local or a remote branch
        if isinstance(self.mainbranch.start, Branch):
            startcommit = self.mainbranch.start.commit.sha
        else:
            startcommit = self.mainbranch.start

        #Check start point
        if self.pushuptodate and (
                localbranches.has_key(0)
                and (
                    not myremotebranches.has_key(0)
                    or
                    myremotebranches[0].commit.sha != startcommit)
                ):
            if isinstance(self.mainbranch.start, Branch):
                rmbranches.append(self.mainbranch.start)
            elif myremotebranches.has_key(0):
                rmbranches.append(myremotebranches[0])

            self.error = error.FeaturePushError()
            verbose('Start point push error on %s (%s)' % (
                self,
                startcommit
                )
                )

        #If no local start point branch remove remote if exists
        if self.pushuptodate and (
                not localbranches.has_key(0)
                #Handle case when start point is a remote branch
                and not isinstance(self.mainbranch.start, Branch)
                and myremotebranches.has_key(0)):
            rmbranches.append(myremotebranches[0])
            self.error = error.FeaturePushError()
            verbose('Start point push error on %s' % self)

        #Remote branch to remove
        if not self.mainbranch.isactive() or rmlower:
            #If feature is not active never keep remote branch below
            #current state
            level_to_keep = self.mainbranch._stateid
        else:
            #Keep only the highest level remote branch
            level_to_keep = myremotebranch._stateid

        rmbranches.extend([myremotebranches[k]
            for k in myremotebranches.iterkeys()
            if k < level_to_keep and k > 0])

        if self.mainbranch.isstart():
            if not myremotebranches.has_key(0):
                #TODO > warning : Strange situation
                pass
            else:
                rmbranches.append(myremotebranches[0])
        return rmbranches

    def pushlist(self, force = False):
        """ Return iterable of branches to push (or remote to remove). """
        branches = list(self.pushclean(True))
        if self.mainbranch.depend and self.mainbranch.depend.local:
            dependfeat = self.mainbranch.depend.feature
            branches.extend(dependfeat.pushclean(True))
            branches.extend(dependfeat.pushlist(force))

        if self.mainbranch.local and (force or self.mainbranch.isactive()):
            branches.append(self.mainbranch)
            if isinstance(self.mainbranch.start, Branch):
                branches.append(self.mainbranch.start)

        return branches

    def haslocal(self):
        """ Return True if there is a local branch for this feature """
        return self.mainbranch.local

    def needpush(self):
        """ Return True if there is something to push for this feature. """
        return (self.mainbranch.local
                and self.pushed
                and not self.pushuptodate
                and not self.integrated)

    def depend(self):
        """ Return dependency of main branch """
        if not self.integrated:
            return self.mainbranch.depend
        return None

    def uptodate(self):
        """ Return True is up to date regarding its dependencies. """
        if not self.integrated:
            return self.mainbranch.uptodate
        return True

    def fulluptodate(self, checkthisuptodate = True):
        """ True if this feature and its dependancies are up to date. """
        if not self.integrated:
            return self.mainbranch.fulluptodate(checkthisuptodate)
        return True

    def hasuser(self, featuser):
        """ Return True if specified user has a branch for this feature """
        for branch in self.branches:
            if branch.featuser == featuser:
                return True

        return False

    def heads(self, uptodate = False):
        """ Return the list of active branches for this feature """
        if not uptodate:
            return [branch for branch in self.branches
                    if branch._stateid == self.mainbranch._stateid]
        else:
            return [branch for branch in self.branches
                    if (branch._stateid == self.mainbranch._stateid
                        and branch.uptodate)]

    def finalheads(self):
        """ Return the list of final branches """
        return [branch for branch in self.branches if branch.isfinal()]

    def draftheads(self):
        """ Return the list of draft branches """
        return [branch for branch in self.branches if branch.isdraft()]

    def relatedupdates(self):
        """ Return the set of branch that can be altered
            by the modification of this feature. """
        children = lambda branch: branch.children
        return set().union(*imap(children, self.branches))

    def relatedfeatures(self):
        """ Return the set of features that can be altered
            by the modification of this feature. """
        children = lambda branch: branch.children
        branchfeat = lambda branch: branch.feature
        return set(
                imap(branchfeat,
                    chain(
                        *imap(children, self.branches)
                        )
                    )
                )

    def __str__(self):
        return self.name

    def __repr__(self):
        return '%50s : %s : %s' % (
                self.mainbranch,
                self.integrated,
                self.branches)

class _CommitStore(object):
    def __init__(self):
        self.commits = {}
        self.devrefs = {}
        self.fixedfeat = {}

    def _mapnewcommits(self, sha, index = 0):
        sha_bin = a2b_hex(sha)
        max_index = 0
        while sha_bin is not None and not self.commits.has_key(sha_bin):
            commit = self.repo.get_object(sha)
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

            self.devrefs[refhead] = a2b_hex(sha)

        #Now reverse commit count
        for sha, count in self.newcommits.iteritems():
            count = max_index - count
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

        del self.newcommits
        del self.repo

    def __str__(self):
        return '\n'.join(['%s : %s' % (count, b2a_hex(sha))
            for sha, count in self.commits.iteritems()])

class RepoCache(object):
    """ This class hold cached data related to features and branches """
    def __init__(self):
        self.features = {}
        self.commits = {}
        self.branches = {}
        self.featusers = []
        self.devrefs = {}
        self.pendingpush = set()
        self.events = set()
        self.version = _CACHEVER

    def featupdate(self, featname, branch):
        """ Add a branch to the given feature (name) and create if needed. """
        if self.features.has_key(featname):
            feature = self.features[featname]
            feature.addbranch(branch)
        else:
            feature = Feature(self, featname, branch)

        return feature

    def get_username(self, featuser):
        """ Return the reference to the featuser string in featusers list.
            Create the item in the list if not found. """
        try:
            return self.featusers[self.featusers.index(featuser)]
        except ValueError:
            self.featusers.append(featuser)
            return featuser

    def sethead(self, sha, branch):
        """ Change the head commit of the given branch. """
        branch.unsethead()
        if self.commits.has_key(sha):
            self.commits[sha].sethead(branch)
        else:
            Commit(self, sha, head = branch)

    def _cleandeleted(self, repo):
        """ Check branches that must be removed from branches """
        branchlist = []
        for branch in self.branches.itervalues():
            if not branch.local:
                refname = 'refs/remotes/%s' % branch
            else:
                refname = 'refs/heads/%s' % branch
            try:
                repo.refs[refname]
            except KeyError:
                branchlist.append(branch)

        modfeatset = set()
        modbranchset = set()
        for branch in branchlist:
            verbose('delete branch %s' % branch)
            modbranchset.update(branch.relatedupdates())
            modfeatset.add(branch.feature)
            branch.delete()

        return modfeatset, modbranchset

    def _load_commitstore(self):
        if not hasattr(self, 'commitstore') or self.commitstore is None:
            pickle_file = join_file(Config.FEATDIR, 'featstore')
            if len(self.devrefs) > 0 and exists(pickle_file):
                self.commitstore = cPickle.load(open(pickle_file))
            else:
                self.commitstore = _CommitStore()

    def _save_cache(self):
        if hasattr(self, 'commitstore') and self.commitstore is not None:
            verbose('Save commitstore : %s' % self.commitstore.devrefs)
            f = open('out', 'w')
            f.write(str(self.commitstore))
            f.close()
            pickle_file = join_file(Config.FEATDIR, 'featstore')
            cPickle.dump(self.commitstore, open(pickle_file, 'wb', -1))
            del self.commitstore
        else:
            verbose('No save commitstore')

        sys.setrecursionlimit(5000)
        pickle_file = join_file(Config.FEATDIR, 'featcache')
        cPickle.dump(self, open(pickle_file, 'wb'), -1)

    def check_integrated(self, featname):
        self._load_commitstore()

        if not hasattr(self.commitstore, 'integrated'):
            return 0
        if not self.commitstore.integrated.has_key(featname):
            return 0

        sha = self.commitstore.integrated[featname]
        return self.commitstore.commits[sha]

    def isatdevref(self, sha):
        self._load_commitstore()
        return sha in self.commitstore.devrefs.values()

    def isindevref(self, sha):
        self._load_commitstore()
        if not self.commitstore.commits.has_key(sha):
            return 0
        return self.commitstore.commits.has_key(sha)

    def sync(self, addevent = '', all_check = False):
        """ Sync cache with real state of the repository """
        from dulwich.repo import Repo

        repo = Repo(Config.GITROOT)

        if not hasattr(self, 'version') or self.version != _CACHEVER:
            self.__init__()

        if not hasattr(self, 'events'):
            self.events = set()

        if len(addevent) > 0:
            self.events.add(addevent)

        #TODO Manage multiple devref
        devref = Config.DEVREF
        basedevref = basename(devref)

        try:
            sha_hex = repo.refs['refs/remotes/%s' % devref]
        except KeyError:
            sha_hex = repo.refs['refs/heads/%s' % devref]

        sha = a2b_hex(sha_hex)
        devref_tocheck = {}
        if (not self.devrefs.has_key(basedevref)
                or sha != self.devrefs[basedevref]):
            devref_tocheck[basedevref] = sha_hex
        if len(devref_tocheck) > 0:
            verbose('Changes on devrefs : %s' % devref_tocheck)
            self.events.add('integration')
            self._load_commitstore()
            self.commitstore.mapnewcommits(devref_tocheck, repo)

            for name, sha in devref_tocheck.iteritems():
                self.devrefs[name] = a2b_hex(sha)
            all_check = True

        count = 0
        changed = []
        created = []
        #Check changes in branches
        for ref in repo.refs.subkeys('refs/heads/'):
            nameparts = ref.split('/')
            if len(nameparts) > 1 and nameparts[-2] in _featstates:
                count += 1
                sha = a2b_hex(repo.refs['refs/heads/%s' % ref])
                try:
                    if sha != self.branches[ref].commit.sha or all_check:
                        changed.append((ref, sha, True))
                except KeyError:
                    created.append((ref, sha, True))

        #TODO Improve : only do this if some fetch or pull were performed
        for ref in repo.refs.subkeys('refs/remotes/'):
            nameparts = ref.split('/')
            if len(nameparts) > 1 and nameparts[-2] in _featstates:
                count += 1
                sha = a2b_hex(repo.refs['refs/remotes/%s' % ref])
                try:
                    if sha != self.branches[ref].commit.sha or all_check:
                        changed.append((ref, sha, False))
                except KeyError:
                    created.append((ref, sha, False))

        modbranchset = set()
        modfeatset = set()

        #Check deleted branches (except when new ones are detected)
        if (count - len(created)) < len(self.branches):
            self.events.add('delete')
            modfeatset, modbranchset = self._cleandeleted(repo)

        #Nothing more to do if there are no created nor changed branches
        if len(created) == 0 and len(changed) == 0 and len(modfeatset) == 0:
            if len(addevent) > 0:
                self._save_cache()
            return

        if len(created) > 0:    self.events.add('created')
        if len(changed) > 0:    self.events.add('changed')

        #Create new branch object and set heads (just in commits)
        for branch_data in created:
            branchname, sha, local = branch_data
            branch = Branch(self, branchname, local)
            self.sethead(sha, branch)
            #Pending sha is used in updatecommits()
            branch.pending_sha = sha
            modbranchset.add(branch)
            modbranchset.update(branch.relatedupdates())
            modfeatset.add(branch.feature)

        for branch_data in changed:
            branchname, sha, local = branch_data
            branch = self.branches[branchname]
            self.sethead(sha, branch)
            #Pending sha is used in updatecommits()
            branch.pending_sha = sha
            modbranchset.add(branch)
            modbranchset.update(branch.relatedupdates())
            modfeatset.add(branch.feature)

        #Update all commit datas related to branches (use heads previously set)
        for branch in modbranchset:
            try:
                branch.updatecommits(repo)
            except error.BranchError as e:
                verbose('Error on branch %s : %s' % (basename(str(branch)), e))

        for feature in modfeatset:
            feature.update()

        for branch in modbranchset:
            branch.check_depend()

        #Forget removed remote branches
        self.pendingpush = set(ifilterfalse(
            lambda branch: hasattr(branch, 'deleted'),
            self.pendingpush))

        #Finally save newly updated cache
        self._save_cache()
        verbose('-' * 60)

    def listfeat(self, local = None,
            featuser = None,
            integrated = False,
            uptodate = False,
            state = None,
            sort = None,
            old = None,
            reverse = False):
        listout = []
        if isinstance(state, str):
            state = state.split(',')

        if old is not None:
            from time import time

        for feature in self.features.itervalues():
            hide = False
            hide |= local is not None and feature.haslocal() != local
            hide |= featuser is not None and not feature.hasuser(featuser)
            hide |= state is not None and not feature.mainbranch.state() in state
            hide |= uptodate and not feature.uptodate()
            hide |= integrated ^ feature.integrated
            hide |= old is not None and feature.mainbranch.time > time() - old

            if not hide:
                listout.append(feature)

        if sort is not None and _featsort.has_key(sort):
            listout.sort(key=_featsort[sort], reverse = reverse)
        return listout

    def read_events(self):
        if hasattr(self, 'events') and len(self.events) > 0:
            events = self.events
            self.events = set()
            self._save_cache()
            return events

        return None

    def get_feature(self, featname, nocheck = False):
        """ Retrieve a feature object from its name """
        featname = basename(featname)
        dependlook = 0
        while featname[-1] == '^':
            featname = featname[:-1]
            dependlook += 1

        if not self.features.has_key(featname):
            raise error.NotFoundFeature
        feature = self.features[featname]
        while dependlook > 0 and feature is not None:
            feature = feature.depend()
            if feature:
                feature = feature.feature
            dependlook -= 1

        if not nocheck and feature is not None:
            if feature.mainbranch.error is not None:
                raise feature.mainbranch.error
            if feature.error is not None:
                raise feature.error
        return feature

    def get_branch(self, branchname):
        try:
            feat = self.get_feature(branchname)
        except error.NotFoundFeature:
            return branchname

        try:
            return self.branches[branchname]
        except:
            return feat.mainbranch

    def get_dereference(self, branchname):
        if '/' in branchname:
            return branchname
        try:
            feat = self.get_feature(branchname)
            return feat.mainbranch
        except error.NotFoundFeature:
            return branchname

    def get_isfeaturebranch(self, branchname):
        """ Check if the given branch is related to an existing feature """
        try:
            self.get_feature(branchname)
        except error.BranchError:
            pass
        return 'y'

    def get_start(self, featname):
        """ Return SHA of the start point of the given feature """
        return b2a_hex(self.get_branch(featname).get_start())

    def get_branches(self, featname):
        """ Return list of branches of the given feature """
        return ' '.join(map(str, self.get_feature(featname).heads()))

    def get_allbranches(self, featname):
        """ Return all branches of the feature (any state) """
        return ' '.join(imap(str, self.get_feature(featname).branches))

    def get_locals(self, featname):
        """ Return all local branches of the feature (any state) """
        return ' '.join([str(branch) for branch in
            self.get_feature(featname, True).branches
            if branch.local])

    def get_final(self, featname):
        """ Return the first final branch of the given feature """
        try:
            return self.get_feature(featname).finalheads()[0]
        except IndexError:
            return ''

    def get_finals(self, featname):
        """ Return the list of final branches of the given feature """
        return '\n'.join(imap(str, self.get_feature(featname).finalheads()))

    def get_draftbranch(self, featname):
        """ Return the closest draft branch """
        branch = self.get_branch(featname)
        if branch.isdraft():
            return branch
        elif branch.feature.mainbranch.isdraft():
            return branch.feature.mainbranch
        try:
            return branch.feature.draftheads()[0]
        except IndexError:
            return ''

    def get_state(self, featname):
        """ Return current state of the given feature """
        return self.get_branch(featname).state()

    def get_depend(self, featname):
        """ Return the parent branch of the given branch or feature """
        return self.get_branch(featname).depend

    def get_smartdepend(self, featname):
        """ Return the real SHA on which to update the branch. """
        #TODO Manage multiple devref
        devref = self.devrefs[basename(Config.DEVREF)]
        depend = self.get_branch(featname).depend
        if depend is not None and not depend:
            return ''
        elif depend is None or depend.feature.integrated:
            return b2a_hex(devref)
        else:
            return b2a_hex(depend.commit.sha)

    def get_related(self, branchname):
        """ For debug purpose only """
        return self.get_branch(branchname).relatedupdates()

    def get_featrelated(self, featname):
        """ For debug purpose only """
        return self.get_feature(featname).relatedupdates()

    def get_root(self, branchname):
        """ Return root of the branch (commit which is in devel) """
        return b2a_hex(self.get_branch(branchname).root)

    def get_isworkingbranch(self, branchname):
        """ Check if the given branch is valid for working on """
        branch = self.get_branch(branchname)
        if branch.local and branch.ismaxstate():
            return 'y'
        raise error.NotWorkingBranchError

    def get_workingbranch(self, branchname):
        """ Check if the closest working or empty string if none """
        branch = self.get_branch(branchname)
        if branch.local and branch.ismaxstate():
            return branch
        branch = branch.feature.mainbranch
        if branch.local:
            return branch
        return ''

    def get_shortstate(self, featname):
        feat = self.get_feature(featname)
        if feat.integrated:
            return ">I : feature already integrated"
        elif not feat.mainbranch.local:
            return ">R : remote feature"
        elif feat.mainbranch.isfinal():
            return ">F : feature being finalized"
        else:
            return ">D : draft feature"

    def get__viewpush(self, featname):
        """ For debug : view list of feature branches to push """
        feature = self.get_feature(featname, True)
        return '\n'.join(imap(str, feature.pushlist(True)))

    def get_push(self, featname):
        """ Return list of branches to push to update a remote feature """
        feature = self.get_feature(featname, True)
        pushname = lambda branch: branch.pushname()
        return '\n'.join(imap(pushname, feature.pushlist(True)))

    def get_pushauto(self, featname):
        """ Return list of branches to push to update a remote feature """
        feature = self.get_feature(featname, True)
        pushname = lambda branch: branch.pushname()
        return '\n'.join(imap(pushname,
            chain(
                feature.pushlist(True),
                self.pendingpush
                )
            )
            )

    def get_mainbranch(self, featname):
        """ Return the main working branch of the given feature """
        return self.get_feature(featname, True).mainbranch

    def get_islocal(self, featname):
        """ Check if the given feature has local branches """
        if self.get_feature(featname, True).haslocal():
            return 'y'
        raise error.NoLocalBranch

    def get_isintegrated(self, featname):
        """ Check if the given feature is integrated """
        if self.get_feature(featname).integrated:
            return 'y'
        raise error.NotIntegrated

    def get_isuptodate(self, featname):
        """ Check if the given feature is up to date """
        if self.get_feature(featname).uptodate():
            return 'y'
        raise error.NotUpToDate

    def get_dependnotuptodate(self, featname):
        """ Get the name of the first dependant feature not up to date."""
        feature = self.get_feature(featname)
        baddepend = feature.mainbranch.dependnotuptodate()
        if isinstance(baddepend, Branch):
            return baddepend.feature

        return ''

    def get_relatedlocalbranches(self, branchname):
        """ Get all parent and dependant loacal branches (including starts) """
        branch = self.get_branch(branchname)
        branches = branch.recursechildren(True, True)

        while branch and branch.local:
            branches.add(branch)
            startbranch = branch.get_startbranch()
            if(startbranch is not None):
                branches.add(startbranch)

            branch = branch.depend

        return '\n'.join(map(str, branches))

    def get_relatedbranches(self, branchname):
        """ Get all parent and dependant branches (including starts) """
        branch = self.get_branch(branchname)
        branches = branch.recursechildren(False, True)

        while branch:
            branches.add(branch)
            startbranch = branch.get_startbranch()
            if(startbranch is not None):
                branches.add(startbranch)

            branch = branch.depend

        return '\n'.join(map(str, branches))

