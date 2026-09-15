# Plan v2 — Interactive QT–RR Dynamics page (CinC 2026, Abstract #257)

Status: **IMPLEMENTED on branch `feat/projects-qtrr` — built and verified locally, not committed, not pushed, not deployed.**
See §12 for what changed during implementation and §13 for verification results.
Date: 2026-09-15 (v2, supersedes v1 of the same date)
Incorporates: your review of v1, the updated beat CSVs with QRS-onset / T-peak / T-end columns, and `mims2_tamp_exercise_scatter.m` as the styling reference (§2.1)
Target URL: `https://sajjadkarimi.com/projects/qt-rr-dynamics/` · QR alias `https://sajjadkarimi.com/qtrr/`

Awaiting your approval of this preview before anything is committed, pushed or deployed.

---

## 0. Data re-verification (updated CSVs, re-read 2026-09-15)

Every claim in your review was re-derived from the files. All of it reproduces exactly.

**New landmark columns confirmed** in both beat files:
`beat_idx, r_sample_100hz, qrson_sample_100hz, tpeak_sample_100hz, toff_sample_100hz, t_s, t_rel_peak_s, phase, rr_ms, qt_ms, tamp_mv, rr_ms_smooth, qt_ms_smooth, tamp_mv_smooth`

| check | subject 1 (1925 beats) | subject 2 (1394 beats) |
|---|---|---|
| incomplete-landmark beats | **2** — beat 44 (qrsOn/tPeak/tOff null, qt null), beat 1924 (tPeak/tOff null, **qt_ms = 404 finite**) | **1** — beat 1377 (qrsOn/tPeak/tOff null, qt null) |
| strict reversals `tPeak > tOff` | **5** — 475, 483, 510, 771, 965 | **0** |
| reversals retaining finite `qt_ms` | **4** — 475, 483, 771, 965 (**483 has null `tamp_mv`**) | — |
| ties `tPeak == tOff` | **2** — 537 (qt = 348, finite), 874 (qt null) | **0** |
| total out-of-order (incl. ties) | **7** | 0 |
| other order violations (`qrsOn ≤ R < tPeak`, `qrsOn < tOff`) | 0 | 0 |
| finite landmarks integral & in `[0, 120001)` | ✅ all | ✅ all |
| `rr_ms_smooth` / `qt_ms_smooth` / `tamp_mv_smooth` NaNs | **0** | **0** |
| `rr_ms`, `t_s` NaNs | 0 | 0 |
| ECG grid | uniform, `t_s == idx/100` and `t_rel_peak_s == idx/100 − 600` for all 120 001 rows | same |
| `\|t_s − rIdx/100\|` max | 0.0040 s | 0.0040 s |
| beat-to-beat gap | 0.306 – 1.270 s | 0.562 – 1.448 s |
| max `tOff − qrsOn` span | 46 samples (460 ms) | 51 samples (510 ms) |
| ECG amplitude range | −1.794 … 2.319 mV | −2.111 … **5.688** mV |
| first recovery beat | index **924**, `t_s = 600.428` (previous beat exactly `600.000`) | index **782**, `t_s = 600.596` (previous `600.000`) |

**Quantization, measured:**
- `(tOff − qrsOn) × 10 ms` vs `qt_ms`: median **0 ms**, range **−8 … +8 ms** (both subjects). So reconstructed QT ≠ `qt_ms`.
- `|ecg_mv[tPeak] − tamp_mv|`: S1 median 0.065 mV / max 0.313 mV; S2 median 0.027 mV / max 0.461 mV; **0 exact matches out of 1776 / 1342**. So the trace sample at T-peak ≠ `tamp_mv`.
- int16 @ 0.001 mV/LSB round-trip: max error exactly **0.5000 µV** (the half-LSB bound).

**Strip files** now share the global index (`rest` = rows 500–1499, `peak` = rows 59 500–60 499), as the updated README states. They stay in `data/` for reference but are not part of the web payload — the page fetches the full trace and slices it.

Two consequences that drive the design:
1. **`qt_ms` finite is not a sufficient condition for drawing T annotations.** Subject 1 beat 1924 has `qt_ms = 404` with null `tPeak`/`tOff`. The README's "skip beats whose `qt_ms` is NaN" rule alone would try to index null.
2. **`qt_ms` NaN is not a necessary condition for bad ordering either.** Beats 475/483/771/965 are strictly reversed *with* finite `qt_ms`. The validity test must be conjunctive over landmarks **and** ordering **and** `qt_ms`.

---

## 1. Site & GitHub Pages constraints (verified)

- academicpages Jekyll, built by **classic GitHub Pages from `master`** (the only workflow is `scrape_talks.yml`). Custom domain `sajjadkarimi.com` via `CNAME`.
- **Nothing in this plan needs a plugin that isn't already whitelisted.** `jekyll-redirect-from` is in both `plugins:` and `whitelist:`, so the `/qtrr/` alias is safe on Pages. No new gems, no build action, no submodules.
- Generated data must be **committed** — Pages runs no build step of ours.
- **No server config on Pages**: no custom headers, no `Content-Encoding`, no `.htaccess`. Text types (`.json`, `.css`, `.js`, `.html`) are served gzipped by the CDN; `application/octet-stream` is not. Size estimates in §5 reflect that honestly.
- `_layouts/default.html` wraps everything in `compress.html`. The collapse step rejoins on spaces; newlines survive, so inline JS would *probably* be fine — but **the page will contain zero inline `<script>` and zero inline `<style>`** anyway. All CSS/JS lives in external files under `assets/`, which sidesteps the question entirely.
- Directories beginning with `_` or `.` are not published. `assets/projects/...` publishes normally; binary files pass through untouched. The generated JSON contains no `{{` or `{%`, so Liquid will not touch it.
- Pages limits: 1 GB published site, 100 MB per file. Our whole addition is well under 1 MB.

**Local toolchain, checked:** system Ruby is **2.6.10** with Bundler 1.17.2, no `Gemfile.lock`, and Docker is **not installed**. Current `github-pages` releases require Ruby ≥ 2.7, so `bundle install` against system Ruby is expected to fail. Python is **3.6.8** with no numpy/pandas/qrcode. This shapes §8 (local preview) and means the build script must be **pure stdlib and Python 3.6-compatible**.

---

## 2. Template & colour preservation

The page inherits your template — it does not introduce a second visual language.

- New layout `_layouts/project-app.html` **extends `default`**, so masthead, greedy nav, theme toggle, footer, SEO and `main.css` are unchanged and untouched. It only omits the sidebar/author profile and the `.page` max-width, giving the app a wider content column.
- **No edits to `_sass/`, `assets/css/main.scss`, `_includes/masthead.html`, or any existing layout.** One new stylesheet, `assets/projects/qt-rr-dynamics/css/app.css`, scoped under `.qtrr-app`.
- All chrome (backgrounds, panel borders, text, axes, gridlines, captions, buttons) is drawn from the existing custom properties — `--global-bg-color`, `--global-text-color`, `--global-text-color-light`, `--global-border-color`, `--global-link-color`, `--global-fig-caption-color`, `--global-footer-bg-color` — read at draw time via `getComputedStyle`, so light and dark are automatically correct and stay correct if you ever retheme.
- Typography inherits `$sans-serif` from the template; canvas labels use the same stack. No web fonts added.
- The **only** new colours are the two phase hues your README and poster already specify: exercise `rgb(217,83,25)`, recovery `rgb(0,114,189)`. These are data encodings, kept identical in both themes so screenshots match the poster. In dark mode they get a lightness lift only if measured contrast against `--global-bg-color` (#474747) falls below 3:1; hue is preserved either way. The moving point and playhead use `--global-link-color` (#52adc8 light / #0ea1c5 dark), so the interactive accent is your site's accent.
- A `MutationObserver` on `html[data-theme]` triggers a full redraw, so your existing sun/moon toggle recolours the plots live.

### 2.1 MATLAB reference (`mims2_tamp_exercise_scatter.m`) — the styling source of truth

You supplied the original plotting script; the web panels reproduce its visual language. What I took from it, and the three places I deliberately deviate:

| MATLAB | web page |
|---|---|
| `exercise_color = [0.8500 0.3250 0.0980]` | `rgb(217,83,25)` — **identical** (also matches the README) |
| `recovery_color = [0.0000 0.4470 0.7410]` | `rgb(0,114,189)` — **identical** |
| `movmean(rr,[20,20])`, `movmean(target,[20,20])` for the scatter axes | the supplied `rr_ms_smooth` / `qt_ms_smooth` / `tamp_mv_smooth` columns — the same 41-beat centred mean, precomputed |
| `xlabel('RR (ms)')`, `ylabel('QT (ms)')` / `ylabel('T-amp (mV)')`, `'FontWeight','bold'` | **same strings, bold** (v1 invented "RR interval" / "T-wave amplitude" — corrected) |
| `grid on`, `FontSize 12` | light grid in `--global-border-color`, 12 px template sans |
| legend `exercise (RR↓, 10 min)` / `recovery (RR↑, 10 min)` | same wording |
| scatter figure `8 × 4 in` | hysteresis panels target **2:1** aspect |
| time-series: target 2 tiles over RR 1 tile, `linkaxes` on x | ECG / hysteresis / RR stack shares one time domain by construction (§4.3) |
| RR trace `'-'`, `[0.35 0.35 0.35]`, `LineWidth 0.8` | same grey, 1 px |
| `xline(t_peak,'--',exercise_color,'LineWidth',1.3)` | peak marker dashed in **exercise orange**, not a neutral dash |
| raw layer: `scatter(rr, target, 16, …, 'MarkerFaceAlpha', 0.05)` | **excluded by default**, per your instruction — available behind "Display options" |
| smoothed layer: `scatter(rr_mm, target_mm, 22, …, 'MarkerFaceAlpha', 0.9)` | drawn as a **1.5 px polyline** by default (deviation — see below), with a "dots" mode that reproduces the MATLAB marker rendering |
| `scatter_ylim = [340 500]` (QT), `[-0.1 0.5]` (T-amp) | **not used** — data-driven per-subject ranges (deviation — see below) |

**Deviation 1 — raw scatter off by default.** Your instruction. 1925 + 1394 translucent markers redrawn behind a 60 fps playhead is the single heaviest thing on the page, and at `MarkerFaceAlpha 0.05` it contributes texture rather than information. It stays available as a toggle; when enabled it is baked into the same cached offscreen background as the loop, so it costs nothing per frame.

**Deviation 2 — polyline instead of markers for the smoothed loop.** The smoothed beats are time-ordered, so connecting them is the same geometry with fewer draw calls and a cleaner line — "smooth and light", as you asked. The MATLAB dot rendering is one toggle away for figure parity.

**Deviation 3 — the MATLAB fixed y-limits would clip this data, so they are not used.** Measured: `scatter_ylim = [340 500]` clips **subject 1's QT** (`qt_ms_smooth` reaches **286.9 ms**), and `[-0.1 0.5]` clips **subject 2's T-amp** (`tamp_mv_smooth` reaches **0.706 mV**). Fixed limits are right for a poster panel built from one cohort view; they are wrong for a page that switches subjects. Axis ranges are therefore per subject from the data with 4 % padding (§6), consistent with the no-silent-clipping rule in §5.1. A "poster axes" toggle can pin `[340 500]` / `[-0.1 0.5]` for screenshot parity, and when pinned it shows the same explicit out-of-range indicators as the ECG panel rather than quietly cropping.

---

## 3. Folder convention & routing

```
data/mims2-qtrr/                       # raw source, in git, EXCLUDED from the Jekyll build
  README.md  index.csv
  subject_{1,2}_beats.csv
  subject_{1,2}_ecg_100hz.csv
  subject_{1,2}_meta.csv
  strips/subject_{1,2}_ecg_strip_{rest,peak}.csv

scripts/projects/build_qtrr_data.py    # CSV -> web payload (stdlib only, py3.6-safe)

assets/projects/qt-rr-dynamics/
  css/app.css
  js/{app,clock,data,sync,overlays,panel-ecg,panel-hysteresis,panel-timeline}.js
  data/meta.json
  data/subject_1/{beats.json, ecg_int16.bin}
  data/subject_2/{beats.json, ecg_int16.bin}
  dev.html                             # static preview harness (see §8); excluded from build

_projects/qt-rr-dynamics.md            # the page (front matter + intro prose)
_pages/projects.html                   # the /projects/ hub
_layouts/project-app.html
images/projects/qt-rr-dynamics-{card.png,qr.svg}
```

`_config.yml`: add a `projects` collection (`output: true`, `permalink: /projects/:path/`) and a matching `defaults` entry (`layout: project-app`, `author_profile: false`); add `data`, `scripts` and `assets/projects/qt-rr-dynamics/dev.html` to `exclude:`. Add `.DS_Store` to `.gitignore`. Nav gains `- title: "Projects" / url: /projects/` before "Portfolio"; `_portfolio` is not touched.

| URL | source |
|---|---|
| `/projects/` | `_pages/projects.html` — card grid over `site.projects` sorted by `order` |
| `/projects/qt-rr-dynamics/` | `_projects/qt-rr-dynamics.md` |
| `/qtrr/` | `redirect_from` on the same doc |

**Convention for project #2 onward:** `data/<slug>/` (source, unbuilt) → `scripts/projects/build_<slug>_data.py` → `assets/projects/<slug>/` (payload) → `_projects/<slug>.md` (route + copy). Nothing project-specific in the site root.

---

## 4. Time, synchronization and interpolation

### 4.1 Time model

- `peakTimeS = 600` **by definition** — `t_rel_peak_s == t_s − 600` holds for all 120 001 ECG rows in both subjects. This is the annotation anchor and the dashed marker on the timeline.
- `firstRecoveryBeatIndex` is **separate**: 924 (S1) / 782 (S2), at `t_s = 600.428` / `600.596`. The last exercise beat sits at exactly `600.000` in both. Phase shading on the timeline switches at the *beat* boundary; the "Peak HR" marker sits at 600 s. They differ by 0.4–0.6 s and the plan does not conflate them.
- `phase(i) = i < firstRecoveryBeatIndex ? 'exercise' : 'recovery'` — verified to reproduce the `phase` column exactly (single transition, no interleaving), so `phase` is not stored per beat. This is exactly the MATLAB rule `ex_mask = t <= t_peak`, `rc_mask = t > t_peak`: checked beat-by-beat, `phase == 'exercise'` ⟺ `t_s <= 600` with **0 violations in either subject**, and the counts reproduce `index.csv` (924/1001 and 782/612).
- **No peak detection, no re-smoothing, no re-filtering in the browser.** The MATLAB pipeline already did bad-beat removal, the QT-based quality filters, the two-step robust outlier filter, the RR de-spike-and-fill, the `movmean(·,[20,20])` smoothing, and the peak-HR windowing. The export *is* the ±10 min window about the peak. The page reads the supplied columns and does nothing to them but interpolate between beats for display (§4.2).
- Beat timing uses **`t_s` from the file** (never `rIdx/100`, which differs by up to 4 ms). Sample indices are used **only** for positioning into the ECG array. The two are never mixed.
- Window is peak ±10 min, so `t = 0` is already mid-ramp (RR ≈ 824 ms ≈ 73 bpm for S1; 1079 ms ≈ 56 bpm for S2). **The page will not label the window start "Rest".** Annotations are limited to "Exercise (HR rising)", "Peak HR", "Recovery (HR falling)", plus a note that the export begins 10 min before peak. (v1 planned poster-style "Rest" labels; removed — unsupported by this data.)

### 4.2 One shared beat-selection / interpolation rule

Used identically by the RR handle, **both** hysteresis points, and every readout. Defined once in `sync.js`, called once per frame, returning a single `state` object that all panels consume — so they cannot drift apart.

```
Given playback time t (s):
  i = largest index with beats.t[i] <= t        (binary search, monotonic hint -> O(1) typical)
  Boundaries:
    t <  beats.t[0]   -> i = 0,   j = 0,   u = 0,  atStart = true
    t >= beats.t[n-1] -> i = n-1, j = n-1, u = 0,  atEnd   = true
    otherwise         -> j = i+1, u = (t - t[i]) / (t[j] - t[i]),  u in [0,1)
  Smoothed (always finite): v = v[i] + u*(v[j] - v[i])   -- linear interpolation
      drives: RR handle y, QT-RR point (rrS, qtS), T-amp-RR point (rrS, tampS)
  Raw (may be null):  NEVER interpolated.
      nearestBeat = (u < 0.5) ? i : j
      readout shows beats.rr/qt/tamp[nearestBeat], or "—" if null. Never coerced to 0.
  phase = phase(i)
```

Interpolating the smoothed series matters: beat gaps are 0.31–1.45 s, which at 10× is 31–145 ms of wall time — visibly steppy without it. Every interpolated readout is labelled: the hysteresis panels show **"smoothed (41-beat centred mean), interpolated between beats"** in their caption, and raw readouts are labelled **"beat #N, raw"**. The 41-beat centred moving mean is explained once in the methods note, including that it is centred (uses future beats) and therefore not causal — it is a smoothing of the whole record, not a real-time filter.

**Moving point:** a single bright dot (site accent, 6 px, with a soft halo) is the primary element, as you asked. An optional **time-based** trail — default **off**, default length 8 s of data time when enabled — traces the interpolated path behind it. Time-based, not beat-count-based, so its visual length is the same at 55 bpm and 140 bpm. (v1's "last 40 beats comet" is replaced.)

### 4.3 Synchronization contract

**One authoritative clock.** `tPlay ∈ [0, 1200]`, advanced by a single `requestAnimationFrame` loop: `tPlay += (now − last)/1000 × rate`, `rate` default **10×** (options 1 / 5 / 10 / 20). The RR handle and both hysteresis points are recomputed from `tPlay` every frame — they are always mutually exact.

**The ECG is separately timestamped.** It holds a 5-second snapshot `[tSnap − 5, tSnap]`, where `tSnap` is the playback time at which it was latched. Re-latch happens on **wall-clock** cadence: when `performance.now() − lastLatchWall ≥ latchIntervalMs` (default **3000 ms**), independent of `rate`.

> **Acknowledged lag.** At 10× with a 3 s latch, `tPlay − tSnap` grows from 0 to **nearly 30 data seconds** between refreshes, and the snapshot covers 5 s out of every 30 s of record — a deliberate stroboscopic sample, because a 100 Hz trace is unreadable when swept at 10×. The page states this in plain words next to the ECG, shows a live `ECG: −12.4 s behind` readout, and draws the snapshot's **time-range bracket on the timeline** so you can always see which slice is on screen relative to the playhead.

Event behaviour, specified:

| event | ECG | clock |
|---|---|---|
| **seek** (timeline click, keyboard step, "copy link" restore) | immediate re-latch, `tSnap = tPlay` | `tPlay` set; `playing` unchanged |
| **drag** (pointer down → move → up) | follows continuously, re-latched on pointer move throttled to ~20 Hz; the 3 s hold does **not** apply while dragging | paused for the duration; on release resumes iff it was playing before the drag |
| **subject change** | immediate re-latch after the new data is live (atomic swap, §6) | `tPlay` preserved (both records are 1200 s) |
| **replay / restart** | immediate re-latch at `tPlay = 0` | `tPlay = 0`, `playing = true` |
| **loop wrap** (reaching 1200 with loop on) | immediate re-latch at 0 | `tPlay` wraps to 0; default `loop = on` |
| **endpoint, loop off** | immediate re-latch at 1200 | `tPlay` clamps to 1200, `playing = false`, replay button shown |
| **pause** | frozen, no further latching | rAF loop stops; no time advance |
| **resume** | immediate re-latch | loop restarts from the current `tPlay` |
| **tab hidden** (`visibilitychange`) | frozen | rAF cancelled; **no time accrues** while hidden (no jump on return) |
| **tab visible again** | immediate re-latch | resumes from the same `tPlay` iff it was playing |
| **`prefers-reduced-motion`** | static snapshot at `tPlay` | autoplay does not start; all scrubbing still works |

**Window clamping at the edges:** for `tSnap < 5` the snapshot shows `[0, 5]` rather than a short window (ECG exists from 0); at the end, `tSnap = 1200` gives `[1195, 1200]`. The bracket reflects the actual displayed span in both cases. Snapshot length (3 / 5 / 10 s) and latch interval (2 / 3 / 5 s) are exposed as secondary controls so you can tune after seeing it; defaults are 5 s and 3 s.

---

## 5. Panels

Four canvases (2D, `devicePixelRatio`-aware, `ResizeObserver`-driven), no plotting library — a library would add 1–3 MB for four fixed panel types and fight a 60 fps playhead. Panel order top → bottom: **ECG**, **QT–RR**, **T-amp–RR**, **RR-vs-time**.

### 5.1 ECG snapshot (top)

5 s of trace, refreshed per §4.3. R-peak ticks always shown (they are the beat markers).

**Y-scaling — no silent clipping.** Default is **fixed full-range per subject**, computed at build time from the file min/max plus 5 % padding (S1 −1.794…2.319, S2 −2.111…5.688 mV). Clipping is impossible by construction; the scale never changes between latches, so morphology is comparable across the record. Because S2's R-peak reaches 5.7 mV while T-amp is 0.3–0.7 mV, a **"Fit T-wave"** toggle offers a robust zoom (p1–p99 of the visible window). While that zoom is active, any sample beyond the axis is marked explicitly: hatched chevrons on the exceeded edge, a capped R-peak stub, and a persistent `clipped: R-peak 5.69 mV` chip. One click returns to full range. Default is full range, so the honest view is the one you get without doing anything.

### 5.2 Optional ECG overlays — "Show measurements" (default off)

Toggle draws QRS-onset, R-peak, T-peak and T-end markers plus subtle QT shading. Marker heights are `ecg_mv[index]` (never a fixed y). **QT shading spans QRS-onset → T-end**, never R → R + QT.

**Per-beat validity predicate** (`overlays.js`), with `N = 120001`:

```js
const idxOK = v => Number.isInteger(v) && v >= 0 && v < N;   // null fails, never coerced
const hasQrsOn = idxOK(qrsOn), hasR = idxOK(rIdx),
      hasTpk   = idxOK(tPeak), hasToff = idxOK(tOff);
const qtOK    = Number.isFinite(qt);
const orderOK = hasQrsOn && hasR && hasTpk && hasToff &&
                qrsOn <= rIdx && rIdx < tPeak && tPeak <= tOff && qrsOn < tOff;
const isTie   = orderOK && tPeak === tOff;

showQrsOn      = hasQrsOn;                         // independently valid
showR          = hasR;                             // independently valid
showT          = qtOK && orderOK;                  // T-peak + T-end markers
showQtShading  = qtOK && orderOK;                  // QRS-onset -> T-end band
showTampLabel  = showT && Number.isFinite(tamp);   // amplitude annotation only
```

Rules this encodes, each one explicit:
- Missing CSV values become **JSON `null`**; `null` never becomes 0 and is never used as an index.
- R-peak and QRS-onset markers stand on their own when T landmarks are absent.
- T markers *and* QT shading are suppressed when `qt_ms` is missing, **or** any required landmark is missing, **or** the order is invalid — all three conditions, conjunctively.
- `tPeak === tOff` is accepted as a 100 Hz rounding tie and drawn as **one combined diamond glyph** labelled "T-peak = T-end", visually distinct from the normal two-marker case.
- Strict reversal `tPeak > tOff` → **suppress** that beat's T markers, T-amp label and QT shading. Source values are never reordered, repaired, swapped or clamped.
- `tamp_mv` missing → suppress the amplitude annotation only; the T-peak marker itself may still show if `showT` holds.

**Expected behaviour on this exact data** (asserted by the build script and listed on the page's data-quality note):

| beat | condition | result |
|---|---|---|
| S1 #44 | all three landmarks null, `qt` null | R marker only |
| S1 #1924 | `tPeak`/`tOff` null but **`qt_ms = 404` finite** | QRS-onset + R only; T markers & shading suppressed |
| S1 #475, #771, #965 | `tPeak > tOff`, `qt` finite, `tamp` finite | QRS-onset + R only |
| S1 #483 | `tPeak > tOff`, `qt` finite, **`tamp` null** | QRS-onset + R only |
| S1 #510, #874 | `qt` null (#874 also a tie) | QRS-onset + R only |
| S1 #537 | tie `tPeak == tOff == 41854`, `qt = 348` | full overlay, **combined T glyph** |
| S2 #1377 | all three null, `qt` null | R marker only |
| S2, all others | clean | full overlay |

**Window clipping.** Overlays are clipped to the visible span `[s0, s1]` in sample units. A beat is considered if its `[qrsOn, tOff]` **intersects** the window, even when its R-peak is outside it — so a QT band entering from the left or leaving on the right is drawn as a band that runs to the panel edge and stops, with no fabricated endpoint and a small inward-pointing cue that it continues off-window. Scan bounds: start from the last beat with `tOff ≥ s0`, stop at the first with `qrsOn > s1`; the lookback bound is 100 samples (1.0 s), safely above the measured maxima of 46 / 51 samples, and the build script asserts `max(tOff − qrsOn) < 100`.

**Labels come from the source columns, never from the drawing.** The readout shows `qt_ms` and `tamp_mv` verbatim. It does **not** show `(tOff − qrsOn) × 10` (measured to differ from `qt_ms` by up to ±8 ms) and does **not** show `ecg_mv[tPeak]` (median |Δ| 0.065 mV S1 / 0.027 mV S2, max 0.461 mV, zero exact matches). A footnote states that the shading is a positional depiction on a 10 ms grid while the number beside it is the source measurement. Raw per-beat ECG annotations are visually and textually distinct from the smoothed hysteresis values — different typographic treatment, and each readout carries its own "raw, beat #N" or "smoothed, interpolated" tag.

**Hysteresis is never affected by ECG-annotation suppression.** Panels 2 and 3 use `*_smooth`, finite for all 1925/1394 beats. A beat whose ECG overlay is suppressed still contributes its smoothed point.

### 5.3 QT–RR and T-amp–RR hysteresis (middle)

- **Background, drawn once per subject to an offscreen canvas and blitted each frame:** the full smoothed loop — `rrS` on x, `qtS` / `tampS` on y — as a 1.5 px polyline coloured by phase (exercise `rgb(217,83,25)`, recovery `rgb(0,114,189)`) at ~20 % alpha, split at `firstRecoveryBeatIndex` into two coloured runs. Optional raw scatter (`rr` vs `qt` / `tamp`, `Number.isFinite`-guarded) at ~8 % alpha, **off by default** per your instruction, baked into the same cached background when enabled so it costs nothing per frame. Optional "dots" mode reproduces the MATLAB `scatter(..., 22, ..., 0.9)` marker rendering.
- **Foreground, per frame:** the single bright interpolated point (+ optional trail, §4.2), plus a corner readout `RR 612 ms · QT 371 ms (smoothed)`.
- Axis labels exactly as in the MATLAB script — `RR (ms)` on x, `QT (ms)` / `T-amp (mV)` on y, bold, 12 px — with `grid on` rendered as a light grid in `--global-border-color`. Panels target a **2:1** aspect, matching the 8 × 4 in figure.
- Axis ranges precomputed **per subject** in `meta.json` with 4 % padding (not the MATLAB fixed limits — see §2.1, deviation 3). Direction arrows on the exercise and recovery limbs and a "Peak HR" tick; **no "Rest" label** (§4.1).
- Smooth rendering: `lineJoin/lineCap = 'round'`, halo behind the moving point, and the point's position eased only by interpolation — no extra animation lag.

### 5.4 RR vs time (bottom) — the scrubber

- x = **time in minutes**, 0–20, ticks every 2 min; toggle to −10…+10 "min from peak HR". y label `RR (ms)`, bold, `grid on` — matching the MATLAB context figure, whose x axis was in seconds; minutes is your request and the only change.
- Traces: raw `rr` as a 1 px line in `[0.35 0.35 0.35]` grey (the MATLAB `LineWidth 0.8` trace), with `rrS` over it in the phase colours. Exercise/recovery regions lightly tinted; **dashed vertical at `peakTimeS = 600` in exercise orange** (`xline(t_peak,'--',exercise_color,'LineWidth',1.3)`), labelled "Peak HR".
- **Interaction:** click to seek; drag the handle (a filled dot riding the smoothed curve) to scrub either direction. Pointer Events, so mouse, trackpad and touch share one path. `setPointerCapture` so a drag that leaves the canvas still tracks. Drag pauses, release restores prior play state.
- The ECG snapshot's span is drawn here as a translucent bracket, and the gap between bracket and playhead is the visible form of the lag in §4.3.
- Keyboard (panel is focusable, `role="slider"`, `aria-valuemin/max/now/text`): `Space` play/pause · `←/→` ±5 s · `Shift+←/→` ±30 s · `Home/End` · `,`/`.` speed down/up · `1`/`2` subject · `M` measurements · `L` loop.

### 5.5 Controls, layout, mobile

- **Primary bar** (play/pause, speed, elapsed `mm:ss / 20:00`, loop, subject segmented control) sits directly under the panel stack in a **sticky footer bar on phones**, so it is always reachable without scrolling; on desktop it is inline under the timeline. Touch targets ≥ 44 px.
- **Secondary controls** — raw scatter, trail on/off + length, snapshot length, latch interval, axis mode, "Fit T-wave" — live in a collapsed `<details>` "Display options", closed by default. The four requested plots stay dominant.
- Breakpoints: ≥ 900 px → the two hysteresis panels side by side; below → single column, panels stack in the order above. Canvas heights clamp via `min(vh-based, px)` so all four remain visible on a laptop without scrolling, and the phone layout is verified by measurement, not assumption (§9).
- Loading states: skeleton panels with a spinner; error state with a **Retry** button and the failing URL; a stale-response guard (§6) so a slow first fetch cannot overwrite a newer subject.

---

## 6. Data pipeline (`scripts/projects/build_qtrr_data.py`)

Pure stdlib, **Python 3.6-compatible** (no walrus, no f-string `=`), run manually, output committed. Deterministic: fixed key order, fixed float formatting, `sort_keys` off but explicit ordering, LF endings, no timestamps or paths embedded in the output — re-running on unchanged input is byte-identical, and the script verifies this by hashing before/after.

**`ecg_int16.bin`** — little-endian `int16`, scale **0.001 mV/LSB**. Range ±32.767 mV covers the 5.688 mV maximum with large margin. 120 001 samples = **234 KB** per subject. No timestamps stored; the grid is exactly uniform (asserted for every row), so the client reconstructs `t = i/100`. `.bin` extension for a predictable `application/octet-stream`.

**`beats.json`** — struct-of-arrays, **including all four landmark arrays**, `null` preserved for every missing value:

```json
{ "n": 1925, "firstRecoveryBeatIndex": 924, "peakTimeS": 600,
  "t":     [...],                       // s, 3 dp, from t_s
  "rIdx":  [...], "qrsOn": [...],       // int or null
  "tPeak": [...], "tOff":  [...],       // int or null
  "rr":    [...], "qt":    [...], "tamp":  [...],    // raw; null where NaN
  "rrS":   [...], "qtS":   [...], "tampS": [...] }   // smoothed; never null
```

**Measured payload sizes** (prototype built and weighed, not estimated):

| | beats.json raw | beats.json gzipped | ecg_int16.bin |
|---|---|---|---|
| subject 1 | 131 KB | **51 KB** | 234 KB |
| subject 2 | 96 KB | **39 KB** | 234 KB |

Over the wire: JSON is gzipped by the Pages CDN; the `.bin` is not (§1). **First load ≈ 285 KB** (one subject); the second subject adds ≈ 273 KB only when selected. `meta.json` is ~1 KB. *(Optionally the `.bin` could ship pre-gzipped and be inflated with `DecompressionStream`, saving ~70 KB — noted, not planned, default off: it adds a code path for a modest win.)*

**`meta.json`** — per subject: `fs: 100`, `ecgScale: 0.001`, `durationS: 1200`, `nSamples: 120001`, `nBeats`, `firstRecoveryBeatIndex`, `peakTimeS: 600`, `rrAtPeakMs`, `ecgMin/ecgMax` (full-range ECG axis), `maxLandmarkSpanSamples`, and the annotation-exclusion summary from the validations below.

Axis ranges are stored **twice** per subject, both with 4 % padding: `axisSmooth` (covering `rrS`/`qtS`/`tampS` only — the default view) and `axisAll` (covering raw ∪ smoothed). Turning the raw scatter on switches the panel to `axisAll`, because raw values fall well outside the smoothed envelope — measured S1 QT raw 258–454 vs smoothed 287–426, S2 T-amp raw 0.117–0.903 vs smoothed 0.304–0.706 — and cropping them silently would break the same rule as §5.1. Measured smoothed ranges, for reference: S1 `RR 426–889 · QT 287–426 · T-amp −0.067–0.483`; S2 `RR 596–1215 · QT 349–483 · T-amp 0.304–0.706`.

**Build-time validations** (each prints a line; a failure aborts the build):

1. ECG row count == 120001; `sample_idx` contiguous from 0; `t_s == idx/100` and `t_rel_peak_s == idx/100 − 600` within 1e-9 / 1e-6 for **every** row (uniform sample spacing).
2. int16 round-trip error **≤ 0.5 µV + 1e-9** floating-point tolerance. *(Corrected from v1's strict `< 0.5 µV`; the measured maximum is exactly 0.5000 µV, the half-LSB bound.)*
3. All beat arrays have identical length `n`; `t` strictly increasing; `t ∈ [0, 1200]`; `|t − rIdx/100| ≤ 0.01 s`.
4. Every finite landmark is integral and within `[0, nSamples)`; every non-finite one serialises as `null`.
5. `rrS`, `qtS`, `tampS` finite for all beats; `rr` and `t` finite for all beats.
6. Exactly one `exercise → recovery` transition; `phase(i) = i < firstRecoveryBeatIndex` reproduces the CSV column exactly, **and** `phase == 'exercise'` ⟺ `t_s <= 600` (the MATLAB `ex_mask`/`rc_mask` rule) with zero violations; beat counts match `index.csv`; report the first recovery beat's `t_s`.
7. `max(tOff − qrsOn) < 100` samples (the overlay lookback bound).
8. **Annotation-quality report, not rejection** — counts and beat indices for: incomplete landmarks, strict reversals, ties, reversals with finite `qt_ms`, suppressed-`tamp` cases. Expected output is the table in §0/§5.2; a mismatch is a loud warning, not a crash, so refreshed CSVs are caught but still build. Records are never dropped — a beat with unusable ECG annotations keeps its smoothed hysteresis point.
9. Quantization deltas reported (`(tOff−qrsOn)*10 − qt_ms` range; `|ecg[tPeak] − tamp|` percentiles) so the page footnote's numbers stay sourced.

**README:** moved with the data to `data/mims2-qtrr/README.md`, with the path references and the strip-file paths updated for the new location, and a "Web build" section pointing at the script and the generated payload. Source content is otherwise unchanged.

---

## 7. Acceptance checks

Run against the local build before anything is pushed. Each is pass/fail, checked by hand or by a small console assertion.

**Playback & time**
1. At 10×, the full 1200 s record completes in 120 s ± 2 s; at 1× / 5× / 20× the elapsed readout tracks proportionally.
2. ECG re-latches every 3.0 s ± 0.2 s of wall time during autoplay, **regardless of speed**; the displayed `ECG behind` value grows 0 → ~30 s at 10× and 0 → ~5 s at 1×, then resets.
3. Seeking forward and backward while **playing** re-latches the ECG immediately, and the RR handle + both hysteresis points land on the same time.
4. Seeking while **paused** re-latches immediately and nothing advances afterwards.
5. `t = 0` and `t = 1200` endpoints: no NaN, no blank panels; clamped readouts; snapshot shows `[0,5]` and `[1195,1200]`.
6. Loop on → wraps to 0 and re-latches, indefinitely. Loop off → stops at 1200, shows replay; replay restarts cleanly.
7. Pause/resume preserves `tPlay` exactly; resume re-latches.
8. Tab hidden for 60 s → on return, `tPlay` has **not** advanced, ECG re-latches, playback resumes only if it was playing.
9. `prefers-reduced-motion: reduce` → no autoplay, scrubbing fully functional.

**Data, overlays, correctness**
10. S1 beat 44 and S2 beat 1377: R marker only; no exception, nothing drawn at y = 0.
11. S1 beat 1924: `qt_ms` finite but T landmarks null → **no** T markers, **no** QT shading, QRS-onset + R present.
12. S1 beats 475, 483, 771, 965 (reversed, finite `qt_ms`): T annotations and QT shading suppressed; source arrays unmodified (verify in console that `tPeak > tOff` still holds).
13. S1 beat 483: additionally no T-amp label (null `tamp_mv`).
14. S1 beat 537 (tie): full overlay with the combined T-peak/T-end glyph, visually distinct.
15. S1 beats 510, 874: suppressed via null `qt_ms`.
16. A QT band crossing the left and the right window edge renders clipped to the panel with no fabricated endpoint; a beat whose R-peak is outside the window but whose QT interval overlaps it **is** drawn.
17. Readout QT equals the CSV `qt_ms` for a spot-checked beat, and differs from `(tOff − qrsOn) × 10` where the CSV does; T-amp readout equals `tamp_mv`, not `ecg_mv[tPeak]`.
18. Every hysteresis point is finite for all 1925 / 1394 beats, including beats whose ECG overlays are suppressed.
19. RR handle y, both hysteresis x-coordinates, and the RR readout agree to display precision at arbitrary paused times, including exactly on a beat, between beats, and before the first / after the last beat.

**Subject switching & loading**
20. Rapid alternation (1→2→1→2 within a second) leaves **all four panels plus axes, readouts and annotation-quality note on one subject** — the swap is atomic: new data is fully parsed and validated into a candidate object, and only then assigned in a single step with one redraw.
21. A slow or out-of-order fetch cannot win: each request carries a monotonically increasing token, and a response whose token is not the newest is discarded.
22. Loading skeleton appears for a cold fetch; a forced failure (devtools offline) shows the error state; **Retry** recovers without reloading the page.
23. `tPlay` is preserved across a subject switch, and the ECG re-latches after the swap.

**Presentation**
24. Theme toggle (sun/moon) redraws all four canvases with template colours; no hard-coded hex survives in either theme except the two phase hues.
25. Window resize and device-pixel-ratio change redraw crisply (no blur, no stale offscreen background).
26. Default ECG scaling never clips: the full-range axis contains the file min/max for both subjects. With "Fit T-wave" on, clipping indicators appear and the clipped magnitude is stated.
26a. **MATLAB parity.** With "dots" mode and the raw scatter both enabled, each hysteresis panel is visually comparable to `<id>_exercise_scatter_<biomarker>.png` — same two colours, same axis labels, same grid, same 2:1 aspect. Colours sampled from the canvas equal `rgb(217,83,25)` / `rgb(0,114,189)` exactly.
26b. **No silent cropping from axes.** Default (`axisSmooth`) contains every smoothed point for both subjects; enabling the raw scatter switches to `axisAll` and every raw point is inside it. If the optional "poster axes" toggle is used, subject 1's QT (min 286.9 ms) and subject 2's T-amp (max 0.706 mV) fall outside `[340,500]` / `[-0.1,0.5]` and must raise visible out-of-range indicators, not disappear.
27. Phone layout (390×844 and 360×740): all four panels reachable, primary controls visible without scrolling past the plots, touch drag scrubs the timeline, no horizontal page scroll.
28. Desktop (1440×900): all four panels visible together without scrolling.
29. Keyboard: every control in §5.4 works; focus is visible; the timeline announces `aria-valuetext` as `mm:ss, exercise/recovery`.
30. Lighthouse-style sanity: no console errors, no 404s, page interactive well under 2 s on the local server.

---

## 8. Local preview (before anything goes public)

Nothing is pushed until you have seen it. Two layers, because the toolchain check found obstacles:

**Layer 1 — static harness, works today.** The app is entirely client-side, so `assets/projects/qt-rr-dynamics/dev.html` loads the same CSS, JS and data over `python3 -m http.server 8000` from the repo root → `http://localhost:8000/assets/projects/qt-rr-dynamics/dev.html`. This exercises all four panels, every interaction and every acceptance check in §7 except the Jekyll chrome. `dev.html` is added to `_config.yml`'s `exclude:` so it never publishes. (`file://` will not work — `fetch` of the `.bin` requires a server.)

**Layer 2 — full Jekyll preview.** Needed to verify the layout, hub, routes, redirect and theme integration. Obstacle: system Ruby is **2.6.10**, current `github-pages` needs ≥ 2.7, and Docker is not installed. Options in order of cost:

1. Try `bundle install` with system Ruby — cheap to attempt, expected to fail on `github-pages`.
2. Install Ruby 3.x (`brew install ruby` or rbenv) and `bundle install` — reliable, but installs toolchain on your machine, so **I will not do this without your explicit OK**.
3. Install Docker Desktop and `docker compose up` — the repo's `Dockerfile` already pins `ruby:3.2`.

Plan of record: build and iterate on Layer 1, attempt option 1 once, and ask you before touching option 2 or 3. Work happens on branch `feat/projects-qtrr`; **no commit to `master`, no push, no deploy without your go-ahead.**

**QR code:** neither `qrcode` nor `segno` is installed and there is no numpy/PIL. I will generate `images/projects/qt-rr-dynamics-qr.svg` offline via a throwaway `pip install --user segno` (not added to the repo, nothing committed but the SVG), or hand you the URL to generate it yourself — your call, and it is the last step either way.

---

## 9. Implementation order

1. Restructure + `_config.yml` collection/excludes + `.gitignore`. Site still builds; no visible change.
2. `build_qtrr_data.py` → payload + validation report (§6). Review the report with you.
3. Routing skeleton: `project-app` layout, `/projects/` hub, `_projects/qt-rr-dynamics.md`, nav entry, placeholder content.
4. `clock.js` + `sync.js` + timeline panel — the scrubber. **Stop here and show you**, since everything else is built on this feel.
5. Both hysteresis panels.
6. ECG panel with the latch contract.
7. Overlays + validity predicate + data-quality note.
8. Polish: theme sync, responsive/mobile, keyboard/ARIA, URL state, loading/error, intro copy.
9. Acceptance checks §7, desktop + phone.
10. QR + `redirect_from`. Then, and only then, ask you about committing.

---

## 10. Resolved inconsistencies from v1

| # | v1 said | v2 says | why |
|---|---|---|---|
| 1 | QT shading `R → R + qt_ms` | **QRS-onset → T-end**, from the new columns | anatomically correct; landmarks now exist |
| 2 | "skip where `qt_ms` is NaN" | conjunctive predicate over landmarks **and** order **and** `qt_ms` | S1 #1924 has finite `qt_ms` with null T landmarks; #475/483/771/965 are reversed with finite `qt_ms` |
| 3 | comet of "last ~40 beats" | bright point primary; optional **time-based** trail, default off | beat-count trails change visual length with HR |
| 4 | poster-style "Rest" annotation | removed | window starts mid-ramp (73 / 56 bpm); no evidence of rest |
| 5 | peak ≈ phase switch | `peakTimeS = 600` **separate from** `firstRecoveryBeatIndex` (924 / 782 at 600.428 / 600.596 s) | they differ by 0.4–0.6 s |
| 6 | lazy load **and** idle prefetch | **lazy only**, with stale-response tokens | v1 contradicted itself; prefetch doubles mobile data |
| 7 | ECG y-axis at p0.5/p99.5 | **full range by default**; robust zoom is opt-in with explicit clip indicators | p0.5/p99.5 would silently clip exactly 1.00 % of samples |
| 8 | tolerance `< 0.5 µV` | **`≤ 0.5 µV + 1e-9`** | measured max is exactly 0.5000 µV |
| 9 | "links to the poster PDF and the paper" | **PENDING** — see §11 | neither is in the repo; `_publications/` has no CinC 2026 entry and `files/` holds only template PDFs |
| 10 | strip CSVs "redundant" | still out of the web payload, retained under `data/mims2-qtrr/strips/` | they now share the global `sample_idx`; useful reference, not needed at runtime |
| 11 | sizes without landmarks | measured: beats.json 131→51 KB gz (S1), 96→39 KB gz (S2); ~285 KB first load | four new arrays added |
| 12 | `ecg.i16` | `ecg_int16.bin` | predictable MIME on Pages |
| 13 | interpolation unspecified | one shared rule in `sync.js` (§4.2), boundaries included | prevents panel drift |
| 14 | URL state vague | `?subject=1\|2` + `?t=<seconds, 1 dp>`; strict validation; written on pause, drag-end, or the explicit "Copy link to this moment" button — **never during playback** | no history spam, no rAF-rate URL writes |
| 15 | no GitHub-Pages section | §1 | you asked for nothing inconsistent with GitHub |
| 16 | axis labels "RR interval / QT interval / T-wave amplitude" | **`RR (ms)` / `QT (ms)` / `T-amp (mV)`**, bold, `grid on` | matches `mims2_tamp_exercise_scatter.m` and the poster |
| 17 | peak marked with a neutral dashed line | dashed in **exercise orange**, RR trace in `[0.35 0.35 0.35]` | matches the MATLAB `xline` and context figure |
| 18 | raw scatter "default off" as a performance guess | **off by design**, on your instruction; cached into the offscreen background when on | it is the heaviest element on the page |
| 19 | axis ranges unspecified beyond "4 % padding" | `axisSmooth` **and** `axisAll`; MATLAB's fixed `[340,500]` / `[-0.1,0.5]` rejected | those limits clip S1 QT (287 ms) and S2 T-amp (0.706 mV) |
| 20 | — | added: **no peak detection, no re-filtering, no re-smoothing** client-side | the export is already the ±10 min peak window; MATLAB did the cleaning |

**URL parameter validation, stated:** `subject` must be exactly `"1"` or `"2"`, otherwise it falls back to 1 silently. `t` is parsed with `Number()`, must be finite, and is clamped to `[0, 1200]`; anything else falls back to 0. Time is in **seconds** (one decimal) in the URL even though the timeline axis is labelled in minutes — seconds keeps the parameter unambiguous and matches `t_s`; the UI never shows a raw seconds figure without its `mm:ss` equivalent.

Minor preferences taken as defaults without asking: loop **on**; speed **10×**; trail **off**; raw scatter **off**; measurements overlay **off**; snapshot **5 s**; latch **3 s**; timeline axis **minutes from window start** (toggle to minutes-from-peak); subject **1**; hysteresis side-by-side ≥ 900 px.

---

## 11. Blocking questions (only these)

**B1 — Poster / paper sources.** Neither the CinC 2026 poster PDF nor a paper is in the repo: `files/` contains only the template's `paper1-3.pdf` / `slides1-3.pdf`, and `_publications/` has no 2026 entry. I can draft the intro copy from the poster content in our conversation, but any **link, embed, citation or "as in the poster" annotation is marked PENDING** until you add the file. Do you want to (a) add the poster PDF to `files/` now, (b) ship with no poster link and add it later, or (c) hold the intro copy entirely until the paper is public?

**B2 — Local full-preview toolchain.** Layer 1 (static harness) works today and needs nothing from you. For Layer 2 (Jekyll chrome, routes, redirect) system Ruby 2.6.10 is too old and Docker is absent. May I install Ruby 3.x via Homebrew/rbenv on your machine, should I install Docker Desktop instead, or do you want to run the Jekyll server yourself and have me verify against it?

Everything else has a stated default and needs no answer. **I will not create, move, generate, commit or deploy anything until you approve.**

---

## 12. What changed during implementation

Deviations from plan v2, each with the reason.

| # | plan v2 said | shipped | why |
|---|---|---|---|
| 1 | ECG default = **fixed full range**, with a "Fit T-wave" opt-in | **default = robust fit with explicit clipping indicators**; "Full-range ECG" is the opt-in | at full record range the T wave — the subject of the page — was a couple of pixels tall. Your review sanctioned either "fixed full-range scaling **or** explicit clipping indicators with a full-range option"; this is the second option. Clipping is still never silent: excursions are counted, marked with chevrons on the exceeded edge and named in a chip. |
| 2 | one stylesheet `qt-rr-dynamics/css/app.css` | split into `assets/projects/projects.css` (shell + hub cards) and `qt-rr-dynamics/css/app.css` (panels) | the hub uses the `archive` layout and so never loaded the app stylesheet; the cards rendered unstyled. |
| 3 | no shared includes touched | added an **opt-in** block to `_includes/head/custom.html`, guarded by `{% if page.projects_css %}` | that file is the theme's designated customisation hook and already carries site link tags. Nothing renders differently on any page that does not set the flag. |
| 4 | overlay scan from "the last beat with `tOff >= s0`" | **full scan of all beats** per ECG refresh, markers and bands checked independently | your review, and it is cheap: under 2000 beats, only on re-latch. |
| 5 | data lived in `webpage_mims2_public/` (untracked) | `git mv` to `data/mims2-qtrr/` | you had committed it in `a1e848e`, so the move preserves history. |
| 6 | Jekyll 4 / `github-pages` gem for local preview | **Jekyll 3.9.5** installed user-local (`gem install --user-install`) | system Ruby is 2.6.10 and modern gems require >= 2.7/3.0+. Jekyll 3.9 is also what GitHub Pages actually pins, so it is closer to the deployment target. No system Ruby change, no Docker. |
| 7 | — | `jemoji` and `jekyll-gist` could not be installed on Ruby 2.6 | the local build drops them from `plugins:` via a temporary config. Neither affects layout, routing, redirects or these pages; both remain in the committed `_config.yml` for the real Pages build. **This is the one part of the build that differs from production.** |

Bugs found and fixed while verifying (each was real, not cosmetic):

- **Theme race.** `watchTheme` was registered after the first `await`, so the site's own script setting `data-theme="dark"` during loading was missed and every panel drew with the light palette on a dark page. The observer is now registered before any await, and the palette is re-read at the atomic subject swap.
- **Serif axis labels.** The palette read `font-family` from `<html>`, which computes to **Times**; the template sets its typeface on `<body>`. Canvas labels now read the body font.
- **`?t=` was clobbered.** The first `selectSubject()` wrote the URL before `readTimeParam()` ran, so a shared link always opened at 00:00. The incoming time is now captured once, before any load.
- **`setPointerCapture` could abort a seek.** It throws for some pointer sources; it is now guarded so a failure cannot prevent scrubbing.
- **Clipped edge tick labels** and a **legend sitting on the data** — the last x-tick is now kept inside the panel and the hysteresis legend is placed in whichever corner the loop leaves emptiest.

## 13. Verification results

**Build:** full Jekyll build succeeds against the real `_config.yml`. Routes `/projects/`, `/projects/qt-rr-dynamics/` and the `/qtrr/` redirect all serve; asset URLs resolve to `https://sajjadkarimi.com/...` as the rest of the site does; `data/`, `plans/`, `scripts/` and `dev.html` are all absent from the output.

**Data pipeline:** all validations pass; output is byte-identical on rebuild (`--check` verifies the committed payload). Payload: `beats.json` 138.2 / 101.1 KB, `ecg_int16.bin` 234.4 KB each, `meta.json` 1.9 KB.

**56 automated checks, all passing**, driven through the Chrome DevTools Protocol against the real built site:

- *Playback and sync (21):* 10x rate accuracy; ECG re-latch every ~3.0 s at both 1x and 10x (wall-clock, not data-time); lag 3.0 s at 1x and 29.7 s at 10x; seeking forward/backward while playing and paused; no drift while paused; both endpoints; loop wrap; stop-at-end with loop off; keyboard stepping; rapid subject switching landing atomically on one subject; URL state and invalid-parameter fallback.
- *Data semantics (17):* every case from your review — S1 beats 44, 475, 483, 510, 537, 771, 874, 965, 1924 and S2 beat 1377 — plus the tie drawing one combined glyph, suppressed beats keeping finite smoothed values, no null ever reaching an index, bands crossing either window edge with true endpoints preserved, a beat contributing a band while its R-peak is outside the window, and confirmation that reconstructed QT differs from `qt_ms` (1539/1894 beats, max 8 ms).
- *Integration (18):* blocked-fetch error state with a working Retry and the URL kept to console diagnostics; hidden tab accruing no time; theme redraw; body-font check; resize; no horizontal scroll at 700 px or 390 px; sticky mobile controls with >= 44 px targets; touch drag; hub and nav; four existing pages still rendering; `/qtrr/` redirect.

**Not verified:** the live GitHub Pages build itself, and the two plugins that could not be installed locally (§12 row 7).
