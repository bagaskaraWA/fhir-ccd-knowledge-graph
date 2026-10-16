# -*- coding: utf-8 -*-
r"""Bekukan paket telaah klinisi: salin artefak yang dinilai, lalu catat sidik jarinya.

Perumusan kalimat oleh model bersifat stokastik, sehingga ringkasan yang dinilai klinisi
harus berupa berkas yang tetap. Skrip ini menyalin ringkasan dan muatan faktanya ke
telaah-klinisi/paket/, lalu menuliskan MANIFEST.txt berisi SHA-256 tiap berkas.

Manifest itu yang membuat pembekuan dapat dibuktikan: setelah penilaian selesai, jalankan
--verify untuk memastikan tidak ada berkas yang berubah sejak dibagikan.

    python telaah-klinisi/bekukan.py            # bekukan
    python telaah-klinisi/bekukan.py --verify   # periksa ulang setelah penilaian
"""
import argparse
import hashlib
import io
import os
import shutil
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(BASE, "telaah-klinisi")
PAKET = os.path.join(HERE, "paket")
EVAL = os.path.join(BASE, "eval")
LIST = os.path.join(HERE, "pasien.txt")
MANIFEST = os.path.join(PAKET, "MANIFEST.txt")

# nama berkas per pasien -> direktori asalnya
SOURCES = [("rekam_%s.md", PAKET), ("briefing_%s.md", EVAL),
           ("briefing_facts_%s.json", EVAL)]


def patients():
    if not os.path.exists(LIST):
        sys.exit("pasien.txt tidak ditemukan: %s" % LIST)
    out = []
    for line in io.open(LIST, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line.split()[0])
    return out


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verify", action="store_true",
                    help="bandingkan isi paket terhadap MANIFEST.txt")
    args = ap.parse_args()

    pids = patients()

    if args.verify:
        if not os.path.exists(MANIFEST):
            sys.exit("MANIFEST.txt belum ada -- jalankan tanpa --verify dahulu.")
        recorded, bad, gone = {}, [], []
        for line in io.open(MANIFEST, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#"):
                digest, name = line.split(None, 1)
                recorded[name] = digest
        for name, digest in sorted(recorded.items()):
            p = os.path.join(PAKET, name)
            if not os.path.exists(p):
                gone.append(name)
            elif sha(p) != digest:
                bad.append(name)
        print("tercatat  : %d berkas" % len(recorded))
        print("hilang    : %d" % len(gone))
        print("berubah   : %d" % len(bad))
        for n in gone + bad:
            print("   %s" % n)
        if gone or bad:
            print("\nPaket TIDAK utuh. Penilaian merujuk pada berkas yang sudah berubah.")
            return 1
        print("\nPaket utuh -- seluruh berkas identik dengan saat dibekukan.")
        return 0

    if not os.path.isdir(PAKET):
        os.makedirs(PAKET)

    disalin, kurang = 0, []
    for pid in pids:
        for pola, asal in SOURCES:
            nama = pola % pid
            src = os.path.join(asal, nama)
            if not os.path.exists(src):
                kurang.append(nama)
                continue
            if asal != PAKET:
                shutil.copy2(src, os.path.join(PAKET, nama))
                disalin += 1

    if kurang:
        print("BELUM LENGKAP -- %d berkas tidak ditemukan:" % len(kurang))
        for n in kurang[:8]:
            print("   %s" % n)
        if len(kurang) > 8:
            print("   ... dan %d lainnya" % (len(kurang) - 8))
        print("\nLengkapi dahulu; paket tidak dibekukan.")
        return 1

    rows = []
    for pid in pids:
        for pola, _ in SOURCES:
            nama = pola % pid
            rows.append((sha(os.path.join(PAKET, nama)), nama))

    with io.open(MANIFEST, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# Paket telaah klinisi -- dibekukan.\n")
        fh.write("# %d pasien x %d berkas = %d berkas.\n" % (len(pids), len(SOURCES), len(rows)))
        fh.write("# Periksa ulang dengan: python telaah-klinisi/bekukan.py --verify\n#\n")
        for digest, nama in rows:
            fh.write("%s  %s\n" % (digest, nama))

    print("pasien    : %d" % len(pids))
    print("disalin   : %d berkas dari eval/" % disalin)
    print("manifest  : %d berkas tercatat -> %s"
          % (len(rows), os.path.relpath(MANIFEST, BASE)))
    print("\nPaket beku. Jangan bangkitkan ulang ringkasan setelah titik ini;")
    print("bila terpaksa, bekukan ulang dan catat alasannya.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
