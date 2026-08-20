# meshtools — STL decimation

Local toolchain for reducing STL triangle counts with quadric edge collapse.

> **Read this first.** This toolchain was installed and verified in an
> **ephemeral cloud container**, not on your desktop. That container gets
> reclaimed, and its `venv/` is Linux-specific and deliberately not committed
> (it's ~110 MB of binaries). What's committed is `decimate.py` and this README.
> To use it on your own machine, pull the repo and run the one-time setup below
> — it takes well under a minute.

## One-time setup on your machine

```bash
git pull
python -m venv meshtools/venv
# Linux/macOS:
meshtools/venv/bin/pip install pymeshlab
# Windows:
meshtools\venv\Scripts\pip install pymeshlab
```

Linux also needs the system libraries noted under *One system dependency* below.

## What got installed

| | |
|---|---|
| Library | **pymeshlab 2025.7.post1** (the first choice — no fallback was needed) |
| Verified on | Linux x86-64, Python 3.11, in a cloud container |
| Also pulled in | numpy 2.4.6 |
| Python | 3.11 |
| Venv | `meshtools/venv` (not committed — recreate locally, see above) |
| Blender | not installed, as requested |

open3d and `trimesh + fast_simplification` were **not** installed; pymeshlab
verified working, so the fallback chain was never entered.

### One system dependency (Linux only)

pymeshlab ships MeshLab's Qt plugins, and they refuse to load without OpenGL
system libraries — including `libio_base.so`, the plugin that reads and writes
STL. On a bare/headless Linux box the first run fails with
`Unknown format for save: stl`. Fixed here with:

```bash
sudo apt-get install -y libopengl0 libegl1 libglx0 libgl1
```

No GPU or display is needed at runtime — only these libraries being present.
Windows wheels bundle what they need, so this step is Linux-only.

## Activate and run

### Linux / macOS

```bash
source meshtools/venv/bin/activate
python meshtools/decimate.py model.stl
```

### Windows

The venv in this repo was built on Linux, so its binaries won't run on Windows.
Create one there once:

```bat
python -m venv meshtools\venv
meshtools\venv\Scripts\activate
pip install pymeshlab
```

Then, on every later session:

```bat
meshtools\venv\Scripts\activate
python meshtools\decimate.py model.stl
```

You can also skip activation entirely and call the venv's interpreter directly:

```bash
meshtools/venv/bin/python meshtools/decimate.py model.stl     # Linux/macOS
meshtools\venv\Scripts\python.exe meshtools\decimate.py model.stl   # Windows
```

## Usage

```
python decimate.py <input.stl> [--ratios 20,10,5,2] [--out DIR]
```

* `--ratios` — comma-separated **percentages of the original triangle count**.
  Default `20,10,5,2`. Fractional values are fine (`12.5` → `_12_5pct.stl`).
* `--out` — output directory, created if missing. Default `./decimated`.
* `--help` — full help.

Outputs are named `<stem>_<pct>pct.stl` and written as **binary STL**.
Decimation uses quadric edge collapse with boundary preservation, topology
preservation, normal preservation and optimal vertex placement. Each ratio is
decimated from the original mesh, not from the previous (already reduced)
result, so the 2% output isn't a decimation of a decimation.

**The input file is only ever read** — never modified, and never overwritten by
an output.

## Worked example

```console
$ source meshtools/venv/bin/activate
$ python meshtools/decimate.py testsphere.stl

Input:      /home/you/models/testsphere.stl
Triangles:  20480
Vertices:   10242
File size:  1000.1 KB (1024084 bytes)
Watertight: yes
Output dir: /home/you/models/decimated

Output               | Triangles | % of orig | File size | Watertight
---------------------+-----------+-----------+-----------+-----------
testsphere_20pct.stl | 4096      | 20.0%     | 200.1 KB  | yes
testsphere_10pct.stl | 2048      | 10.0%     | 100.1 KB  | yes
testsphere_5pct.stl  | 1024      | 5.0%      | 50.1 KB   | yes
testsphere_2pct.stl  | 410       | 2.0%      | 20.1 KB   | yes

Report written to /home/you/models/decimated/report.txt
```

The same table, plus the original's stats, is written to `report.txt` in the
output directory.

Exit codes: `0` success, `1` ran but produced no outputs, `2` bad input or
arguments.

## Expected RAM for a ~5M triangle mesh

Measured on this machine (peak RSS, load → decimate to 20% → save):

| Triangles | Peak RSS |
|---|---|
| 82 K | 165 MB |
| 328 K | 345 MB |
| 1.31 M | 1.06 GB |

That works out to roughly **730 MB per million triangles** at the margin, on top
of a ~100 MB interpreter/library baseline.

**A ~5M triangle mesh should peak around 3.5–4 GB.** Have **8 GB of free RAM**
to run it comfortably — the peak lands near the end of the collapse pass, and
swapping there slows it down badly. Notes:

* Peak scales with the **input** size, not the target, so `--ratios 20,10,5,2`
  costs about the same peak as a single ratio. The script reloads the source per
  ratio and frees the previous mesh, so the ratios don't stack.
* Memory is dominated by the per-vertex quadric heap; a 5M-triangle mesh with
  unusually many boundary edges or non-manifold vertices can run somewhat higher.
* If you're tight on RAM, run one ratio at a time — same peak, but a failure
  costs you less work.
