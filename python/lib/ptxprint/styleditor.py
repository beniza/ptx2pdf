
import re
from ptxprint.usfmutils import Sheets
from ptxprint.font import FontRef
from copy import deepcopy

mkrexceptions = {k.lower().title(): k for k in ('BaseLine', 'TextType', 'TextProperties', 'FontName',
                'FontSize', 'FirstLineIndent', 'LeftMargin', 'RightMargin',
                'SpaceBefore', 'SpaceAfter', 'CallerStyle', 'CallerRaise',
                'NoteCallerStyle', 'NoteCallerRaise', 'NoteBlendInto', 'LineSpacing',
                'StyleType', 'ColorName', 'XMLTag', 'TEStyleName', 'ztexFontFeatures', 'ztexFontGrSpace')}
binarymkrs = {"bold", "italic", "smallcaps"}

absolutes = {"baseline", "raise", "callerraise", "notecallerraise"}
aliases = {"q", "s", "mt", "to", "imt", "imte", "io", "iq", "is", "ili", "pi",
           "qm", "sd", "ms", "mt", "mte", "li", "lim", "liv", }
_defFields = {"Marker", "EndMarker", "Name", "Description", "OccursUnder", "TextProperties", "TextType", "StyleType"}

class StyleEditor:

    def __init__(self, model):
        self.model = model
        self.sheet = None
        self.basesheet = None
        self.marker = None
        self.registers = {}

    def allStyles(self):
        if self.sheet is None:
            return {}
        res = set(self.basesheet.keys())
        res.update(self.sheet.keys())
        return res

    def asStyle(self, m):
        res = self.basesheet.get(m, {}).copy()
        res.update(self.sheet.get(m, {}))
        return res

    def getval(self, mrk, key, default=None):
        if self.sheet is None:
            raise KeyError(f"stylesheet missing: {mrk} + {key}")
        res = self.sheet.get(mrk, {}).get(key, None)
        if res is None or (mrk in _defFields and not len(res)):
            res = self.basesheet.get(mrk, {}).get(key, default)
        return res

    def setval(self, mrk, key, val, ifunchanged=False):
        if self.sheet is None:
            raise KeyError(f"{mrk} + {key}")
        if ifunchanged and self.basesheet.get(mrk, {}).get(key, None) != \
                self.sheet.get(mrk, {}).get(key, None):
            return
        if key in self.sheet.get(mrk, {}) and (val is None or val == self.basesheet.get(mrk, {}).get(key, None)):
            del self.sheet[mrk][key]
            return
        elif self.basesheet.get(mrk, {}).get(key, None) != val:
            self.sheet.setdefault(mrk, {})[key] = val or ""
        elif key in self.basesheet.get(mrk, {}) and val is None:
            del self.basesheet[mrk][key]

    def get_font(self, mrk, style=""):
        f = self.getval(mrk, " font")
        if f is not None:
            return f
        f = self.model.getFont(style if len(style) else "regular")
        return f

    def registerFn(self, mark, key, fn):
        self.registers.setdefault(mark, {})[key.lower()] = fn

    def load(self, sheetfiles):
        if len(sheetfiles) == 0:
            return
        foundp = False
        self.basesheet = Sheets(sheetfiles[:-1])
        self._createFonts(self.basesheet)
        self.sheet = Sheets(sheetfiles[-1:], base = "")
        self._createFonts(self.sheet)

    def _createFonts(self, sheet):
        for k in self.allStyles():
            if 'FontName' in self.sheet.get(k, {}):
                v = self.sheet[k]
            elif 'FontName' in self.basesheet.get(k, {}):
                v = self.basesheet[k]
            else:
                continue
            f = FontRef.fromTeXStyle(v)
            if f is not None:
                self.setval(k, " font", f)

    def _convertabs(self, key, valstr):
        def asfloat(v, d):
            try:
                return float(v)
            except (ValueError, TypeError):
                return d
        baseline = float(self.model.get("s_linespacing", 1.))
        if key.lower() == "fontsize":
            res = asfloat(valstr, 1.) * 12.
        elif key.lower() == "baseline":
            res = asfloat(valstr, 12.) * baseline
        elif key.lower() == "fontscale": 
            res = asfloat(valstr, 12.) / 12.
        elif key.lower() == "linespacing":
            res = asfloat(valstr, baseline) / baseline
        return res

    def _setData(self, key, val):
        if self.basesheet.get(self.marker, {}).get(key, None) != val:
            self.sheet[self.marker][key] = val
            fn = self.registers.get(self.marker, {}).get(key.lower(), None)
            if fn is not None:
                fn(key, val)
        elif key in self.sheet.get(self.marker, {}):
            del self.sheet[self.marker][key]

    def _eq_val(self, a, b, key=""):
        if key.lower() in absolutes:
            fa = self.asFloatPts(str(a))
            fb = self.asFloatPts(str(b))
        else:
            try:
                fa = float(a)
                fb = float(b)
                return abs(fa - fb) < 0.005
            except (ValueError, TypeError):
                pass
            if key.lower() not in binarymkrs:
                a = a or ""
                b = b or ""
            return a == b

    def _str_val(self, v, key=""):
        if isinstance(v, (set, list)):
            if key.lower() == "textproperties":
                res = " ".join(x.lower().title() if x else "" for x in sorted(v))
            else:
                res = " ".join(self._str_val(x, key) for x in sorted(v))
        elif key.lower() in absolutes:
            fv = self.asFloatPts(str(v))
            res = "{:.3f} pt".format(fv)
        elif isinstance(v, float):
            res = re.sub(r"(:\.0)?0$", "", str(int(v * 100) / 100.))
        else:
            res = str(v)
        if key.lower() == "baseline":
            res = re.sub(r"^\s*(.*\d+)\s*$", r"\1pt", res)
        return res

    def output_diffile(self, outfh, regular=None, inArchive=False, root=None):
        def normmkr(s):
            x = s.lower().title()
            return mkrexceptions.get(x, x)
        for m in sorted(self.allStyles()):
            markerout = False
            if m in aliases:
                sm = self.basesheet.get(m+"1", {}).copy()
                sm.update(self.sheet.get(m+"1", {}))
            elif inArchive:
                sm = self.sheet.get(m, {}).copy()
            else:
                sm = self.sheet.get(m, {})
            om = self.basesheet.get(m, {})
            if 'zDerived' in om or 'zDerived' in sm:
                continue
            if " font" in sm:
                sm[" font"].updateTeXStyle(sm, regular=regular, inArchive=inArchive, root=root)
            for k,v in sm.items():
                if k.startswith(" "):
                    continue
                other = om.get(k, None)
                if not self._eq_val(other, v, key=k):
                    if not markerout:
                        outfh.write("\n\\Marker {}\n".format(m))
                        markerout = True
                    outfh.write("\\{} {}\n".format(normmkr(k), self._str_val(v, k)))

    def asFloatPts(self, s, mrk=None):
        if mrk is None:
            mrk = self.marker
        m = re.match(r"^\s*(-?\d+(?:\.\d*))\s*(\D*?)\s*$", s)
        if m:
            try:
                v = float(m[1])
            except (TypeError, ValueError):
                v = 0.
            units = m[2]
            if units == "" or units.lower() == "pt" or mrk is None:
                return v
            elif units == "in":
                return v * 72.27
            elif units == "mm":
                return v * 72.27 / 25.4
            try:
                fsize = float(self.getval(mrk, "FontSize"))
            except TypeError:
                return v
            if fsize is None:
                return v
            try:
                bfsize = float(self.model.get("s_fontsize"))
            except TypeError:
                return v
            if units == "ex":
                return v * fsize / 12. / 2.
            elif units == "em":
                return v * fsize / 12.
            return v
        else:
            try:
                return float(s)
            except (ValueError, TypeError):
                return 0.

