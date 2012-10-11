import sys, os
import re

def spaces(length):
    return (' ' * length)[0:length]

inLine = sys.stdin.readlines()
features = {}

try:
    exclude = sys.argv[1]
except:
    exclude = ''

if len(exclude) == 0:
    rc = None
else:
    rc = re.compile(exclude)

for l in inLine:
    l = l.strip()
    feat = os.path.basename(l)
    if not features.has_key(feat) and (
            rc is None
            or rc.match(l) is None):
        features[feat] = l


# for k, v in features.iteritems():
#     print '%s%s > %s' % (k, spaces(50 - len(k)), v)
for v in features.itervalues():
    print v



