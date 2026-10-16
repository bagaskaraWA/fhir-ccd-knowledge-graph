# -*- coding: utf-8 -*-
r"""Bangkitkan briefing untuk seluruh pasien pada pasien.txt.

Pemandu untuk crs_briefing.py: membaca daftar pasien, melewati yang briefing-nya sudah
ada, dan menjalankan sisanya satu per satu. Aman dijalankan ulang -- pasien yang sudah
selesai tidak dibangkitkan dua kali, sehingga proses yang terputus dapat dilanjutkan.

Kredensial dibaca dari environment oleh crs_briefing.py sendiri. Skrip ini hanya memeriksa
bahwa variabelnya terisi; nilainya tidak pernah dibaca, dicetak, maupun disimpan.

    python telaah-klinisi/buat_briefing.py --dry-run     # lihat rencananya dulu
    python telaah-klinisi/buat_briefing.py
"""
import argparse
import os
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIST = os.path.join(BASE, "telaah-klinisi", "pasien.txt")
EVAL = os.path.join(BASE, "eval")
SCRIPT = os.path.join(BASE, "crs_briefing.py")

REQUIRED = ("NEO4J_PASSWORD", "ANTHROPIC_API_KEY")
# Non-secret settings, echoed so a wrong database or username fails visibly rather than
# as an opaque auth error. NEO4J_USER defaults to "neo4j" inside crs_briefing.py.
OPTIONAL = ("NEO4J_URI", "NEO4J_USER", "NEO4J_DATABASE", "ANTHROPIC_MODEL")
DEFAULTS = {"NEO4J_URI": "bolt://localhost:7687", "NEO4J_USER": "neo4j",
            "NEO4J_DATABASE": "sihdfhir", "ANTHROPIC_MODEL": "claude-sonnet-5"}


def read_list():
    if not os.path.exists(LIST):
        sys.exit("pasien.txt tidak ditemukan: %s" % LIST)
    out = []
    for line in open(LIST, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line.split()[0])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="tampilkan rencana, jangan jalankan")
    ap.add_argument("--python", default=sys.executable, help="interpreter yang dipakai")
    args = ap.parse_args()

    pasien = read_list()
    todo = [p for p in pasien
            if not os.path.exists(os.path.join(EVAL, "briefing_%s.md" % p))]
    done = len(pasien) - len(todo)

    print("daftar pasien : %d" % len(pasien))
    print("sudah ada     : %d" % done)
    print("akan dibuat   : %d" % len(todo))

    if not todo:
        print("\nSeluruh briefing sudah ada. Tidak ada yang perlu dijalankan.")
        return 0

    missing = [v for v in REQUIRED if not os.environ.get(v)]
    if missing:
        print("\nVariabel environment berikut belum terisi: %s" % ", ".join(missing))
        print("Isi dahulu, lalu jalankan ulang. Nilainya tidak dibaca oleh skrip ini.")
        if not args.dry_run:
            return 1
    print()
    for v in OPTIONAL:
        val = os.environ.get(v)
        print("   %-16s = %-26s %s"                            # non-rahasia
              % (v, val or DEFAULTS[v], "" if val else "(bawaan)"))
    print("   %-16s = %s" % ("kredensial", "terisi" if not missing else "BELUM LENGKAP"))

    if args.dry_run:
        print("\n--dry-run: tidak ada yang dijalankan. Yang akan dibuat:")
        for p in todo:
            print("   %s" % p)
        return 0

    print("\nmulai -- perkiraan %d-%d menit, sekitar $%.2f\n"
          % (len(todo) // 2, len(todo), 0.055 * len(todo)))

    ok, gagal, t0 = [], [], time.time()
    for i, pid in enumerate(todo, 1):
        print("[%2d/%2d] %s ... " % (i, len(todo), pid[:8]), end="", flush=True)
        t = time.time()
        try:
            r = subprocess.run([args.python, SCRIPT, pid, "--save"],
                               cwd=BASE, capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            print("TIMEOUT")
            gagal.append((pid, "timeout 600s"))
            continue
        if r.returncode == 0 and os.path.exists(os.path.join(EVAL, "briefing_%s.md" % pid)):
            print("ok (%.0fs)" % (time.time() - t))
            ok.append(pid)
        else:
            tail = (r.stderr or r.stdout or "").strip().splitlines()
            print("GAGAL -- %s" % (tail[-1][:90] if tail else "exit %d" % r.returncode))
            gagal.append((pid, tail[-1][:200] if tail else "exit %d" % r.returncode))

    print("\nselesai dalam %.1f menit" % ((time.time() - t0) / 60.0))
    print("berhasil : %d" % len(ok))
    print("gagal    : %d" % len(gagal))
    for pid, why in gagal:
        print("   %s  %s" % (pid[:8], why))
    if gagal:
        print("\nJalankan ulang skrip ini untuk mencoba lagi yang gagal saja.")
    else:
        print("\nLangkah berikutnya:")
        print("   python faithfulness_check.py")
        print("   python telaah-klinisi/buat_formulir.py")
    return 1 if gagal else 0


if __name__ == "__main__":
    sys.exit(main())
