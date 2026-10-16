# -*- coding: utf-8 -*-
r"""Ringkas hasil telaah klinisi dari hasil/penilaian.csv (keluaran baca_hasil.py).

    python telaah-klinisi/analisis_hasil.py      # menulis hasil/ringkasan.txt

Isinya:
  1. sebaran penilaian tiap penilai, dengan interval kepercayaan 95% bagi proporsi "Tepat"
     dari bootstrap yang mencuplik ulang PASIEN (baris dari satu pasien tidak saling bebas,
     sama seperti pada kappa_bootstrap.py);
  2. sebaran menurut kelompok baris (cek/stop, tatalaksana, medikamentosa) dan menurut
     rekomendasi;
  3. kesepakatan antarpenilai pada baris yang dinilai keduanya: kesepakatan teramati, Cohen's
     kappa, dan PABAK, dengan interval bootstrap per pasien bila pasiennya lebih dari satu;
  4. saran yang ditulis pada baris "Belum tepat" dan "Tidak dapat dinilai".

Baris yang tidak diisi (di luar cakupan penilai, atau terlewat) tidak dihitung.
"""
import csv
import io
import math
import os
import random
import sys
from collections import Counter, OrderedDict, defaultdict

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "hasil", "penilaian.csv")
LAPORAN = os.path.join(HERE, "hasil", "ringkasan.txt")
KATEGORI = ("Tepat", "Belum tepat", "Tidak dapat dinilai")
B = 10000
SEED = 20261001


def pct(xs, q):
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    f, c = math.floor(k), math.ceil(k)
    return xs[f] if f == c else xs[f] + (xs[c] - xs[f]) * (k - f)


def kappa(pasangan):
    """(p_o, kappa, PABAK) untuk daftar pasangan kategori."""
    n = len(pasangan)
    if not n:
        return float("nan"), float("nan"), float("nan")
    po = sum(a == b for a, b in pasangan) / n
    ma, mb = Counter(a for a, _ in pasangan), Counter(b for _, b in pasangan)
    pe = sum(ma[k] * mb[k] for k in KATEGORI) / n / n
    k = (po - pe) / (1 - pe) if pe < 1 else float("nan")
    q = len(KATEGORI)
    return po, k, (q * po - 1) / (q - 1)


def boot_pasien(kelompok, fungsi, rng):
    """Bootstrap per pasien: kelompok = {pasien: [unit]}, fungsi(list unit) -> angka."""
    kunci = list(kelompok)
    hasil = []
    for _ in range(B):
        ambil = [u for p in (rng.choice(kunci) for _ in kunci) for u in kelompok[p]]
        v = fungsi(ambil)
        if v == v:                                      # buang NaN
            hasil.append(v)
    return pct(hasil, 0.025), pct(hasil, 0.975)


def main():
    rows = [r for r in csv.DictReader(io.open(DATA, encoding="utf-8-sig")) if r["penilaian"]]
    rng = random.Random(SEED)
    penilai = list(OrderedDict.fromkeys(r["penilai"] for r in rows))
    ket = {r["penilai"]: r["keterangan"] for r in rows}
    baris = []

    def out(s=""):
        baris.append(s)
        print(s)

    out("=" * 92)
    out("TELAAH KLINISI -- ringkasan hasil (dari hasil/penilaian.csv)")
    out("=" * 92)

    # ── 1. sebaran per penilai ────────────────────────────────────────────────────────
    out("\n-- 1. sebaran penilaian per penilai " + "-" * 56)
    for p in penilai:
        rs = [r for r in rows if r["penilai"] == p]
        c = Counter(r["penilaian"] for r in rs)
        pas = sorted({int(r["no"]) for r in rs})
        n = len(rs)
        teks = "  ".join("%s %d (%.1f%%)" % (k, c[k], 100 * c[k] / n) for k in KATEGORI)
        ci = ""
        if len(pas) > 1:
            per = defaultdict(list)
            for r in rs:
                per[r["no"]].append(r["penilaian"] == "Tepat")
            lo, hi = boot_pasien(per, lambda u: sum(u) / len(u), rng)
            ci = "   Tepat 95%% CI per pasien %.1f%%--%.1f%%" % (100 * lo, 100 * hi)
        out("%-7s %-32s pasien %s, %d baris" % (p, ket[p], "%d-%d" % (pas[0], pas[-1]), n))
        out("        %s%s" % (teks, ci))
        # tanpa "Tidak dapat dinilai"
        dn = c["Tepat"] + c["Belum tepat"]
        out("        dari baris yang dapat dinilai (%d): Tepat %.1f%%" % (dn, 100 * c["Tepat"] / dn))

    # ── 2. menurut kelompok dan rekomendasi ──────────────────────────────────────────
    out("\n-- 2a. menurut kelompok baris " + "-" * 62)
    kelompok = list(OrderedDict.fromkeys(r["kelompok"] for r in rows))
    for p in penilai:
        for g in kelompok:
            rs = [r for r in rows if r["penilai"] == p and r["kelompok"] == g]
            if not rs:
                continue
            c = Counter(r["penilaian"] for r in rs)
            out("%-7s %-22s n=%3d  Tepat %3d  Belum tepat %3d  Tidak dapat dinilai %3d"
                % (p, g, len(rs), c["Tepat"], c["Belum tepat"], c["Tidak dapat dinilai"]))
    out("\n-- 2b. menurut rekomendasi (T/B/X = Tepat/Belum tepat/Tidak dapat dinilai) " + "-" * 16)
    rec = sorted({(r["recId"], r["cor"]) for r in rows}, key=lambda x: x[0])
    out("%-10s %-14s" % ("recId", "COR") + "".join("%16s" % p for p in penilai))
    for rid, cor in rec:
        sel = []
        for p in penilai:
            c = Counter(r["penilaian"] for r in rows if r["penilai"] == p and r["recId"] == rid)
            sel.append("%d/%d/%d" % (c["Tepat"], c["Belum tepat"], c["Tidak dapat dinilai"])
                       if sum(c.values()) else "-")
        out("%-10s %-14s" % (rid, cor) + "".join("%16s" % s for s in sel))

    # ── 3. kesepakatan ───────────────────────────────────────────────────────────────
    out("\n-- 3. kesepakatan antarpenilai pada baris yang dinilai keduanya " + "-" * 28)
    nilai = {(r["penilai"], r["no"], r["recId"], r["rekomendasi"]): r["penilaian"] for r in rows}
    for i, a in enumerate(penilai):
        for b in penilai[i + 1:]:
            per = defaultdict(list)
            for (p, no, rid, tx), v in nilai.items():
                if p == a and (b, no, rid, tx) in nilai:
                    per[no].append((v, nilai[(b, no, rid, tx)]))
            pas = [u for v in per.values() for u in v]
            if not pas:
                continue
            po, k, pabak = kappa(pas)
            out("%s vs %s: %d baris dari %d pasien" % (a, b, len(pas), len(per)))
            out("    kesepakatan teramati %.3f   Cohen's kappa %.3f   PABAK %.3f" % (po, k, pabak))
            if len(per) > 1:
                lo, hi = boot_pasien(per, lambda u: kappa(u)[1], rng)
                lo2, hi2 = boot_pasien(per, lambda u: kappa(u)[0], rng)
                out("    95%% CI per pasien: kappa %.3f--%.3f, kesepakatan %.3f--%.3f" % (lo, hi, lo2, hi2))
            dua = [("Tepat" if x == "Tepat" else "lain", "Tepat" if y == "Tepat" else "lain")
                   for x, y in pas]
            po2 = sum(x == y for x, y in dua) / len(dua)
            out("    dua kategori (Tepat vs lainnya): kesepakatan %.3f" % po2)
            out("    matriks (baris %s, kolom %s):" % (a, b))
            m = Counter(pas)
            out("    %-22s" % "" + "".join("%22s" % k for k in KATEGORI))
            for x in KATEGORI:
                out("    %-22s" % x + "".join("%22d" % m[(x, y)] for y in KATEGORI))
    # ketiganya pada pasien yang sama
    tiga = defaultdict(dict)
    for (p, no, rid, tx), v in nilai.items():
        tiga[(no, rid, tx)][p] = v
    lengkap = {k: v for k, v in tiga.items() if len(v) == len(penilai)}
    if lengkap:
        sama = sum(len(set(v.values())) == 1 for v in lengkap.values())
        out("ketiganya: %d baris dinilai ketiga penilai, %d sepakat penuh" % (len(lengkap), sama))

    # ── 4. saran ─────────────────────────────────────────────────────────────────────
    out("\n-- 4. saran pada baris yang tidak dinilai Tepat " + "-" * 44)
    for p in penilai:
        rs = [r for r in rows if r["penilai"] == p and r["penilaian"] != "Tepat"]
        out("%s (%d baris, %d bersaran):" % (p, len(rs), sum(1 for r in rs if r["saran"])))
        for r in sorted(rs, key=lambda r: (r["recId"], int(r["no"]))):
            out("    P%-2s %-8s %-19s %s" % (r["no"], r["recId"], r["penilaian"], r["saran"] or "-"))

    io.open(LAPORAN, "w", encoding="utf-8").write("\n".join(baris) + "\n")


if __name__ == "__main__":
    main()
