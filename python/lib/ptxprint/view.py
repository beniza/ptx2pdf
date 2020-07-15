
import configparser, os, re, regex, random, collections
from .texmodel import ModelMap, TexModel, universalopen
from .ptsettings import ParatextSettings, allbooks, books, bookcodes, chaps
from .font import TTFont
import pathlib, os, sys
from configparser import NoSectionError, NoOptionError, _UNSET
from zipfile import ZipFile, ZIP_DEFLATED
from io import StringIO

VersionStr = "0.8.8 beta"

pdfre = re.compile(r".+[\\/](.+)\.pdf")

varpaths = (
    ('prjdir', ('settings_dir', 'prjid')),
    ('settingsdir', ('settings_dir',)),
    ('workingdir', ('working_dir',)),
)

def newBase(fpath):
    doti = fpath.rfind(".")
    f = os.path.basename(fpath[:doti])
    cl = re.findall(r"(?i)_?((?=ab|cn|co|hk|lb|bk|ba|dy|gt|dh|mh|mn|wa|dn|ib)..\d{5})[abc]?$", f)
    if cl:
        return cl[0].lower()
    else:
        return re.sub('[()&+,. ]', '_', f.lower())

class Path(pathlib.Path):

    _flavour = pathlib._windows_flavour if os.name == "nt" else pathlib._posix_flavour

    @staticmethod
    def create_varlib(aView):
        res = {}
        for k, v in varpaths:
            res[k] = pathlib.Path(*[getattr(aView, x) for x in v])
        res['pdfassets'] = pathlib.Path(os.path.abspath(os.path.dirname(__file__)), 'PDFassets')
        return res

    def __new__(cls, txt, view=None):
        if view is None or not txt.startswith("${"):
            return pathlib.Path.__new__(cls, txt)
        varlib = cls.create_varlib(view)
        k = txt[2:txt.find("}")]
        return pathlib.Path.__new__(cls, varlib[k], txt[len(k)+4:])

    def withvars(self, aView):
        varlib = self.create_varlib(aView)
        bestl = len(str(self))
        bestk = None
        for k, v in varlib.items():
            try:
                rpath = self.relative_to(v)
            except ValueError:
                continue
            if len(str(rpath)) < bestl:
                bestk = k
        if bestk is not None:
            return "${"+bestk+"}/"+rpath.as_posix()
        else:
            return self.as_posix()


class ViewModel:
    _attributes = {
        # modelname: (attribute, isMultiple, label)
        "project/frontincludes":    ("FrontPDFs", True, "lb_inclFrontMatter"),
        "project/backincludes":     ("BackPDFs", True, "lb_inclBackMatter"),
        "project/selectscript":     ("customScript", False, None),
        "paper/watermarkpdf":       ("watermarks", False, "lb_applyWatermark"),
        "fancy/pageborderpdf":      ("pageborder", False, "lb_inclPageBorder"),
        "fancy/sectionheaderpdf":   ("sectionheader", False, "lb_inclSectionHeader"),
        "fancy/versedecoratorpdf":  ("versedecorator", False, "lb_inclVerseDecorator"),
        "document/customfigfolder": ("customFigFolder", False, None),
        "document/customoutputfolder": ("customOutputFolder", False, None)
    }
    _settingmappings = {
        "notes/xrcallers": "crossrefs",
        "notes/fncallers": "footnotes"
    }
    _activekeys = {
        "document/diglotsecprj": "updateDiglotConfigList"
    }

    def __init__(self, settings_dir, workingdir):
        self.settings_dir = settings_dir
        self.fixed_wd = workingdir != None
        self.working_dir = workingdir
        self.ptsettings = None
        self.customScript = None
        self.FrontPDFs = None
        self.BackPDFs = None
        self.watermarks = None
        self.pageborder = None
        self.sectionheader = None
        self.versedecorator = None
        self.customFigFolder = None
        self.customOutputFolder = None
        self.prjid = None
        self.configId = None
        self.isDisplay = False

        # private to this implementation
        self.dict = {}

    def doError(self, txt, secondary=None):
        print(txt)
        if secondary is not None:
            print(secondary)

    def msgQuestion(self, q1, q2):
        print("Answering \"no\" to: " + q1)
        print(q2)
        return False

    def parse_fontname(self, font):
        m = re.match(r"^(.*?)(\d+(?:\.\d+)?)$", font)
        if m:
            return [m.group(1), int(m.group(2))]
        else:
            return [font, 0]

    def get(self, wid, default=None, sub=0, asstr=False, skipmissing=False):
        if wid.startswith("bl_"):
            return (self.dict.get(wid + "/name", None), self.dict.get(wid + "/style", None))
        return self.dict.get(wid, default)

    def set(self, wid, value, skipmissing=False):
        if wid.startswith("bl_"):
            self.setFont(wid, *value)
        elif wid.startswith("s_"):
            self.dict[wid] = "{:.3f}".format(float(value))
        else:
            self.dict[wid] = value

    def baseTeXPDFname(self):
        bks = self.getBooks()
        if self.working_dir == None:
            self.working_dir = os.path.join(self.settings_dir, self.prjid, 'PrintDraft')
        cfgname = self.configName()
        if cfgname is None:
            cfgname = ""
        else:
            cfgname = "-" + cfgname
        if len(bks) > 1:
            fname = "ptxprint{}-{}_{}{}".format(cfgname, bks[0], bks[-1], self.prjid)
        else:
            fname = "ptxprint{}-{}{}".format(cfgname, bks[0], self.prjid)
        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)
        return os.path.join(self.working_dir, fname)
        
    def getBooks(self):
        bl = self.get("t_booklist", "").split()
        if not self.get('c_multiplebooks'):
            return [self.get("ecb_book")]
        elif len(bl):
            blst = []
            for b in bl:
                bname = self.getBookFilename(b, self.prjid)
                if os.path.exists(os.path.join(self.settings_dir, self.prjid, bname)):
                    blst.append(b)
            return blst
        else:
            # return self.booklist
            return []

    def getBookFilename(self, bk, prjid):
        if self.ptsettings is None or self.prjid != prjid:
            self.ptsettings = ParatextSettings(self.settings_dir, prjid)
        fbkfm = self.ptsettings['FileNameBookNameForm']
        bknamefmt = (self.ptsettings['FileNamePrePart'] or "") + \
                    fbkfm.replace("MAT","{bkid}").replace("41","{bkcode}") + \
                    (self.ptsettings['FileNamePostPart'] or "")
        fname = bknamefmt.format(bkid=bk, bkcode=bookcodes.get(bk, 0))
        return fname

    def setFont(self, btn, name, style):
        self.dict[btn+"/name"] = name
        self.dict[btn+"/style"] = style

    def onFontChanged(self, fbtn):
        font_info = self.get("bl_fontR")
        f = TTFont(*font_info)
        if "Silf" in f:
            self.set("c_useGraphite", True)
        else:
            self.set("c_useGraphite", False)
        silns = "{urn://www.sil.org/ldml/0.1}"
        if self.get("t_fontfeatures") == "":
            d = self.ptsettings.find_ldml('.//special/{1}external-resources/{1}font[@name="{0}"]'.format(f.family, silns))
            if d is not None:
                featstring = d.get('features', '')
                self.set("t_fontfeatures", featstring)
        for s in ('Bold', 'Italic', 'Bold Italic'):
            sid = "".join(x[0] for x in s.split())
            esid = s.lower().replace(" ", "")
            w = "bl_font"+sid
            nf = TTFont(f.family, style = " ".join(s.split()))
            if nf.filename is None:
                styles = s.split()
                if len(styles) > 1:
                    bf = TTFont(f.family, style=styles[0])
                    if bf.filename is not None:
                        self.set("s_{}embolden".format(esid), 0)
                        styles.pop(0)
                    else:
                        bf = f
                else:
                    bf = f
                self.set(w, (bf.family, bf.style))
                self.set("c_fake"+esid, True)
                for t in styles:
                    if t == 'Bold':
                        self.set("s_{}embolden".format(esid), 2)
                    elif t == 'Italic':
                        self.set("s_{}slant".format(esid), 0.15)
            else:
                self.set(w, (nf.family, nf.style))
                self.set("c_fake"+esid, False)

    def updateSavedConfigList(self):
        pass

    def updateDiglotConfigList(self):
        pass

    def updateBookList(self):
        pass

    def setPrjid(self, prjid, saveCurrConfig=False):
        return self.updateProjectSettings(prjid, saveCurrConfig=saveCurrConfig)

    def setConfigId(self, configid, saveCurrConfig=False, force=False):
        return self.updateProjectSettings(self.prjid, saveCurrConfig=saveCurrConfig, configName=configid, forceConfig=force)

    def updateProjectSettings(self, prjid, saveCurrConfig=False, configName=None, forceConfig=False):
        currprj = self.prjid
        readConfig = False
        if currprj is None or currprj != prjid:
            if currprj is not None and saveCurrConfig:
                self.writeConfig()
                self.updateSavedConfigList()
                self.set("t_savedConfig", "")
                self.set("t_configNotes", "")
            self.ptsettings = None
            self.prjid = self.get("fcb_project") if prjid is None else prjid
            self.configId = None
            if self.prjid:
                self.ptsettings = ParatextSettings(self.settings_dir, self.prjid)
                self.updateBookList()
            if not self.prjid:
                return False
            if not self.fixed_wd:
                self.working_dir = os.path.join(self.settings_dir, self.prjid, 'PrintDraft')
            readConfig = True
        if readConfig or self.configId != configName:
            res = self.readConfig(cfgname=configName)
            if res or forceConfig:
                self.configId = configName
            return res
        else:
            return True

    def getDialogTitle(self):
        prjid = "  -  " + (self.get("fcb_project") or "")
        if prjid == "  -  ":
            return "PTXprint [{}] - Welcome! Start by selecting a project to work with...".format(VersionStr)
        else:
            if self.get('c_multiplebooks'):
                bks = self.get('t_booklist').split()
            else:
                bks = [self.get('ecb_book')]
                
            if len(bks) == 2:
                bks = bks[0] + "," + bks[1]
            elif len(bks) <= 4:
                bks = ",".join(bks)
            elif len(bks) > 4:
                bks = bks[0] + "," + bks[1] + "..." + bks[-2] + "," + bks[-1]
            else:
                try:
                    bks = bks[0]
                except IndexError:
                    bks = "No book selected!"
            return "PTXprint [{}] {} ({}) {}".format(VersionStr, prjid, bks, self.get("ecb_savedConfig") or "")

    def configName(self):
        return self.configId or None

    def configPath(self, cfgname=None, makePath=False):
        if self.settings_dir is None or self.prjid is None:
            return None
        prjdir = os.path.join(self.settings_dir, self.prjid, "shared", "ptxprint")
        if cfgname is not None and len(cfgname):
            prjdir = os.path.join(prjdir, cfgname)
        if makePath:
            os.makedirs(prjdir,exist_ok=True)
        return prjdir

    def readConfig(self, cfgname=None):
        if cfgname is None:
            cfgname = self.configName() or ""
        path = os.path.join(self.configPath(cfgname), "ptxprint.cfg")
        if not os.path.exists(path):
            return False
        #print("Reading config: {}".format(path))
        config = configparser.ConfigParser()
        config.read(path, encoding="utf-8")
        self.versionFwdConfig(config)
        self.loadConfig(config)
        return True

    def writeConfig(self, cfgname=None):
        if cfgname is None:
            cfgname = self.configName() or ""
        path = os.path.join(self.configPath(cfgname=cfgname, makePath=True), "ptxprint.cfg")
        config = self.createConfig()
        #print("Writing config: {}".format(path))
        with open(path, "w", encoding="utf-8") as outf:
            config.write(outf)

    def _configset(self, config, key, value):
        if "/" in key:
            (sect, k) = key.split("/", maxsplit=1)
        else:
            (sect, k) = (key, "")
        if not config.has_section(sect):
            config.add_section(sect)
        if isinstance(value, bool):
            value = "true" if value else "false"
        config.set(sect, k, value)

    def createConfig(self):
        def sortkeys(x):
            k, v = x
            if k in self._activekeys:
                return (0, k, v)
            else:
                return (1, k, v)
        config = configparser.ConfigParser()
        for k, v in sorted(ModelMap.items(), key=sortkeys):
            if v[0] is None or k.endswith("_"):
                continue
            if k in self._attributes:
                v = self._attributes[k]
                val = getattr(self, v[0])
                if val is None:
                    continue
                if v[1]:
                    val = "\n".join(x.withvars(self) for x in val)
                else:
                    val = val.withvars(self)
            elif v[0].startswith("bl_"):
                val = self.get(v[0])
                self._configset(config, k+"/name", val[0] or "")
                self._configset(config, k+"/style", val[1] or "")
                continue
            else:
                if v[0] is None:
                    continue
                val = self.get(v[0], asstr=True)
            if k in self._settingmappings:
                if val == "" or val == self.ptsettings.dict.get(self._settingmappings[k], ""):
                    continue
            self._configset(config, k, str(val) if val is not None else "")
        return config

    def _config_get(self, config, section, option, conv=None, fallback=_UNSET, **kw):
        try:
            v = config.get(section, option, **kw)
        except (NoSectionError, NoOptionError):
            if fallback is _UNSET:
                raise
            return fallback
        if conv is None:
            return v
        if v == "" and fallback is not _UNSET:
            return fallback
        return conv(v)

    def versionFwdConfig(self, config):
        version = self._config_get(config, "config", "version", conv=float, fallback=0.0)
        # print("version=",version)
        if float(version) < 0.9:
            try:
                self._configset(config, "document/ifshowchapternums", not config.getboolean("document", "ifomitchapternum"))
                self._configset(config, "document/ifshowversenums", not config.getboolean("document", "ifomitallverses"))
                self._configset(config, "document/bookintro", not config.getboolean("document", "supressbookintro"))
                self._configset(config, "document/introoutline", not config.getboolean("document", "supressintrooutline"))
                self._configset(config, "document/firstparaindent", not config.getboolean("document", "supressindent"))
                self._configset(config, "document/sectionheads", not config.getboolean("document", "supresssectheads"))
                self._configset(config, "document/parallelrefs", not config.getboolean("document", "supressparallels"))
            except:
                pass
            config.set("config", "version", "0.9")

    def loadConfig(self, config):
        def setv(k, v): self.set(k, v, skipmissing=True)
        for sect in config.sections():
            for opt in config.options(sect):
                key = "{}/{}".format(sect, opt)
                val = config.get(sect, opt)
                if key in ModelMap:
                    # print("Key:", key)
                    v = ModelMap[key]
                    if val == "None":
                        val = None
                    if key in self._attributes:
                        w = self._attributes[key]
                        if w[1]:
                            val = val.split("\n") if val is not None else []
                            val = [Path(x, self) for x in val if x is not None]
                            if w[2] is not None:
                                setv(w[2], ",".join(pdfre.sub(r"\1", x.as_posix()) for x in val))
                        else:
                            val = Path(val, self) if val is not None else None
                            if w[2] is not None and val is not None:
                                setv(w[2], pdfre.sub(r"\1", val.as_posix()))
                        setattr(self, w[0], val)
                    else:
                        try: # Safeguarding from changed/missing keys in .cfg  or v[0].startswith("f_") 
                            if v[0].startswith("s_"):
                                # print(key,v[0])
                                val = float(val) if val is not None and val != '' else 0
                            elif v[0].startswith("c_"):
                                # print("v[0]:", v[0])
                                val = config.getboolean(sect, opt) if val else False
                            if val is not None:
                                setv(v[0], val)
                        except AttributeError:
                            pass # ignore missing keys 
                elif sect in ModelMap:
                    v = ModelMap[sect]
                    if v[0].startswith("bl_") and opt == "name":
                        vname = re.sub(r"\s*,?\s+\d+\s*$", "", val) # strip legacy style and size
                        vstyle = config.get(sect, "style", fallback="")
                        # print("loadConfig: {}->{} = {},{}".format(sect, ModelMap[sect][0], vname, vstyle))
                        setv(ModelMap[sect][0], (vname, vstyle))
                if key in self._activekeys:
                    getattr(self, self._activekeys[key])()
        for k, v in self._settingmappings.items():
            (sect, name) = k.split("/")
            try:
                val = config.get(sect, name)
            except configparser.NoOptionError:
                setv(ModelMap[k][0], self.ptsettings.dict.get(v, ""))

    def generatePicLists(self, booklist, generateMissingLists=False):
        # Format of lines in pic-list file: BBB C.V desc|file|size|loc|copyright|caption|ref
        # MRK 1.16 fishermen...catching fish with a net|hk00207b.png|span|b||Jesus calling the disciples to follow him.|1:16
        xl = []
        randomizePosn = self.get("c_randomPicPosn")
        diglot   = self.get("c_diglotAutoAligned")
        digmode  = self.get("fcb_diglotPicListSources")[:3] if diglot else "Pri"
        prjid    = self.get("fcb_project")
        secprjid = self.get("fcb_diglotSecProject")
        if diglot and secprjid is None and digmode != "Pri":
            self.doError("No Secondary Project Set", secondary="In order to use the blended PicList for Diglots, the \n"+
                                                                "Secondary project must be set on the Diglot+Border tab.")
            return
        existingList = []
        existingFilelist = []
        for bk in booklist:
            outfname = self.getDraftFilename(bk)
            if os.path.exists(outfname) and os.path.getsize(outfname) != 0:
                existingFilelist.append(re.split(r"\\|/",outfname)[-1])
                existingList.append(bk)
        if len(existingFilelist) and not generateMissingLists:
            q1 = "One or more PicList file(s) already exist!"
            q2 = "\n".join(existingFilelist)+"\n\nDo you want to OVERWRITE the above-listed file(s)?"
            if self.msgQuestion(q1, q2):
                existingList =[]
        for bk in list(set(booklist) - set(existingList)):
            leftpicinfo = {}
            rightpicinfo = {}
            if not (diglot and digmode == "Sec"):
                leftpicinfo = self.getFigures(bk, sfmonly=True)
            if diglot and digmode != "Pri":
                digprinter = ViewModel(self.settings_dir, self.working_dir)
                digprinter.setPrjid(secprjid)
                rightpicinfo = digprinter.getFigures(bk, sfmonly=True)

            if len(leftpicinfo) + len(rightpicinfo) == 0:
                continue
            if diglot:
                allpicinfo = {(k, "L"):v for k, v in leftpicinfo.items()}
                allpicinfo.update({(k, "R"):v for k, v in rightpicinfo.items()})
            else:
                allpicinfo = {(k, ""):v for k, v in leftpicinfo.items()}

            fname = self.getBookFilename(bk, prjid)
            piclist = []
            piclist.append("% PicList Generated by PTXprint\n") # {}\n".format(self.dict['document/date'])) - need this from texmodel
            if diglot:
                digsrc = prjid if digmode != "Sec" else secprjid
                digsrc += "=L + R="+secprjid if digmode == "Bot" else "" 
                piclist.append("% Source for DIGLOT Illustrations: {}\n".format(digsrc))
            piclist.append("% Location   |Image Name|Img.Size|Position on Page||Illustration|Ref.\n")
            piclist.append("% book ch.vs |filename.ext|span/col|t/b/tl/tr/bl/br||Caption Text|ch:vs\n")
            piclist.append("%   (See end of list for more help for troubleshooting)\n\n")
                        
            for k in sorted(allpicinfo.keys()):
                p = allpicinfo[k]
                if   k[1] == "L" and digmode == "Bot":
                    _picposn = {"col":  ("tl", "bl"),             "span": ("t")}
                elif k[1] == "R" and digmode == "Bot":
                    _picposn = {"col":  ("tr", "br"),             "span": ("b")}
                else:
                    _picposn = {"col":  ("tl", "tr", "bl", "br"), "span": ("t", "b")}
                    
                if randomizePosn:
                    pageposn = random.choice(_picposn.get(p['size'], 'col')) # Randomize location of illustrations on the page (tl,tr,bl,br)
                else:
                    if p['loc'] in ["t", "b", "tl", "tr", "bl", "br"]:
                        pageposn = p['loc']
                    else:
                        pageposn = (_picposn.get(p['size'], 'col'))[0]       # use the t or tl (first in list)

                doti = p['src'].rfind(".")
                extn = p['src'][doti:]
                picfname = re.sub('[()&+,. ]', '_', p['src'])[:doti]+extn
                
                piclist.append("{}{} {} {}|{}|{}|{}|{}|{}|{}\n".format(bk, k[1], p['anchor'], p.get('desc', ''), picfname, \
                                                    p['size'], pageposn, p.get('copy', ''), p['alt'], p.get('ref', '')))
                # MRK 1.16 fishermen...catching fish with a net.|hk00207b.png|span|b||Jesus calling the disciples to follow him.|1:16

            piclist.append("\n% If illustrations are not appearing in the output PDF, check:\n")
            piclist.append("%   a) The anchor location reference on the far left is very particular, so check\n")
            piclist.append("%      (i) only use '.' as the ch.vs separator\n")
            piclist.append("%      (ii) ensure there is a space after the verse and before the first |\n")
            piclist.append("%      (iii) anchor refs must match the text itself\n")
            piclist.append("%      (iv) anchor refs must be in logical ch.vs order \n")
            piclist.append("%      (iv) the same anchor reference cannot be used more than once (except in a diglot)\n")
            piclist.append("%   b) Does the illustration exist in 'figures' or 'local/Figures' or another specified folder?\n")
            piclist.append("%   c) Position on Page for a 'span' image should only be 't'=top or 'b'=bottom\n")
            piclist.append("% Other Notes:\n")
            piclist.append("%   d) To (temporarily) remove an illustration prefix the line with % followed by a space\n")
            piclist.append("%   e) To scale an image use this notation: span*.7  or  col*1.3)\n")
            plpath = os.path.join(self.configPath(self.configName()), "PicLists")
            os.makedirs(plpath, exist_ok=True)
            outfname = os.path.join(plpath, self.getDraftFilename(bk))
            with open(outfname, "w", encoding="utf-8") as outf:
                outf.write("".join(piclist))

    def getDraftFilename(self, bk, ext=".piclist"):
        fname = self.getBookFilename(bk, self.prjid)
        doti = fname.rfind(".")
        if doti > 0:
            return fname[:doti] + "-draft" + fname[doti:] + ext
        else:
            return fname + "-draft" + ext

    def getFigures(self, bk, sfmonly=False):
        posparms = ("desc", "src", "size", "loc", "copy", "alt", "ref", "xetex")
        res = {}
        fname = self.getBookFilename(bk, self.prjid)
        usepiclist = not sfmonly and self.get("c_usePicList") and bk not in TexModel._peripheralBooks
        if usepiclist:
            plfname = self.getDraftFilename(bk)
            piclstfname = os.path.join(self.configPath(cfgname=self.configName()), "PicLists", plfname)
            if not os.path.exists(piclstfname):
                usepiclist = False
            else:
                fname = piclstfname
        if not usepiclist:
            fname = os.path.join(self.settings_dir, self.prjid, fname)
        if usepiclist:
            with universalopen(fname) as inf:
                for l in inf.readlines():
                    m = l.strip().split("|")
                    if len(m) < 7 or m[0].startswith("%"):
                        continue
                    r = m[0].split()[1]
                    res[r] = {}
                    for i, f in enumerate(m[1:]):
                        res[r][posparms[i+1]] = f
        else:
            with universalopen(fname) as inf:
                dat = inf.read()
                blocks = [""] + re.split(r"\\c\s+(\d+)", dat)
                for c, t in zip(blocks[0::2], blocks[1::2]):
                    m = re.findall(r"(?ms)(?<=\\v )(\d+?[abc]?([,-]\d+?[abc]?)?) (.(?!\\v ))*\\fig (.*?)\|(.+?\.....?)\|(....?)\|([^\\]+?)?\|([^\\]+?)?\|([^\\]+?)?\|((?:[^\d\\]+? ?)?(\d+[\:\.]\d+?[abc]?(?:[\-,\u2013\u2014]\d+[abc]?)?))\\fig\*", t)
                    if len(m):
                        for f in m:     # usfm 2
                            r = self._sortkey(c, f[0])
                            res[r] = {}
                            res[r]['anchor'] = "{}.{}".format(c, f[0])
                            for i, v in enumerate(f[3:]):
                                res[r][posparms[i]] = v
                    else:
                        m = re.findall(r'(?ms)(?<=\\v )(\d+?[abc]?([,-]\d+?[abc]?)?) (.(?!\\v ))*\\fig ([^\\]*?)\|([^\\]+)\\fig\*', t)
                        for f in m:     # usfm 3
                            caption = f[3]
                            r = self._sortkey(c, f[0])
                            res[r] = {}
                            res[r]['anchor'] = "{}.{}".format(c, f[0])
                            labelParams = re.findall(r'([a-z]+?="[^\\]+?")', f[4])
                            for l in labelParams:
                                k,v = l.split("=")
                                res[r][k.strip()] = v.strip('"')
        return res

    def _sortkey(self, c, v):
        return "{:0>3}{:0>3}".format(c, re.sub(r"(\d+)[\-,abc\d]*", r"\1", v))
        

    def getFigureSources(self, figlist, filt=newBase):
        res = {}
        if filt is not None:
            newfigs = {filt(f): f for f in figlist}
        else:
            newfigs = {f: f for f in figlist}
        if self.get("c_useCustomFolder"):
            srchlist = [self.printer.customFigFolder]
        else:
            srchlist = []
        if not self.get("c_exclusiveFiguresFolder"):
            if sys.platform == "win32":
                srchlist += [os.path.join(self.settings_dir, self.prjid, "figures")]
                srchlist += [os.path.join(self.settings_dir, self.prjid, "local", "figures")]
            elif sys.platform == "linux":
                chkpaths = []
                for d in ("local", "figures"):
                    chkpaths += [os.path.join(self.settings_dir, self.prjid, x) for x in (d, d.title())]
                for p in chkpaths:
                    if os.path.exists(p):
                        srchlist += [p]
        extensions = []
        extdflt = {x:i for i, x in enumerate(["jpg", "jpeg", "png", "tif", "tiff", "bmp", "pdf"])}
        imgord = self.get("t_imageTypeOrder").lower()
        extuser = re.sub("[ ,;/><]"," ",imgord).split()
        extensions = {x:i for i, x in enumerate(extuser) if x in extdflt}
        if not len(extensions):   # If the user hasn't defined any extensions 
            extensions = extdflt  # then we can assign defaults

        for srchdir in srchlist:
            if srchdir is None or not os.path.exists(srchdir):
                continue
            if self.get("c_exclusiveFiguresFolder"):
                search = [srchdir, [], os.listdir(srchdir)]
            else:
                search = os.walk(srchdir)
            for subdir, dirs, files in search:
                for f in files:
                    doti = f.rfind(".")
                    origExt = f[doti:].lower()
                    if origExt[1:] not in extensions:
                        continue
                    filepath = os.path.join(subdir, f)
                    nB = filt(f) if filt is not None else f
                    if nB not in newfigs:
                        continue
                    k = newfigs[nB]
                    if k in res:
                        old = extensions.get(os.path.splitext(res[k]).lower(), 10000)
                        new = extensions.get(os.path.splitext(filepath).lower(), 10000)
                        if old > new:
                            res[k] = filepath
                        elif old == new and (self.printer.get("c_useLowResPics") \
                                            != bool(os.path.getsize(res[k]) < os.path.getsize(filepath))):
                            res[k] = filepath
                    else:
                        res[k] = filepath
        return res

    def generateAdjList(self):
        existingFilelist = []
        booklist = self.getBooks()
        diglot  = self.get("c_diglotAutoAligned")
        digmode = self.get("fcb_diglotPicListSources") if diglot else "Primary"
        prjid = self.get("fcb_project")
        secprjid = ""
        if diglot:
            secprjid = self.get("fcb_diglotSecProject")
            if secprjid is not None:
                secprjdir = os.path.join(self.settings_dir, secprjid)
            else:
                self.doError("No Secondary Project Set", secondary="In order to generate an AdjList for Diglots, the \n"+
                                                                    "Secondary project must be set on the Diglot+Border tab.")
                return
        prjdir = os.path.join(self.settings_dir, self.prjid)
        for bk in booklist:
            fname = self.getBookFilename(bk, prjid)
            outfname = os.path.join(self.configPath(self.configName()), "AdjLists", fname)
            doti = outfname.rfind(".")
            if doti > 0:
                outfname = outfname[:doti] + "-draft" + outfname[doti:] + ".adj"
            if os.path.exists(outfname):
                existingFilelist.append(re.split(r"\\|/",outfname)[-1])
        if len(existingFilelist):
            q1 = "One or more Paragraph Adjust file(s) already exist!"
            q2 = "\n".join(existingFilelist)+"\n\nDo you want to OVERWRITE the above-listed file(s)?"
            if not self.msgQuestion(q1, q2):
                return
        for bk in booklist:
            tmplist = []
            fname = self.getBookFilename(bk, prjid)
            outfname = os.path.join(self.configPath(self.configName()), "AdjLists", fname)
            doti = outfname.rfind(".")
            if doti > 0:
                outfname = outfname[:doti] + "-draft" + outfname[doti:] + ".adj"
            adjlist = []
            flist = [os.path.join(prjdir, fname)]
            if diglot: 
                secfname = self.getBookFilename(bk, secprjid)
                flist += [os.path.join(secprjdir, secfname)]
            if len(flist) == 2:
                sfx = 'L'
            else:
                sfx = ""
            for infname in flist:
                if len(flist) == 2 and infname == flist[1]:
                    sfx = 'R'
                with open(infname, "r", encoding="utf-8") as inf:
                    dat = inf.read()
                    # It would be good to make this more inclusive (\p \m \q1 \q2 etc.) 
                    # and also include \s Section Heads as comments to help show whichs paragraphs are within a single section
                    m = re.findall(r"\\p ?\r?\n\\v (\S+)",dat)
                    if m is not None:
                        prv = 0
                        ch = 1
                        for v in m:
                            iv = int(re.sub(r"^(\d+).*$", r"\1", v), 10)
                            if iv < prv:
                                ch = ch + 1
                            srtchvs = "{:0>3}{:0>3}{}".format(ch,v,sfx)
                            tmplist.append(srtchvs+"\u0009"+bk+sfx+" "+str(ch)+"."+v+" +0\n")
                            prv = iv
            if len(tmplist):
                for al in sorted(tmplist):
                    adjlist.append(al.split("\u0009")[1]+"\n")
            adjpath = os.path.join(self.configPath(self.configName()), "AdjLists")
            os.makedirs(adjpath, exist_ok=True)
            with open(outfname, "w", encoding="utf-8") as outf:
                outf.write("".join(adjlist))

    def generateHyphenationFile(self):
        listlimit = 32749
        prjid = self.get("fcb_project") # self.dict['project/id']
        prjdir = os.path.join(self.settings_dir, self.prjid)
        infname = os.path.join(self.ptsettings.basedir, prjid, 'hyphenatedWords.txt')
        outfname = os.path.join(self.ptsettings.basedir, prjid, "shared", "ptxprint", 'hyphen-{}.tex'.format(prjid))
        hyphenatedWords = []
        if not os.path.exists(infname):
            m1 = "Failed to Generate Hyphenation List"
            m2 = "{} Paratext Project's Hyphenation file not found:\n{}".format(prjid, infname)
        else:
            m2b = ""
            m2c = ""
            z = 0
            with universalopen(infname) as inf:
                for l in inf.readlines()[8:]: # Skip over the Paratext header lines
                    l = l.strip().replace(u"\uFEFF", "")
                    l = re.sub(r"\*", "", l)
                    l = re.sub(r"=", "-", l)
                    # Paratext doesn't seem to allow segments of 1 character to be hyphenated  (for example: a-shame-d) 
                    # (so there's nothing to filter them out, because they don't seem to exist!)
                    if "-" in l:
                        if "\u200C" in l or "\u200D" in l or "'" in l: # Temporary workaround until we can figure out how
                            z += 1                                     # to allow ZWNJ and ZWJ to be included as letters.
                        elif re.search('\d', l):
                            pass
                        else:
                            if l[0] != "-":
                                hyphenatedWords.append(l)
            c = len(hyphenatedWords)
            if c >= listlimit:
                m2b = "\n\nThat is too many for XeTeX! List truncated to longest {} words.".format(listlimit)
                hyphenatedWords.sort(key=len,reverse=True)
                shortlist = hyphenatedWords[:listlimit]
                hyphenatedWords = shortlist
            hyphenatedWords.sort(key = lambda s: s.casefold())
            outlist = '\catcode"200C=11\n\catcode"200D=11\n\hyphenation{' + "\n".join(hyphenatedWords) + "}"
            with open(outfname, "w", encoding="utf-8") as outf:
                outf.write(outlist)
            if len(hyphenatedWords) > 1:
                m1 = "Hyphenation List Generated"
                m2a = "{} hyphenated words were gathered\nfrom Paratext's Hyphenation Word List.".format(c)
                if z > 0:
                    m2c = "\n\nNote for Indic languages that {} words containing ZWJ".format(z) + \
                            "\nand ZWNJ characters have been left off the hyphenation list." 
                m2 = m2a + m2b + m2c
            else:
                m1 = "Hyphenation List was NOT Generated"
                m2 = "No valid words were found in Paratext's Hyphenation List"
        self.doError(m1, m2)

    def checkSFMforFancyIntroMarkers(self):
        unfitBooks = []
        prjid = self.get("fcb_project")
        prjdir = os.path.join(self.settings_dir, prjid)
        bks = self.getBooks()
        for bk in bks:
            if bk not in TexModel._peripheralBooks:
                fname = self.getBookFilename(bk, prjid)
                fpath = os.path.join(self.settings_dir, prjid, fname)
                if os.path.exists(fpath):
                    with open(fpath, "r", encoding="utf-8") as inf:
                        sfmtxt = inf.read()
                    # Put strict conditions on the format (including only valid \ior using 0-9, not \d digits from any script)
                    # This was probably too restrictive, but is a great RegEx: \\ior ([0-9]+(:[0-9]+)?[-\u2013][0-9]+(:[0-9]+)?) ?\\ior\*
                    if regex.search(r"\\iot .+\r?\n(\\io\d .+\\ior [0-9\-:.,\u2013\u2014 ]+\\ior\* ?\r?\n)+\\c 1", sfmtxt, flags=regex.MULTILINE) \
                       and len(regex.findall(r"\\iot",sfmtxt)) == 1: # Must have exactly 1 \iot per book 
                        pass
                    else:
                        unfitBooks.append(bk)
        return unfitBooks

    def onFindMissingCharsClicked(self, btn_findMissingChars):
        count = collections.Counter()
        prjid = self.get("fcb_project")
        prjdir = os.path.join(self.settings_dir, prjid)
        bks = self.getBooks()
        for bk in bks:
            fname = self.getBookFilename(bk, prjid)
            fpath = os.path.join(prjdir, fname)
            if os.path.exists(fpath):
                with open(fpath, "r", encoding="utf-8") as inf:
                    # Strip out all markers themselves, and English content fields
                    sfmtxt = inf.read()
                    sfmtxt = regex.sub(r'\\id .+?\r?\n', '', sfmtxt)
                    sfmtxt = regex.sub(r'\\rem .+?\r?\n', '', sfmtxt)
                    # throw out illustration markup, BUT keep the caption text (USFM2 + USFM3)
                    sfmtxt = regex.sub(r'\\fig (.*\|){5}([^\\]+)?\|[^\\]+\\fig\*', '\2', sfmtxt) 
                    sfmtxt = regex.sub(r'\\fig ([^\\]+)?\|.*src=[^\\]+\\fig\*', '\1', sfmtxt) 
                    sfmtxt = regex.sub(r'\\[a-z]+\d?\*? ?', '', sfmtxt) # remove all \sfm codes
                    sfmtxt = regex.sub(r'[0-9]', '', sfmtxt) # remove all digits
                    bkcntr = collections.Counter(sfmtxt)
                    count += bkcntr
        # slist = sorted(count.items(), key=lambda pair: pair[0])
        f = TTFont(*self.get("bl_fontR"))
        allchars = ''.join([i[0] for i in count.items()])
        if self.get("fcb_glossaryMarkupStyle") == "with ⸤floor⸥ brackets":
            allchars += "\u2e24\u2e25"
        if self.get("fcb_glossaryMarkupStyle") == "with ⌊floor⌋ characters":
            allchars += "\u230a\u230b"
        if self.get("fcb_glossaryMarkupStyle") == "with ⌞corner⌟ characters":
            allchars += "\u231e\u231f"
        missing = f.testcmap(allchars)
        self.set("t_missingChars", ' '.join(missing))
        return missing

    def onFontExtraRclicked(self, bl_fontExtraR):
        self.getFontNameFace("bl_fontExtraR")
        finfor = self.get('bl_fontR')
        finfoe = self.get('bl_fontExtraR')
        if finfor[0] == finfoe[0]:
            self.doError("The Fallback Font needs to be something other than the Regular Font.",
                    "Please select a different Font.")
        else:
            f = TTFont(*finfoe)
            msngchars = self.get("t_missingChars") # .split(" ")
            msngchars = spclChars = re.sub(r"\\[uU]([0-9a-fA-F]{4,6})", lambda m:chr(int(m.group(1), 16)), msngchars)
            stillmissing = f.testcmap(msngchars)
            if len(stillmissing):
                self.doError("The Fallback Font just selected does NOT support all the missing characters listed.",
                        "Please select a different Font.")

    def getExtOrder(self):
        # If the preferred image type(s) has(have) been specified, parse that string
        imgord = self.get("t_imageTypeOrder").lower()
        extOrder = re.sub("[ ,;/><]"," ",imgord).split()
        if not len(extOrder): # If the user hasn't defined a specific order then we can assign this
            if self.get("c_useLowResPics"): # based on whether they prefer small/compressed image formats
                extOrder = ["jpg", "jpeg", "png", "tif", "tiff", "bmp", "pdf"] 
            else:                              # or prefer larger high quality uncompressed image formats
                extOrder = ["pdf", "bmp", "tiff", "tif", "png", "jpeg", "jpg"] # reverse order
        return extOrder

    def incrementProgress(self, val=None):
        pass

    def _getArchiveFiles(self, books, prjid=None, cfgid=None):
        sfiles = {'c_useCustomSty': "custom.sty",
                  'c_useModsSty': "PrintDraft/PrintDraft-mods.sty",
                  'c_usePrintDraftChanges': "PrintDraftChanges.txt"}
        res = {}
        cfgchanges = {}
        pictures = set()
        if prjid is None:
            prjid = self.prjid
        if cfgid is None:
            cfgid = self.configName()
        cfpath = "shared/ptxprint/"
        if cfgid is not None:
            cfpath += cfgid+"/"
        basecfpath = self.configPath(cfgid, prjid)

        for bk in books:
            fname = self.getBookFilename(bk, prjid)
            fpath = os.path.join(self.settings_dir, prjid)
            res[os.path.join(fpath, fname)] = fname
            picinfos = self.getFigures(bk)
            for p in picinfos.values():
                pictures.add(p['src'])

        picsrcs = self.getFigureSources(pictures)
        for p, f in picsrcs.items():
            res[f] = "figures/"+os.path.basename(f)
        adjpath = os.path.join(basecfpath, "AdjLists")
        adjbks = set(self.getDraftFilename(bk, ext=".adj") for x in books)
        if os.path.exists(adjpath):
            for adj in os.listdir(adjpath):
                if adj.endswith(".adj") and adj in adjbks:
                    res[os.path.join(adjpath, adj)] = cfpath+"AdjLists/"+adj

        piclstpath = os.path.join(basecfpath, "PicLists")
        picbks = set(self.getDraftFilename(bk) for x in books)
        if os.path.exists(piclstpath):
            for pic in os.listdir(piclstpath):
                if pic.endswith(".piclist") and pic in picbks:
                    res[os.path.join(piclstpath, pic)] = cfpath+"PicLists/"+pic

        for t,a in sfiles.items():
            if isinstance(t, str) and not self.get(t):
                continue
            p = os.path.join(self.settings_dir, prjid, a[0])
            if os.path.exists(p):
                res[p] = a

        if self.get("c_useModsTex"):
            loaded = False
            if cfgid is not None:
                p = os.path.join(self.settings_dir, prjid, 'shared', 'ptxprint', cfgid, 'ptxprint-mods.tex')
                if os.path.exists(p):
                    res[p] = "shared/ptxprint/" + cfgid + "/ptxprint-mods.tex"
                    loaded = True
            if not loaded:
                p = os.path.join(self.settings_dir, prjid, 'shared', 'ptxprint', 'ptxprint-mods.tex')
                if os.path.exists(p):
                    res[p] = "shared/ptxprint/ptxprint-mods.tex"

        script = self.get("btn_selectScript")
        if script is not None and len(script):
            res[script] = os.path.basename(script)
            cfgchanges["btn_selectScript"] = os.path.join(self.settings_dir, prjid, os.path.basename(script))

        hyphenfpath = os.path.join(self.settings_dir, prjid, "shared", "ptxprint")
        hyphentpath = "shared/ptxprint/"
        hyphenfile = "hyphen-{}.tex".format(self.prjid)
        if os.path.exists(os.path.join(hyphenfpath, hyphenfile)):
            res[os.path.join(hyphenfpath, hyphenfile)] = hyphentpath + hyphenfile

        if self.ptsettings is None or self.prjid != prjid:
            self.ptsettings = ParatextSettings(self.settings_dir, prjid)
        ptres = self.ptsettings.getArchiveFiles()
        res.update(ptres)
        return (res, cfgchanges)

    def createArchive(self, filename=None):
        if filename is None:
            filename = os.path.join(self.configPath(self.configName()), "ptxprintArchive.zip")
        if not filename.lower().endswith(".zip"):
            filename += ".zip"
        zf = ZipFile(filename, mode="w", compression=ZIP_DEFLATED, compresslevel=9)
        zf.write(os.path.join(self.settings_dir, "usfm.sty"), "usfm.sty")
        self._archiveAdd(zf, self.getBooks())
        if self.get("c_diglot"):
            prjid = self.get("fcb_diglotSecProject")
            cfgid = self.get("ecb_diglotSecConfig")
            digprinter = ViewModel(self.settings_dir, self.working_dir)
            digprinter.setPrjid(prjid)
            if cfgid is not None and cfgid != "":
                digprinter.setConfigId(cfgid)
            digprinter._archiveAdd(zf, self.getBooks())
        zf.close()

    def _archiveAdd(self, zf, books):
        prjid = self.prjid
        cfgid = self.configName()
        entries, cfgchanges = self._getArchiveFiles(books, prjid=prjid, cfgid=cfgid)
        for k, v in entries.items():
            zf.write(k, arcname=prjid + "/" + v)
        tmpcfg = {}
        for k,v in cfgchanges.items():
            tmpcfg[k] = self.get(k)
            self.set(k, v)
        config = self.createConfig()
        configstr = StringIO()
        config.write(configstr)
        zf.writestr(prjid + "/shared/ptxprint/" + (cfgid + "/" if cfgid else "") + "ptxprint.cfg",
                    configstr.getvalue())
        configstr.close()
        for k, v in tmpcfg.items():
            self.set(k, v)

