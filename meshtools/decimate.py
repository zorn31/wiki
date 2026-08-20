#!/usr/bin/env python3
"""Decimate an STL mesh to several target percentages of its triangle count.

Uses MeshLab's quadric edge collapse filter (via pymeshlab) with boundary and
topology preservation enabled. The input file is only ever read, never written.

Example:
    python decimate.py bracket.stl --ratios 20,10,5,2 --out ./decimated
"""

import argparse
import os
import sys
from pathlib import Path

DEFAULT_RATIOS = "20,10,5,2"
DEFAULT_OUT = "./decimated"


def die(msg, code=2):
    """Print a clear error to stderr and exit."""
    print("error: %s" % msg, file=sys.stderr)
    sys.exit(code)


def import_pymeshlab():
    """Import pymeshlab, muting the harmless GPU/Qt plugin chatter on headless boxes."""
    try:
        import pymeshlab  # noqa: F401
    except ImportError:
        die("pymeshlab is not installed in this interpreter.\n"
            "       Activate the venv first (see meshtools/README.md), e.g.\n"
            "         Linux/macOS:  source meshtools/venv/bin/activate\n"
            "         Windows:      meshtools\\venv\\Scripts\\activate")
    return sys.modules["pymeshlab"]


def parse_ratios(raw):
    """'20,10,5,2' -> [20.0, 10.0, 5.0, 2.0], validated and de-duplicated."""
    ratios = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            value = float(chunk)
        except ValueError:
            die("--ratios expects comma-separated numbers, got %r" % chunk)
        if not 0 < value <= 100:
            die("--ratios values must be >0 and <=100 (percent), got %g" % value)
        if value not in ratios:
            ratios.append(value)
    if not ratios:
        die("--ratios did not contain any values")
    return ratios


def ratio_tag(value):
    """20.0 -> '20', 2.5 -> '2.5' — used in the output filename."""
    text = ("%g" % value)
    return text.replace(".", "_")


def check_input(path_text):
    """Validate the input path and return it resolved."""
    path = Path(path_text).expanduser()
    if not path.exists():
        die("input path does not exist: %s" % path)
    if path.is_dir():
        die("input path is a directory, expected a mesh file: %s" % path)
    if not os.access(path, os.R_OK):
        die("input file is not readable (check permissions): %s" % path)
    if path.stat().st_size == 0:
        die("input file is empty: %s" % path)
    return path.resolve()


def load_mesh(pymeshlab, path):
    """Load the mesh, turning any loader failure into a clear message."""
    ms = pymeshlab.MeshSet()
    try:
        ms.load_new_mesh(str(path))
    except Exception as exc:  # pymeshlab raises PyMeshLabException subclasses
        die("could not read %s as a mesh.\n"
            "       pymeshlab said: %s" % (path, exc))
    if ms.current_mesh().face_number() == 0:
        die("%s loaded but contains no triangles (point cloud or corrupt file?)" % path)
    return ms


def watertight(ms):
    """Return (is_watertight, detail) for the current mesh."""
    try:
        m = ms.get_topological_measures()
    except Exception as exc:
        return None, "unknown (%s)" % exc
    boundary = int(m.get("boundary_edges", 0))
    holes = int(m.get("number_holes", 0))
    nm_edges = int(m.get("non_two_manifold_edges", 0))
    nm_verts = int(m.get("non_two_manifold_vertices", 0))
    ok = boundary == 0 and nm_edges == 0 and nm_verts == 0
    if ok:
        return True, "yes"
    problems = []
    if boundary:
        problems.append("%d boundary edges" % boundary)
    if holes:
        problems.append("%d holes" % holes)
    if nm_edges:
        problems.append("%d non-manifold edges" % nm_edges)
    if nm_verts:
        problems.append("%d non-manifold vertices" % nm_verts)
    return False, "no (%s)" % ", ".join(problems)


def human_size(num_bytes):
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return "%.1f %s" % (size, unit) if unit != "B" else "%d B" % num_bytes
        size /= 1024


def render_table(rows):
    """rows: list of tuples -> aligned plain-text table."""
    headers = ("Output", "Triangles", "% of orig", "File size", "Watertight")
    table = [headers] + [tuple(str(c) for c in r) for r in rows]
    widths = [max(len(r[i]) for r in table) for i in range(len(headers))]
    line = "-+-".join("-" * w for w in widths)
    out = []
    for idx, row in enumerate(table):
        out.append(" | ".join(row[i].ljust(widths[i]) for i in range(len(headers))))
        if idx == 0:
            out.append(line)
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(
        prog="decimate.py",
        description="Decimate an STL mesh to several percentages of its original "
                    "triangle count using quadric edge collapse (pymeshlab).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="example:\n"
               "  python decimate.py bracket.stl --ratios 20,10,5,2 --out ./decimated\n\n"
               "The input file is never modified or overwritten.",
    )
    parser.add_argument("input", help="path to the input mesh (.stl, or anything MeshLab reads)")
    parser.add_argument("--ratios", default=DEFAULT_RATIOS,
                        help="comma-separated target percentages of the original triangle "
                             "count (default: %s)" % DEFAULT_RATIOS)
    parser.add_argument("--out", default=DEFAULT_OUT, metavar="DIR",
                        help="output directory (default: %s)" % DEFAULT_OUT)
    args = parser.parse_args()

    ratios = parse_ratios(args.ratios)
    src = check_input(args.input)

    pymeshlab = import_pymeshlab()

    out_dir = Path(args.out).expanduser().resolve()
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        die("could not create output directory %s: %s" % (out_dir, exc))

    ms = load_mesh(pymeshlab, src)
    orig_faces = ms.current_mesh().face_number()
    orig_verts = ms.current_mesh().vertex_number()
    orig_size = src.stat().st_size
    orig_wt, orig_wt_text = watertight(ms)

    header = [
        "Input:      %s" % src,
        "Triangles:  %d" % orig_faces,
        "Vertices:   %d" % orig_verts,
        "File size:  %s (%d bytes)" % (human_size(orig_size), orig_size),
        "Watertight: %s" % orig_wt_text,
        "Output dir: %s" % out_dir,
        "",
    ]
    print("\n".join(header))

    stem = src.stem
    rows = []
    failures = []

    for pct in ratios:
        target = max(4, int(round(orig_faces * pct / 100.0)))
        dest = out_dir / ("%s_%spct.stl" % (stem, ratio_tag(pct)))

        if dest.resolve() == src:
            failures.append("%s: refusing to overwrite the input file" % dest.name)
            continue
        if target >= orig_faces:
            failures.append("%s: target %d triangles is not below the original %d, skipped"
                            % (dest.name, target, orig_faces))
            continue

        # Reload the source for every ratio so each output is decimated from the
        # original mesh rather than from the previous (already reduced) result.
        work = load_mesh(pymeshlab, src)
        try:
            work.meshing_decimation_quadric_edge_collapse(
                targetfacenum=target,
                preserveboundary=True,
                boundaryweight=1.0,
                preservenormal=True,
                preservetopology=True,
                optimalplacement=True,
                planarquadric=True,
                autoclean=True,
            )
            work.save_current_mesh(str(dest), binary=True)
        except Exception as exc:
            failures.append("%s: %s" % (dest.name, exc))
            continue

        check = pymeshlab.MeshSet()
        check.load_new_mesh(str(dest))
        faces = check.current_mesh().face_number()
        _, wt_text = watertight(check)
        size = dest.stat().st_size
        rows.append((dest.name, faces, "%.1f%%" % (100.0 * faces / orig_faces),
                     human_size(size), wt_text))

    if rows:
        table = render_table(rows)
        print(table)
    else:
        table = "(no outputs were produced)"
        print(table)

    report_lines = list(header) + [table, ""]
    if failures:
        report_lines += ["Problems:"] + ["  - %s" % f for f in failures] + [""]
        print("\nProblems:")
        for f in failures:
            print("  - %s" % f)

    report = out_dir / "report.txt"
    try:
        report.write_text("\n".join(report_lines), encoding="utf-8")
        print("\nReport written to %s" % report)
    except OSError as exc:
        print("warning: could not write %s: %s" % (report, exc), file=sys.stderr)

    sys.exit(1 if not rows else 0)


if __name__ == "__main__":
    main()
