// usage: node zstd.js d|c <infile> <outfile>   (raw bytes in, raw bytes out)
const z = require('zlib'), fs = require('fs');
const [mode, inp, out] = process.argv.slice(2);
const buf = fs.readFileSync(inp);
const res = mode === 'd' ? z.zstdDecompressSync(buf) : z.zstdCompressSync(buf, { params: { [z.constants.ZSTD_c_compressionLevel]: 3, [z.constants.ZSTD_c_checksumFlag]: 1 } });
fs.writeFileSync(out, res);
