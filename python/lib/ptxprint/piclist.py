
from ptxprint.gtkutils import getWidgetVal, setWidgetVal
from ptxprint.view import refKey
from gi.repository import Gtk, GdkPixbuf

_piclistfields = ["anchor", "caption", "src", "size", "scale", "pgpos", "ref", "alt", "copyright", "mirror"]
_form_structure = {
    'anchor':   't_plAnchor',
    'caption':  't_plCaption',
    'src':      't_plFilename',
    'size':     'fcb_plSize',
    'scale':    's_plScale',
    'pgpos':    'fcb_plPgPos',
    'ref':      't_plRef',
    'alt':      't_plAltText',
    'copyright':    't_plCopyright',
    'mirror':   'fcb_plMirror',
    'hpos':     'fcb_plHoriz',
    'nlines':   's_plLines',
}
_comblist = ['pgpos', 'hpos', 'nlines']

class PicList:
    def __init__(self, view, listview, builder, parent):
        self.view = view
        self.model = view.get_model()
        self.listview = listview
        self.builder = builder
        self.parent = parent
        self.selection = view.get_selection()
        self.selection.set_mode=Gtk.SelectionMode.SINGLE
        self.selection.connect("changed", self.row_select)
        for k, v in _form_structure.items():
            w = builder.get_object(v)
            w.connect("value-changed" if v[0].startswith("s_") else "changed", self.item_changed, k)
        pass

    def isEmpty(self):
        return len(self.model) == 0

    def clear(self):
        self.model.clear()

    def load(self, picinfo):
        self.view.set_model(None)
        self.listview.set_model(None)
        self.model.clear()
        if picinfo is not None:
            for k, v in sorted(picinfo.items(), key=lambda x:(refKey(x[0]), x[1])):
                row = [k] + [v[e] if e in v else (1 if e == "scale" else "") for e in _piclistfields[1:]]
                try:
                    row[4] = int(row[4]) * 100
                except (ValueError, TypeError):
                    row[4] = 100
                self.model.append(row)
        self.view.set_model(self.model)
        self.listview.set_model(self.model)

    def get(self, wid, default=None):
        wid = _form_structure.get(wid, wid)
        w = self.builder.get_object(wid)
        res = getWidgetVal(wid, w, default=default)
        if wid.startswith("s_"):
            res = int(res[:res.find(".")]) if res.find(".") >= 0 else int(res)
        return res

    def getrowinfo(self, row):
        e = {k: row[i+1] for i, k in enumerate(_piclistfields[1:])}
        e['scale'] = e['scale'] / 100. if e['scale'] != 100 else None
        return e

    def getinfo(self):
        res = {}
        for row in self.model:
            res[row[0]] = self.getrowinfo(row)
        return res

    def row_select(self, selection):
        if selection.count_selected_rows() != 1:
            return
        model, i = selection.get_selected()
        if self.model.get_path(i).get_indices()[0] >= len(self.model):
            return
        row = self.model[i]
        for j, (k, v) in enumerate(_form_structure.items()): # relies on ordered dict
            if k == 'pgpos':
                val = row[j][0]
            elif k == 'hpos':
                val = row[5]
                val = val[1] if len(val) > 1 else ""
            elif k == 'nlines':
                val = row[5]
                val = int(val[2]) if len(val) > 2 else 0
            else:
                val = row[j]
            w = self.builder.get_object(v)
            setWidgetVal(v, w, val)

    def select_row(self, i):
        if i >= len(self.model):
            i = len(self.model) - 1
        treeiter = self.model.get_iter_from_string(str(i))
        self.selection.select_iter(treeiter)

    def get_pgpos(self):
        res = "".join(self.get(k, default="") for k in _comblist[:-1])
        if res.startswith("c"):
            res += str(self.get(_comblist[-1]))
        return res

    def item_changed(self, w, key):
        if key in _comblist:
            val = self.get_pgpos()
            key = "pgpos"
        else:
            val = self.get(key)
        if self.model is not None and len(self.model):
            row = self.model[self.selection.get_selected()[1]]
            row[_piclistfields.index(key)] = val
            if key == "src":
                tempinfo = {}
                e = self.getrowinfo(row)
                tempinfo[row[0]] = e
                self.parent.getFigureSources(tempinfo)
                pic = self.builder.get_object("img_picPreview")
                if 'src path' in e:
                    picframe = self.builder.get_object("fr_picPreview")
                    rect = picframe.get_allocation()
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(e['src path'], rect.width, rect.height)
                    pic.set_from_pixbuf(pixbuf)
                else:
                    pic.clear()

    def get_row_from_items(self):
        row = [self.get(k, default="") for k in _piclistfields]
        row[_piclistfields.index('pgpos')] = self.get_pgpos()
        return row

    def add_row(self):
        if len(self.model) > 0:
            row = self.model[self.selection.get_selected()[1]][:]
            row[0] = ""
        else:
            row = self.get_row_from_items()
        self.model.append(row)
        self.select_row(len(self.model)-1)

    def del_row(self):
        model, i = selection.get_selected()
        del self.model[i]
        self.select_row(model.get_path(i).get_indices()[0])

