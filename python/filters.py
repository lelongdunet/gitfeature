import sys, os

def spaces(length):
    return (' ' * length)[0:length]

inLine = sys.stdin.readlines()
features = {}

for l in inLine:
    l = l.strip()
    feat = os.path.basename(l)
    if not features.has_key(feat):
        features[feat] = l


# for k, v in features.iteritems():
#     print '%s%s > %s' % (k, spaces(50 - len(k)), v)
for v in features.itervalues():
    print v



