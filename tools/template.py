"""Write Resolve 21.1.1 grades (.drx) from scratch: correctors (optional LUT or DCTL),
Layer Mixers with a composite mode, and ResolveFX DCTL plugin nodes, wired by explicit links.

Record layout (decoded from Resolve's own exports):
  node   1.7  {1 id, 2 number in the UI, 4 x, 5 y, 7 = 1, 8 type, 9 tools, 10 properties, 12 stamp}
              type 44 = corrector, 90 = Layer Mixer
  link   1.8  {1 source id, [2 source port], 3 destination id, [4 destination port], 5 = 64, 6 = 64, 7 link id}
              a Layer Mixer's inputs are destination ports 0, 1, ...; port 0 is omitted
  input  1.9  {1 id, 2 = 80, 3 (repeated) {1 link id, 2 = 64, 3 input id, 4 destination node}}
  output 1.10 {1 id, 2 = 64, 3 {1 link id, 2 = 64, 3 output id, 4 source node}}
  Layer Mixer composite mode: node property 0xC0000043 = {2: mode}; Normal is the default and
  is not written; Add = 2 and Screen = 10 (measured).

usage (as a library): from template import Grade
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drxlib as d

V, L = 0, 2
CORRECTOR, LAYER_MIXER = 44, 90
COMPOSITE = {"normal": None, "add": 2, "screen": 10}
PROP_BASE = 0xC0000001
PROP_COMPOSITE = 0xC0000043


def msg(*fields):
    return d.serialize(list(fields))


def prop(key, value_msg):
    return msg((1, V, key), (2, L, value_msg))


def int_prop(key, v):
    return prop(key, msg((2, V, v)))


class Grade:
    def __init__(self, base_path):
        self.xml = open(base_path, encoding="utf-8", newline="").read()
        hexbody, self.span = d.get_body(self.xml, "pClipFullVer")
        self.prefix, pb = d.body_decode(hexbody)
        self.top = d.parse(pb)
        graph = [v for f, wt, v in self.top if f == 1][0]
        self.gf = d.parse(graph)
        first = [v for f, wt, v in self.gf if f == 7][0]
        self.lut_node_base = first          # a corrector that carries a LUT in tool 1
        self.stamp = [v for f, wt, v in d.parse(first) if f == 12][0]
        self.nodes, self.links, self.inputs = [], [], []
        self.output = None
        self.next_id = 1

    def _id(self):
        i = self.next_id
        self.next_id += 1
        return i

    # ---- nodes -------------------------------------------------------------
    def corrector(self, num, x, y, lut=None):
        nid = self._id()
        if lut:
            rec = self._lut_record(nid, num, x, y, lut)
        else:
            rec = msg((1, V, nid), (2, V, num), (4, V, x), (5, V, y), (7, V, 1), (8, V, CORRECTOR),
                      (9, L, msg((2, L, bytes([3, 4, 5, 6, 18])))),
                      (10, L, msg((1, L, int_prop(PROP_BASE, 2)))),
                      (12, V, self.stamp))
        self.nodes.append((nid, rec))
        return nid

    def layer_mixer(self, num, x, y, composite="normal"):
        nid = self._id()
        props = [(1, L, int_prop(PROP_BASE, 2))]
        mode = COMPOSITE[composite]
        if mode is not None:
            props.append((1, L, int_prop(PROP_COMPOSITE, mode)))
        rec = msg((1, V, nid), (2, V, num), (4, V, x), (5, V, y), (7, V, 1), (8, V, LAYER_MIXER),
                  (9, L, b""), (10, L, d.serialize(props)), (12, V, self.stamp))
        self.nodes.append((nid, rec))
        return nid

    def dctl_plugin(self, num, x, y, params):
        """params: list of (name, kind, value), kind in 'int', 'f64', 'bool', 'str'."""
        nid = self._id()
        plugin = "com.blackmagicdesign.resolvefx.dctl"
        plist = []
        for name, kind, val in params:
            if kind == "int":
                pv = msg((1, V, val))
            elif kind == "f64":
                pv = msg((2, 1, struct.pack("<d", val)))
            elif kind == "bool":
                pv = msg((3, V, 1 if val else 0))
            else:
                pv = msg((5, L, val.encode()))
            plist.append((5, L, msg((1, L, name.encode()), (2, L, pv))))
        ofx = d.serialize([(1, V, 5195353), (2, L, plugin.encode()),
                           (3, L, b"OfxImageEffectContextFilter"), (4, V, 1)] + plist)
        uuid = "06422d0f-cd85-4c7a-ac18-d33a98975e72"
        props = [
            int_prop(PROP_BASE, 2),
            prop(0xC0000049, msg((5, L, plugin.encode()))),
            prop(0xC000005E, msg((5, L, f"OfxImageEffectContextFilter_{uuid}_{nid}".encode()))),
            prop(0xC0000063, msg((4, V, 0))),
            prop(0xC0000087, msg((21, L, ofx))),
            prop(0xC00000D2, msg((4, V, 0))),
        ]
        rec = msg((1, V, nid), (2, V, num), (4, V, x), (5, V, y), (7, V, 1), (8, V, CORRECTOR),
                  (9, L, msg((2, L, bytes([3, 4, 5, 6, 18])))),
                  (10, L, d.serialize([(1, L, p) for p in props])),
                  (12, V, self.stamp))
        self.nodes.append((nid, rec))
        return nid

    def _lut_record(self, nid, num, x, y, lut):
        out = []
        for f, wt, v in d.parse(self.lut_node_base):
            if wt == V and f in (1, 2, 4, 5):
                v = {1: nid, 2: num, 4: x, 5: y}[f]
            out.append((f, wt, v))
        rec = d.serialize(out)
        kind = 8 if lut.lower().endswith(".dctl") else 6
        for was in (8, 6):                    # the base node may carry either kind
            rec = _replace(rec, msg((1, V, 0x860000A0), (2, L, msg((2, V, was)))),
                           msg((1, V, 0x860000A0), (2, L, msg((2, V, kind)))))
        old = [v for v in _leaves(rec) if v.lower().endswith((b".dctl", b".cube"))][0]
        return _replace(rec, old, lut.encode())

    # ---- wiring ------------------------------------------------------------
    def link(self, src, dst, dst_port=0):
        self.links.append((src, dst, dst_port))

    def feed(self, *node_ids):
        self.inputs.extend(node_ids)

    def out(self, node_id):
        self.output = node_id

    # ---- write -------------------------------------------------------------
    def graph_bytes(self):
        in_id, out_id = self._id(), self._id()
        link_recs = []
        for src, dst, port in self.links:
            fields = [(1, V, src), (3, V, dst)]
            if port:
                fields.append((4, V, port))
            fields += [(5, V, 64), (6, V, 64), (7, V, self._id())]
            link_recs.append(msg(*fields))
        in_rec = [(1, V, in_id), (2, V, 80)]
        for dst in self.inputs:
            in_rec.append((3, L, msg((1, V, self._id()), (2, V, 64), (3, V, in_id), (4, V, dst))))
        out_rec = msg((1, V, out_id), (2, V, 64),
                      (3, L, msg((1, V, self._id()), (2, V, 64), (3, V, out_id), (4, V, self.output))))
        out = []
        for f, wt, v in self.gf:
            if f == 1:
                out.append((1, V, self.next_id - 1))
            elif f == 7:
                if not any(x[0] == 7 for x in out):
                    out += [(7, L, rec) for _, rec in self.nodes]
                    out += [(8, L, r) for r in link_recs]
            elif f == 8:
                continue
            elif f == 9:
                out.append((9, L, d.serialize(in_rec)))
            elif f == 10:
                out.append((10, L, out_rec))
            else:
                out.append((f, wt, v))
        return d.serialize(out)

    def write(self, path):
        g = self.graph_bytes()
        newpb = d.serialize([(f, wt, g if f == 1 else v) for f, wt, v in self.top])
        newhex = d.body_encode(self.prefix, newpb)
        assert d.body_decode(newhex) == (self.prefix, newpb)
        open(path, "w", encoding="utf-8", newline="").write(self.xml[:self.span[0]] + newhex + self.xml[self.span[1]:])
        return path


def _leaves(b):
    for f, wt, v in d.parse(b):
        if wt == L:
            try:
                d.parse(v)
                sub = bool(v)
            except Exception:
                sub = False
            if sub:
                yield from _leaves(v)
            yield v


def _replace(b, old, new):
    out = []
    for f, wt, v in d.parse(b):
        if wt == L:
            if v == old:
                v = new
            else:
                try:
                    d.parse(v)
                    if v:
                        v = _replace(v, old, new)
                except Exception:
                    pass
        out.append((f, wt, v))
    return d.serialize(out)
