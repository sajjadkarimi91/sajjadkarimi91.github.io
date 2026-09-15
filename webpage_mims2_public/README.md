# Exercise-test demo data (web-ready CSVs)

Two de-identified cardiac stress-test recordings, covering the **peak-heart-rate window
only** (peak HR ± 10 min = 20 min each). Subjects are referred to only as
**`subject_1`** and **`subject_2`**.

**Time is abstract.** `t_s` runs 0 → 1200 s from the start of the exported window, and
`t_rel_peak_s` runs −600 → +600 s around peak HR. There are no dates, clock times, or
recording offsets anywhere in these files.

## Files per subject

### `subject_N_ecg_100hz.csv` — ECG trace (~3.6 MB, 120 001 rows)
Baseline-corrected single-lead ECG, decimated 500 → 100 Hz with an FIR anti-alias
filter. Baseline correction = 60 Hz notch + median(0.3 s)/mean(0.15 s) cascade removal.

| column | meaning |
|---|---|
| `sample_idx` | 0-based row index (join key from the beats file) |
| `t_s` | seconds from the start of the window (0 … 1200) |
| `t_rel_peak_s` | seconds from peak HR; **negative = exercise, positive = recovery** |
| `ecg_mv` | ECG amplitude, mV |

Uniform 100 Hz grid, so `t_s = sample_idx / 100`.

### `subject_N_beats.csv` — per-beat biomarkers (1394–1925 rows)
One row per accepted beat in the window, already synced to the ECG file.

| column | meaning |
|---|---|
| `beat_idx` | 0-based beat counter |
| `r_sample_100hz` | **row index into the ECG file** — R-peak |
| `qrson_sample_100hz` | row index of QRS onset |
| `tpeak_sample_100hz` | row index of T-wave peak |
| `toff_sample_100hz` | row index of T-wave end |
| `t_s`, `t_rel_peak_s` | as above |
| `phase` | `exercise` (RR falling) or `recovery` (RR rising) |
| `rr_ms`, `qt_ms`, `tamp_mv` | per-beat RR, QT, T-wave amplitude (may be `NaN`) |
| `rr_ms_smooth`, `qt_ms_smooth`, `tamp_mv_smooth` | 41-beat centred moving mean — **use these for the hysteresis plots** |

### `subject_N_ecg_strip_rest.csv` / `_peak.csv` — 10 s excerpts (~28 KB)
Exact slices of the full ECG file, so `sample_idx` is the **same global row index** the
`*_sample_100hz` columns use — markers need no offset in the strips either
(`rest` = rows 500–1499, `peak` = rows 59 500–60 499). For showing real P-QRS-T morphology — the full 20 min
trace is an unreadable blob at any sensible screen width. `rest` is early in the
exercise ramp, `peak` is centred on peak HR.

### `subject_N_meta.csv` / `index.csv`
`subject`, `source`, `ecg_fs_hz`, `window_min`, `rr_at_peak_ms`, `n_beats`,
`n_ecg_samples`, `n_exercise`, `n_recovery`.

## Plotting notes

- **Hysteresis panels** (QT-RR, T-amp-RR): scatter `rr_ms_smooth` vs `qt_ms_smooth` /
  `tamp_mv_smooth`, coloured by `phase`. Suggested colours: exercise
  `rgb(217,83,25)`, recovery `rgb(0,114,189)`. Raw columns can go underneath at low
  alpha for texture.
- **NaNs are real.** `qt_ms` is NaN on ~2 % of beats and `tamp_mv` on ~4–8 % (quality and
  robust-outlier rejection). `rr_ms` has none — RR outliers are filled with the local
  moving mean/median rather than dropped. Guard with `Number.isFinite()`.
- **Drawing markers**: `ecg_mv[k]` for any `*_sample_100hz` value `k` gives the marker height.
  Fiducial indexes are `NaN` where the delineator gave no point or it falls outside the
  window (≤2 beats per subject, e.g. the T-wave of the final beat). For T-peak/T-end markers,
  skip beats whose `qt_ms` is `NaN` — those were rejected by quality checks and a few have
  mis-ordered points.
- **Indexes position, `*_ms` columns measure.** The 100 Hz grid quantises R-peak
  times to 10 ms, so RR from consecutive R indexes (or QT from T-end − QRS-on) differs from
  `rr_ms` / `qt_ms` by a median of 2–4 ms.
- **Size**: the ECG CSVs gzip to roughly a third. Serve them compressed, or load a strip
  first and fetch the full trace on demand.
