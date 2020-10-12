import gettext
import locale
import os, sys, re
from inspect import currentframe
from ptxprint.ptsettings import books

APP = 'ptxprint'
MODIR = os.path.join(os.path.dirname(__file__), 'mo')

_ = gettext.gettext

def setup_i18n():
    if sys.platform.startswith('win'):
        if os.getenv('LANG') is None:
            lang, enc = locale.getdefaultlocale()
            os.environ['LANG'] = lang
    else:
        locale.bindtextdomain(APP, MODIR)
    locale.setlocale(locale.LC_ALL, '')
    gettext.bindtextdomain(APP, MODIR)

def f_(s):
    frame = currentframe().f_back
    return eval("f'{}'".format(_(s)), frame.f_locals, frame.f_globals)

def refKey(r, info=""):
    m = re.match(r"^(\D*)\s*(\d*)\.?(\d*)(\S*?)$", r)
    if m:
        return (books.get(m.group(1)[:3], 100), int(m.group(2) or 0), int(m.group(3) or 0), m.group(1)[3:], info, m.group(4))
    else:
        return (100, 0, 0, r, info, "")

def universalopen(fname, rewrite=False):
    """ Opens a file with the right codec from a small list and perhaps rewrites as utf-8 """
    fh = open(fname, "r", encoding="utf-8")
    try:
        fh.readline()
        fh.seek(0)
        return fh
    except ValueError:
        pass
    fh = open(fname, "r", encoding="utf-16")
    fh.readline()
    fh.seek(0)
    if rewrite:
        dat = fh.readlines()
        fh.close()
        with open(fname, "w", encoding="utf-8") as fh:
            for d in dat:
                fh.write(d)
        fh = open(fname, "r", encoding="utf-8", errors="ignore")
    return fh

