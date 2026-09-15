#!/usr/bin/env python3
"""Build the browser payload for the QT-RR Dynamics project page.

Reads the de-identified exercise-test CSVs in data/mims2-qtrr/ and writes the
compact files the page fetches at runtime:

    assets/projects/qt-rr-dynamics/data/meta.json
    assets/projects/qt-rr-dynamics/data/subject_N/beats.json
    assets/projects/qt-rr-dynamics/data/subject_N/ecg_int16.bin

Pure standard library, Python 3.6 compatible, deterministic: re-running on
unchanged input produces byte-identical output (verified by hashing).

Usage:
    python3 scripts/projects/build_qtrr_data.py [--check]

    --check  build into a temporary directory and diff against the committed
             payload instead of writing it (non-zero exit if they differ).
"""

from __future__ import print_function

import argparse
import csv
import hashlib
import json
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))
SRC = os.path.join(REPO, "data", "mims2-qtrr")
OUT = os.path.join(REPO, "assets", "projects", "qt-rr-dynamics", "data")

SUBJECTS = (1, 2)
FS = 100
DURATION_S = 1200
ECG_SCALE = 0.001          # mV per int16 LSB
ECG_TOL_MV = 0.0005        # half an LSB
FLOAT_EPS = 1e-9
PEAK_TIME_S = 600.0        # t_rel_peak_s == t_s - 600 by construction
AXIS_PAD = 0.04            # 4 % padding on hysteresis axis ranges
MAX_LANDMARK_SPAN = 100    # samples; overlay scan bound, asserted below

LANDMARKS = ("qrson_sample_100hz", "r_sample_100hz",
             "tpeak_sample_100hz", "toff_sample_100hz")


class BuildError(Exception):
    pass


def is_missing(text):
    return text is None or text.strip() == "" or text.strip().lower() in ("nan", "na")


def as_float(text):
    """CSV cell -> float or None. Missing values never become 0."""
    return None if is_missing(text) else float(text)


def as_index(text):
    """CSV cell -> int index or None, rejecting non-integral values."""
    if is_missing(text):
        return None
    value = float(text)
    if value != int(value):
        raise BuildError("non-integral landmark index: %r" % text)
    return int(value)


def rounded(value, digits):
    return None if value is None else round(value, digits)


def read_ecg(subject):
    """Return the ECG column, asserting the sampling grid is exactly uniform."""
    path = os.path.join(SRC, "subject_%d_ecg_100hz.csv" % subject)
    samples = []
    with open(path) as handle:
        reader = csv.reader(handle)
        header = next(reader)
        if header != ["sample_idx", "t_s", "t_rel_peak_s", "ecg_mv"]:
            raise BuildError("unexpected ECG header in %s: %r" % (path, header))
        for row_no, row in enumerate(reader):
            index = int(row[0])
            if index != row_no:
                raise BuildError("ECG sample_idx not contiguous at row %d" % row_no)
            if abs(float(row[1]) - index / float(FS)) > FLOAT_EPS:
                raise BuildError("ECG t_s off-grid at sample %d" % index)
            if abs(float(row[2]) - (index / float(FS) - PEAK_TIME_S)) > 1e-6:
                raise BuildError("ECG t_rel_peak_s off-grid at sample %d" % index)
            samples.append(float(row[3]))
    return samples


def read_beats(subject):
    path = os.path.join(SRC, "subject_%d_beats.csv" % subject)
    with open(path) as handle:
        rows = list(csv.DictReader(handle))
    for name in LANDMARKS + ("beat_idx", "t_s", "phase", "rr_ms", "qt_ms", "tamp_mv",
                             "rr_ms_smooth", "qt_ms_smooth", "tamp_mv_smooth"):
        if name not in rows[0]:
            raise BuildError("%s missing column %s" % (path, name))
    return rows


def quality_report(rows, n_samples):
    """Classify every beat's ECG-annotation usability.

    Records are never dropped: a beat whose ECG annotations are unusable keeps
    its smoothed hysteresis point. This mirrors the client-side predicate in
    js/overlays.js exactly.
    """
    report = {
        "incompleteLandmarks": [],
        "strictReversals": [],
        "reversalsWithFiniteQt": [],
        "ties": [],
        "tiesWithFiniteQt": [],
        "missingQt": [],
        "missingTamp": [],
        "suppressedTampLabelOnValidT": [],
    }
    max_span = 0
    for row in rows:
        beat = int(row["beat_idx"])
        marks = {}
        for name in LANDMARKS:
            marks[name] = as_index(row[name])
            if marks[name] is not None and not (0 <= marks[name] < n_samples):
                raise BuildError("beat %d: landmark %s out of ECG bounds" % (beat, name))

        qrson = marks["qrson_sample_100hz"]
        r_peak = marks["r_sample_100hz"]
        t_peak = marks["tpeak_sample_100hz"]
        t_off = marks["toff_sample_100hz"]
        qt = as_float(row["qt_ms"])
        tamp = as_float(row["tamp_mv"])

        if None in (qrson, r_peak, t_peak, t_off):
            report["incompleteLandmarks"].append(beat)
        else:
            if qrson > r_peak or r_peak >= t_peak or qrson >= t_off:
                raise BuildError("beat %d: unexpected landmark order %r" % (beat, marks))
            if t_peak > t_off:
                report["strictReversals"].append(beat)
                if qt is not None:
                    report["reversalsWithFiniteQt"].append(beat)
            elif t_peak == t_off:
                report["ties"].append(beat)
                if qt is not None:
                    report["tiesWithFiniteQt"].append(beat)
            max_span = max(max_span, t_off - qrson)

        if qt is None:
            report["missingQt"].append(beat)
        if tamp is None:
            report["missingTamp"].append(beat)

        order_ok = (None not in (qrson, r_peak, t_peak, t_off)
                    and qrson <= r_peak < t_peak <= t_off and qrson < t_off)
        if qt is not None and order_ok and tamp is None:
            report["suppressedTampLabelOnValidT"].append(beat)

    if max_span >= MAX_LANDMARK_SPAN:
        raise BuildError("max QRSon->Toff span %d >= scan bound %d"
                         % (max_span, MAX_LANDMARK_SPAN))
    report["maxLandmarkSpanSamples"] = max_span
    return report


def axis_range(values, pad=AXIS_PAD):
    low, high = min(values), max(values)
    if high == low:
        high = low + 1.0
    margin = (high - low) * pad
    return [low - margin, high + margin]


def build_subject(subject, out_dir, log):
    ecg = read_ecg(subject)
    rows = read_beats(subject)
    n_samples = len(ecg)
    n_beats = len(rows)
    log("subject %d: %d ECG samples, %d beats" % (subject, n_samples, n_beats))

    if n_samples != DURATION_S * FS + 1:
        raise BuildError("subject %d: unexpected ECG length %d" % (subject, n_samples))

    # --- ECG -> int16, round-trip verified -------------------------------
    quantised = [int(round(value / ECG_SCALE)) for value in ecg]
    worst = 0.0
    for raw, code in zip(ecg, quantised):
        if not -32768 <= code <= 32767:
            raise BuildError("subject %d: ECG sample %r exceeds int16 range" % (subject, raw))
        worst = max(worst, abs(code * ECG_SCALE - raw))
    if worst > ECG_TOL_MV + FLOAT_EPS:
        raise BuildError("subject %d: ECG round-trip %.6f mV exceeds tolerance"
                         % (subject, worst))
    log("  int16 round-trip max error %.4f uV (tolerance %.1f uV + eps)"
        % (worst * 1000.0, ECG_TOL_MV * 1000.0))

    subject_dir = os.path.join(out_dir, "subject_%d" % subject)
    if not os.path.isdir(subject_dir):
        os.makedirs(subject_dir)
    with open(os.path.join(subject_dir, "ecg_int16.bin"), "wb") as handle:
        handle.write(struct.pack("<%dh" % len(quantised), *quantised))

    # --- beat arrays ------------------------------------------------------
    columns = {
        "t": [], "rIdx": [], "qrsOn": [], "tPeak": [], "tOff": [],
        "rr": [], "qt": [], "tamp": [], "rrS": [], "qtS": [], "tampS": [],
    }
    first_recovery = None
    previous_t = None
    for position, row in enumerate(rows):
        if int(row["beat_idx"]) != position:
            raise BuildError("subject %d: beat_idx not contiguous at %d" % (subject, position))

        t_s = as_float(row["t_s"])
        if t_s is None or not 0.0 <= t_s <= DURATION_S:
            raise BuildError("subject %d: beat %d has bad t_s" % (subject, position))
        if previous_t is not None and t_s <= previous_t:
            raise BuildError("subject %d: t_s not strictly increasing at %d" % (subject, position))
        previous_t = t_s

        r_index = as_index(row["r_sample_100hz"])
        if r_index is None:
            raise BuildError("subject %d: beat %d has no R-peak" % (subject, position))
        if abs(t_s - r_index / float(FS)) > 0.01:
            raise BuildError("subject %d: beat %d t_s/rIdx disagree" % (subject, position))

        phase = row["phase"]
        expected = "exercise" if t_s <= PEAK_TIME_S else "recovery"
        if phase != expected:
            raise BuildError("subject %d: beat %d phase %r contradicts t_s<=600 rule"
                             % (subject, position, phase))
        if phase == "recovery" and first_recovery is None:
            first_recovery = position

        columns["t"].append(round(t_s, 3))
        columns["rIdx"].append(r_index)
        columns["qrsOn"].append(as_index(row["qrson_sample_100hz"]))
        columns["tPeak"].append(as_index(row["tpeak_sample_100hz"]))
        columns["tOff"].append(as_index(row["toff_sample_100hz"]))
        columns["rr"].append(rounded(as_float(row["rr_ms"]), 1))
        columns["qt"].append(rounded(as_float(row["qt_ms"]), 1))
        columns["tamp"].append(rounded(as_float(row["tamp_mv"]), 5))
        columns["rrS"].append(round(float(row["rr_ms_smooth"]), 2))
        columns["qtS"].append(round(float(row["qt_ms_smooth"]), 2))
        columns["tampS"].append(round(float(row["tamp_mv_smooth"]), 5))

    if first_recovery is None:
        raise BuildError("subject %d: no recovery phase found" % subject)

    for name in ("rrS", "qtS", "tampS"):
        if any(value is None for value in columns[name]):
            raise BuildError("subject %d: %s has a missing value" % (subject, name))
    if any(value is None for value in columns["rr"]):
        raise BuildError("subject %d: rr has a missing value" % subject)
    lengths = set(len(values) for values in columns.values())
    if lengths != set([n_beats]):
        raise BuildError("subject %d: ragged beat arrays %r" % (subject, lengths))

    phases = [row["phase"] for row in rows]
    transitions = [i for i in range(1, n_beats) if phases[i] != phases[i - 1]]
    if transitions != [first_recovery]:
        raise BuildError("subject %d: expected one phase transition, got %r"
                         % (subject, transitions))
    n_exercise = first_recovery
    n_recovery = n_beats - first_recovery
    log("  phase: %d exercise / %d recovery, first recovery beat %d at t=%.3f s"
        % (n_exercise, n_recovery, first_recovery, columns["t"][first_recovery]))

    report = quality_report(rows, n_samples)

    # --- quantisation deltas, for the page footnote ----------------------
    qt_deltas = []
    tamp_deltas = []
    for index in range(n_beats):
        qt = columns["qt"][index]
        qrson, t_peak, t_off = columns["qrsOn"][index], columns["tPeak"][index], columns["tOff"][index]
        if qt is not None and qrson is not None and t_off is not None:
            qt_deltas.append((t_off - qrson) * 10.0 - qt)
        tamp = columns["tamp"][index]
        if tamp is not None and t_peak is not None:
            tamp_deltas.append(abs(ecg[t_peak] - tamp))
    tamp_deltas.sort()
    log("  QT(from index) - qt_ms: %+.0f..%+.0f ms   |ecg[tPeak]-tamp_mv|: median %.4f, max %.4f mV"
        % (min(qt_deltas), max(qt_deltas),
           tamp_deltas[len(tamp_deltas) // 2], tamp_deltas[-1]))

    raw_rr = [v for v in columns["rr"] if v is not None]
    raw_qt = [v for v in columns["qt"] if v is not None]
    raw_tamp = [v for v in columns["tamp"] if v is not None]

    meta = {
        "subject": subject,
        "fs": FS,
        "ecgScale": ECG_SCALE,
        "durationS": DURATION_S,
        "nSamples": n_samples,
        "nBeats": n_beats,
        "peakTimeS": PEAK_TIME_S,
        "firstRecoveryBeatIndex": first_recovery,
        "firstRecoveryBeatTimeS": columns["t"][first_recovery],
        "nExercise": n_exercise,
        "nRecovery": n_recovery,
        "ecgMin": min(ecg),
        "ecgMax": max(ecg),
        "maxLandmarkSpanSamples": report["maxLandmarkSpanSamples"],
        "scanBoundSamples": MAX_LANDMARK_SPAN,
        "axisSmooth": {
            "rr": axis_range(columns["rrS"]),
            "qt": axis_range(columns["qtS"]),
            "tamp": axis_range(columns["tampS"]),
        },
        "axisAll": {
            "rr": axis_range(columns["rrS"] + raw_rr),
            "qt": axis_range(columns["qtS"] + raw_qt),
            "tamp": axis_range(columns["tampS"] + raw_tamp),
        },
        "quantisation": {
            "qtFromIndexMinusQtMsMs": [min(qt_deltas), max(qt_deltas)],
            "tampAbsDiffMedianMv": round(tamp_deltas[len(tamp_deltas) // 2], 5),
            "tampAbsDiffMaxMv": round(tamp_deltas[-1], 5),
        },
        # Short, notable lists ship to the browser for the data-quality note.
        # The bulk lists (hundreds of beats) stay in the development report.
        "annotationQuality": {
            "incompleteLandmarks": report["incompleteLandmarks"],
            "strictReversals": report["strictReversals"],
            "reversalsWithFiniteQt": report["reversalsWithFiniteQt"],
            "ties": report["ties"],
            "tiesWithFiniteQt": report["tiesWithFiniteQt"],
            "missingQtCount": len(report["missingQt"]),
            "missingTampCount": len(report["missingTamp"]),
            "suppressedTampLabelCount": len(report["suppressedTampLabelOnValidT"]),
        },
    }

    beats = {"n": n_beats,
             "firstRecoveryBeatIndex": first_recovery,
             "peakTimeS": PEAK_TIME_S}
    for name in ("t", "rIdx", "qrsOn", "tPeak", "tOff",
                 "rr", "qt", "tamp", "rrS", "qtS", "tampS"):
        beats[name] = columns[name]
    write_json(os.path.join(subject_dir, "beats.json"), beats)

    return meta, report


def write_json(path, payload):
    """Deterministic JSON: fixed separators, no trailing newline drift, LF."""
    text = json.dumps(payload, separators=(",", ":"), sort_keys=False,
                      allow_nan=False, ensure_ascii=True)
    with open(path, "w") as handle:
        handle.write(text)
        handle.write("\n")


def digest(root):
    """Stable hash over every generated file, for the determinism check."""
    sha = hashlib.sha256()
    for directory, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            path = os.path.join(directory, name)
            sha.update(os.path.relpath(path, root).encode("utf-8"))
            with open(path, "rb") as handle:
                sha.update(handle.read())
    return sha.hexdigest()


def build(out_dir, log):
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    subjects = []
    reports = {}
    for subject in SUBJECTS:
        meta, report = build_subject(subject, out_dir, log)
        subjects.append(meta)
        reports[subject] = report
    write_json(os.path.join(out_dir, "meta.json"),
               {"project": "qt-rr-dynamics",
                "source": "MIMS2 exercise test, de-identified, peak HR +/- 10 min",
                "smoothing": "41-beat centred moving mean (movmean [20,20]), applied upstream",
                "phaseColors": {"exercise": [217, 83, 25], "recovery": [0, 114, 189]},
                "subjects": subjects})
    return reports


def brief(beats, limit=12):
    if not beats:
        return "none"
    if len(beats) <= limit:
        return "%d %s" % (len(beats), beats)
    return "%d %s ..." % (len(beats), beats[:limit])


def summarise(reports, log):
    log("")
    log("annotation-quality summary (reported, never dropped)")
    for subject in SUBJECTS:
        report = reports[subject]
        log("  subject %d" % subject)
        log("    incomplete landmarks   : %s" % brief(report["incompleteLandmarks"]))
        log("    strict T reversals     : %s" % brief(report["strictReversals"]))
        log("      of those, finite qt  : %s" % brief(report["reversalsWithFiniteQt"]))
        log("    ties (tPeak == tOff)   : %s" % brief(report["ties"]))
        log("      of those, finite qt  : %s" % brief(report["tiesWithFiniteQt"]))
        log("    missing qt_ms          : %d beats" % len(report["missingQt"]))
        log("    missing tamp_mv        : %d beats" % len(report["missingTamp"]))
        log("    valid T but no tamp    : %s" % brief(report["suppressedTampLabelOnValidT"]))
        log("    max QRSon->Toff span   : %d samples" % report["maxLandmarkSpanSamples"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="verify the committed payload matches a fresh build")
    args = parser.parse_args()

    lines = []

    def log(message):
        lines.append(message)
        print(message)

    try:
        if args.check:
            temporary = tempfile.mkdtemp(prefix="qtrr-check-")
            try:
                build(temporary, log)
                fresh, committed = digest(temporary), digest(OUT)
                log("")
                log("fresh build     : %s" % fresh)
                log("committed build : %s" % committed)
                if fresh != committed:
                    log("MISMATCH: committed payload is stale")
                    return 1
                log("OK: committed payload is byte-identical to a fresh build")
            finally:
                shutil.rmtree(temporary, ignore_errors=True)
            return 0

        reports = build(OUT, log)
        summarise(reports, log)

        # Determinism: rebuild into a temporary tree and compare hashes.
        temporary = tempfile.mkdtemp(prefix="qtrr-determinism-")
        try:
            build(temporary, lambda message: None)
            if digest(temporary) != digest(OUT):
                log("ERROR: build is not deterministic")
                return 1
            log("")
            log("determinism check: identical on rebuild (%s)" % digest(OUT)[:16])
        finally:
            shutil.rmtree(temporary, ignore_errors=True)

        for subject in SUBJECTS:
            directory = os.path.join(OUT, "subject_%d" % subject)
            for name in ("beats.json", "ecg_int16.bin"):
                path = os.path.join(directory, name)
                log("  %-34s %7.1f KB" % (os.path.relpath(path, REPO),
                                          os.path.getsize(path) / 1024.0))
        log("  %-34s %7.1f KB" % (os.path.relpath(os.path.join(OUT, "meta.json"), REPO),
                                  os.path.getsize(os.path.join(OUT, "meta.json")) / 1024.0))
    except BuildError as error:
        print("BUILD FAILED: %s" % error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
