class Error(Exception):
    pass

class InvalidUnique(Error):
    pass

class NoPushAllowedError(Error):
    pass

class BranchError(Error):
    pass

class FeatureMergeError(BranchError):
    pass

class FeaturePushError(BranchError):
    pass

class FeatureStartError(BranchError):
    pass

class FeatureBadMain(BranchError):
    pass

class NotWorkingBranchError(BranchError):
    pass

class NoLocalBranch(BranchError):
    pass

class NotIntegrated(BranchError):
    pass

class NotUpToDate(BranchError):
    pass

class NotFoundFeature(Error):
    pass


