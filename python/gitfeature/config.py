from os import environ

class Config:
    pass

try:
    Config.DEVREF = environ['DEVREF']
except KeyError:
    Config.DEVREF = 'devel'

if Config.DEVREF[:8] == 'remotes/':
    Config.DEVREF = Config.DEVREF[8:]

try:
    Config.MYREPO = environ['REMOTE']
except KeyError:
    Config.MYREPO = 'mine'

#Suppose current directory is the repo root
Config.GITDIR = '.git'
Config.GITROOT = '.'

