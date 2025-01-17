import pytest
import unittest
import subprocess
import re
from difflib import context_diff
import configparser, os, sys, shutil
from ptxprint.ptsettings import ParatextSettings
from collections import namedtuple
from filelock import FileLock

def w2u(path, endwithslash=True):
    """Windows to Unix filepath converter"""
    if path == "":
        return ""
    else:
        path = path.replace("\\", "/")
        return (path + ("/" if endwithslash else "")).replace("//", "/")

def quote(path):
    if " " in path:
        return '"' + path.strip('"') + '"'
    else:
        return path
    
if sys.platform == "win32":
    import winreg
    def queryvalue(base, value):
        return winreg.QueryValueEx(base, value)[0]
    
    def openkey(path):
        return winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\\" + path.replace("/", "\\"))

    ptob = openkey("Paratext/8")
    pt_settings = "."
    try:
        ptv = queryvalue(ptob, "ParatextVersion")
    except FileNotFoundError:
        for v in ('9', '8'):
            path = "C:\\My Paratext {} Projects".format(v)
            if os.path.exists(path):
                pt_settings = path
                pt_bindir = "C:\\Program Files (x86)\\Paratext {}".format(v)
                break
    else:
        if ptv:
            version = ptv[:ptv.find(".")]
            pt_bindir = queryvalue(ptob, 'Program_Files_Directory_Ptw'+version)
        pt_settings = queryvalue(ptob, 'Settings_Directory')
    
    pt_bindir = pt_bindir + ("\\" if pt_bindir[-1] != "\\" else "") + "xetex\\bin\\"
    
else:
    pt_bindir = ""

def call(*a, **kw):
    print("Calling", a, kw)
    return subprocess.call(*a, **kw)

def check_output(*a, **kw):
    print("Capturing", a, kw)
    return subprocess.check_output(*a, **kw)

def make_paths(projectsdir, project, config, xdv=False):
    testsdir = os.path.dirname(__file__)
    ptxcmd = [os.path.join(testsdir, "..", "python", "scripts", "ptxprint"),
                "--nofontcache",
                "-p", projectsdir, "-f", os.path.join(testsdir, "fonts")]
    if xdv:
        ptxcmd += ["-T"]
    if config is not None:
        ptxcmd += ['-c', config]
    ptxcmd += ["-P", project]
    if sys.platform == "win32":
        ptxcmd.insert(0, "python")
    cfg = configparser.ConfigParser()
    if config is not None:
        configpath = os.path.join(projectsdir, project, "shared", "ptxprint", config, "ptxprint.cfg")
        cfgname = config + "-"
    else:
        configpath = os.path.join(projectsdir, project, "shared", "ptxprint", "ptxprint.cfg")
        cfgname = ""
    cfg.read(configpath, encoding="utf-8")
    ptsettings = ParatextSettings(projectsdir, project)
    try:
        ismult = cfg.get("project", "bookscope") == "multiple"
    except configparser.NoOptionError:
        ismult = cfg.getboolean("project", "multiplebooks")
    if ismult:
        bks = [x for x in cfg.get("project", "booklist").split() \
            if os.path.exists(os.path.join(projectsdir, project, ptsettings.getBookFilename(x)))]
    else:
        bks = [cfg.get("project", "book")]
    if len(bks) > 1:
        filename = "{}{}_{}{}".format(cfgname, bks[0], bks[-1], project)
    else:
        filename = "{}{}{}".format(cfgname, bks[0], project)
    stddir = os.path.join(projectsdir, '..', 'standards', project)
    return (stddir, filename, testsdir, ptxcmd)

XdvInfo = namedtuple("XdvInfo", ["projectsdir", "project", "config", "stddir", "filename", "pdfpath", "xdvpath", "testsdir"])

@pytest.fixture(scope="class")
def xdv(request, projectsdir, project, config, starttime):
    (stddir, filename, testsdir, ptxcmd) = make_paths(projectsdir, project, config, xdv=True)
    pdftpath = os.path.join(projectsdir, project, "local", "ptxprint")
    os.makedirs(os.path.join(pdftpath, config), exist_ok=True)
    pdfpath = os.path.join(pdftpath, "ptxprint-"+filename+".pdf")
    xdvpath = os.path.join(pdftpath, config, "ptxprint-"+filename+".xdv")
    lockfile = xdvpath.replace(".xdv", ".lock")
    with FileLock(lockfile):
        try:
            t = os.path.getmtime(xdvpath)
        except FileNotFoundError:
            t = 0
        if t < starttime:
           assert call(ptxcmd) == 0
    request.cls.xdv = XdvInfo(projectsdir, project, config, stddir, filename, pdfpath, xdvpath, testsdir)

@pytest.mark.usefixtures("xdv")
class TestXetex: #(unittest.TestCase):
    def test_pdf(self):
        xdvcmd = " ".join([quote(w2u(pt_bindir, True)+"xdvipdfmx"),"-q", "-E", "-o", quote(w2u(self.xdv.pdfpath, False)) + " " + quote(w2u(self.xdv.xdvpath, False))])
        assert call(xdvcmd, shell=True) == 0

    def test_xdv(self, updatedata, pypy):
        xdvcmd = [os.path.join(self.xdv.testsdir, "..", "python", "scripts", "xdvcompare")]
        if pypy is not None:
            xdvcmd.insert(0, pypy)
        elif sys.platform == "win32":
            xdvcmd.insert(0, "python")

        fromfile = self.xdv.xdvpath
        tofile = os.path.join(self.xdv.stddir, self.xdv.filename+".xdv")
        if updatedata or (not os.path.exists(tofile) and os.path.exists(fromfile)):
            if not os.path.exists(self.xdv.stddir):
                os.makedirs(self.xdv.stddir)
            shutil.copy(fromfile, tofile)
            # pytest.xfail("No regression xdv. Copying...")
            return
        xdvcmd += [fromfile, tofile]
        if call(xdvcmd) != 0:
            pytest.xfail("xdvs are inconsistent")
