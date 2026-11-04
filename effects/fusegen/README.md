# Fusion versions of the effects

`out/` holds a Fuse for each effect that has one. `Install.bat` puts them in Fusion's Fuses folder, under `Develop`.

Each Fuse carries its DCTL's own code and runs it on the GPU, with the same controls as Fusion inputs. A transition has two image inputs,
Outgoing and Incoming, and a Progress input: animate Progress from 0 to 1 over the overlap. Frame Offset adds to the comp frame for the
effect's frame value, and Hold Frame uses Frame Offset alone.

If the kernel cannot run, the output is solid magenta. The reason is in the Fusion console and in `%TEMP%\DevelopFuse.log`.

To make a Fuse from a built DCTL:

    python -I fusegen.py [--out DIR] [file.dctl ...]

With no files it tries every `effects/*/build/*.dctl` and prints REFUSED for any it cannot carry. Generate a Fuse again after a change to its
DCTL. Do not edit a Fuse by hand.
