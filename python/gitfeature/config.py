from os import environ

class Config:
    pass

Config.DEVREF = environ['DEVREF']
Config.REMOTE = environ['REMOTE']
try:
    Config.DEVREF = environ['DEVREF']
except KeyError:
    Config.DEVREF = 'devel'

try:
    Config.MYREPO = environ['REMOTE']
except KeyError:
    Config.MYREPO = 'mine'

#Suppose current directory is the repo root
Config.GITDIR = '.git'
Config.GITROOT = '.'

