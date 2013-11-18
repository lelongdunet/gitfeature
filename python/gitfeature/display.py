import time
from binascii import a2b_hex, b2a_hex

class TermDisp:
    GREEN='\033[1;32m'
    NORMAL='\033[0;39m'
    RED='\033[1;31m'
    PINK='\033[1;35m'
    BLUE='\033[1;34m'
    WHITE='\033[0;02m'
    LIGHT='\033[1;08m'
    YELLOW='\033[1;33m'
    CYAN='\033[1;36m'
    UNDERLINE='\033[04;39m'
    INVERTED='\033[07;39m'
    BLINK='\033[05;39m'
    BOLD='\033[01;39m'
    GREENBOLD='\033[01;32m'


    ERRCOL='%s%s' % (NORMAL, RED)
    WARNCOL='\033[0;37;44;1m'
    IMPORTANT='%s%s%s' % (NORMAL, UNDERLINE, GREEN)
    TITLE='%s%s%s' % (NORMAL, UNDERLINE, BOLD)
    HIGHLIGHT='%s%s' % (NORMAL, GREENBOLD)

    def __init__(self):
        self.buffer = []
        self.currentindent = 0
        self.linestart = True
        self.listmode = False

    def disp(self, text, newline = False, font = None):
        if font is not None:
            if newline: text = '%s%s%s\n' % (font, text, self.NORMAL)
            else: text = '%s%s%s' % (font, text, self.NORMAL)
        else:
            if newline: text = '%s\n' % text

        if(self.listmode):
            linestart_str = '%s- ' % (' ' * self.currentindent)
        else:
            linestart_str = ' ' * self.currentindent

        if self.linestart:
            self.buffer.append('%s%s' % (linestart_str, text))
        else:
            self.buffer.append(text)
        self.linestart = newline

    def title(self, text):
        self.currentindent = 0
        self.disp('\n%s' % text, True, self.TITLE)
        self.currentindent = 2

    def highlight(self, text, newline = False):
        self.disp(text, newline, self.HIGHLIGHT)

    def error(self, text, newline = True):
        self.disp(text, newline, self.ERRCOL)

    def warning(self, text, newline = True):
        self.disp(text, newline, self.WARNCOL)

    def important(self, text, newline = False):
        self.disp(text, newline, self.IMPORTANT)

    def ul(self, text, newline):
        self.disp(text, newline, self.UNDERLINE)

    def bold(self, text, newline):
        self.disp(text, newline, self.BOLD)

    def startlist(self):
        if self.listmode:
            return

        self.currentindent += 2
        self.listmode = True

    def endlist(self):
        if not self.listmode:
            return

        self.currentindent -= 2
        self.listmode = False

    def flush(self):
        s = ''.join(self.buffer)
        self.buffer = []
        return s

    def printall(self):
        print ''.join(self.buffer)
        self.buffer = []

def debug_disp():
    disp = TermDisp()
    disp.disp('Test some text to display from featcache ...\n', True)
    disp.title('Begin the test')
    disp.disp('First line of the test', True)
    disp.disp('Second line with ')
    disp.highlight('some formatting ')
    disp.important('and some important text', True)
    disp.error('This is the final error line')
    disp.title('Here is the list test : ')
    disp.disp('The content of the list is : ', True)
    disp.startlist()
    disp.highlight('Highlight item', True)
    disp.important('Important item', True)
    disp.disp('Normal item', True)
    disp.disp('Last normal item', True)
    disp.endlist()
    disp.disp('End is here', True)


    disp.printall()

def show_feature(disp, repo_cache, featname):
    feature = repo_cache.get_feature(featname, True)
    if feature is None:
        disp.error("No valid feature specified!")
        return disp.flush()

    disp.disp('Feature :        ')
    disp.important(str(feature), True)
    if feature.mainbranch.error is not None:
        error_text = 'Error on main branch : %s' % feature.mainbranch.error
    if feature.error is not None:
        error_text = 'Error : %s ' % feature.error
    else:
        error_text = None

    if error_text is not None:
        disp.error(error_text)

    disp.disp('', True)
    disp.disp('State :          ')
    disp.highlight(repo_cache.get_shortstate(featname), True)
    if feature.mainbranch.depend:
        disp.disp('Depend :         ')
        disp.highlight(feature.mainbranch.depend.feature, True)
    elif feature.mainbranch.depend is not None:
        disp.error('Dependancy not found!')

    disp.disp('Last change :    ')
    branchdate = time.localtime(feature.mainbranch.time)
    disp.highlight(time.strftime("%a, %d %b %Y %H:%M:%S", branchdate), True)

    if hasattr(feature.mainbranch, 'commit_count'):
        disp.disp('Commit count :   ')
        disp.highlight(feature.mainbranch.commit_count, True)

    disp.disp('Root commit :    ')
    disp.disp(b2a_hex(feature.mainbranch.root), True)

    if not feature.uptodate():
        disp.error('Update needed :  ', False)
        disp.disp(repo_cache.get_smartdepend(featname), True)

    disp.title('Branches')
    disp.startlist()
    for branch in feature.heads():
        if(branch == feature.mainbranch):
            disp.important(repr(branch), True)
        else:
            disp.highlight(repr(branch), True)
    disp.endlist()

    related = feature.relatedfeatures()
    if len(related) > 0:
        disp.title('Related features')
        disp.startlist()
        for branch in related:
            disp.disp(branch, True)
        disp.endlist()

    return disp.flush()

