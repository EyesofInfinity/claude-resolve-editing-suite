"""Probe helpers: DRX Body decode/encode and a schema-less protobuf dumper."""
import os, re, struct, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ZJS = os.path.join(HERE, "zstd.cjs")     # .cjs, so a package.json above this folder cannot turn it into a module


def check_node():
    """Grade files need Node's zstd, which arrived in Node 22.15 and 23.8. Stops with a clear message before anything
    changes; no Node at all stops the same way."""
    try:
        v = subprocess.run(["node", "--version"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        sys.exit("Node was not found. Install Node 22.15 or newer from nodejs.org, then run this again.")
    m = re.match(r"v(\d+)\.(\d+)", v)
    have = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    if not (have >= (23, 8) or (22, 15) <= have < (23, 0)):
        sys.exit(f"Node {v} is too old for Resolve's grade files. Install Node 22.15 or newer from nodejs.org.")


def _zstd(mode, data):
    with tempfile.TemporaryDirectory() as td:
        a, b = os.path.join(td, "a"), os.path.join(td, "b")
        open(a, "wb").write(data)
        subprocess.run(["node", ZJS, mode, a, b], check=True)
        return open(b, "rb").read()


def body_decode(hexstr):
    raw = bytes.fromhex(hexstr)
    return raw[0], _zstd("d", raw[1:])


def body_encode(prefix, pb):
    return (bytes([prefix]) + _zstd("c", pb)).hex()


def read_varint(b, i):
    v = s = 0
    while True:
        c = b[i]; i += 1
        v |= (c & 0x7F) << s; s += 7
        if not c & 0x80:
            return v, i


def enc_varint(v):
    out = bytearray()
    while True:
        c = v & 0x7F; v >>= 7
        if v:
            out.append(c | 0x80)
        else:
            out.append(c); return bytes(out)


def parse(b):
    """Return list of (field, wiretype, value) or raise."""
    i, out = 0, []
    while i < len(b):
        key, i = read_varint(b, i)
        f, wt = key >> 3, key & 7
        if f == 0:
            raise ValueError("field 0")
        if wt == 0:
            v, i = read_varint(b, i)
        elif wt == 1:
            v = b[i:i + 8]; i += 8
        elif wt == 5:
            v = b[i:i + 4]; i += 4
        elif wt == 2:
            n, i = read_varint(b, i)
            v = b[i:i + n]; i += n
            if i > len(b):
                raise ValueError("overrun")
        else:
            raise ValueError("wt %d" % wt)
        out.append((f, wt, v))
    return out


def serialize(fields):
    out = bytearray()
    for f, wt, v in fields:
        out += enc_varint((f << 3) | wt)
        if wt == 0:
            out += enc_varint(v)
        elif wt == 2:
            out += enc_varint(len(v)) + v
        else:
            out += v
    return bytes(out)


def dump(b, ind=0, path="", lines=None):
    if lines is None:
        lines = []
    for f, wt, v in parse(b):
        p = f"{path}.{f}" if path else str(f)
        pad = "  " * ind
        if wt == 0:
            lines.append(f"{pad}{p} varint {v}")
        elif wt == 5:
            lines.append(f"{pad}{p} f32 {struct.unpack('<f', v)[0]:.6g} (0x{v.hex()})")
        elif wt == 1:
            lines.append(f"{pad}{p} f64 {struct.unpack('<d', v)[0]:.6g}")
        else:
            sub = None
            if v:
                try:
                    parse(v); sub = True
                except Exception:
                    sub = False
            printable = v and all(32 <= c < 127 or c in (9, 10, 13) for c in v)
            if printable and len(v) > 2:
                lines.append(f"{pad}{p} str {v.decode()!r}")
            elif sub:
                lines.append(f"{pad}{p} msg ({len(v)} bytes)")
                dump(v, ind + 1, p, lines)
            else:
                lines.append(f"{pad}{p} bytes {v.hex()}")
    return lines


def get_body(xml, tag):
    """Body hex inside <tag>...</tag> block."""
    m = re.search(r"<%s>.*?<Body>([0-9a-f]+)</Body>" % tag, xml, re.S)
    return m.group(1), m.span(1)
