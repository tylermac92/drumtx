# 0003 — Components and licenses

- **Status:** Accepted, 2026-10-30
- **Task:** M0-2

Decision 0001 makes DrumTx a personal, non-commercial, undistributed tool. So non-commercial (NC) and share-alike (SA) terms are acceptable: share-alike only applies when something is shared. Each item below is checked for terms beyond that: research-only clauses, registration, and no-redistribution or no-modification clauses. Items with unclear terms are excluded. Licenses were checked on 2026-10-30 at the sources linked at the end.

## Components

| Component | Kind | License and terms | Flags | Verdict |
|---|---|---|---|---|
| ADTOF pretrained models | Detection model | CC BY-NC-SA 4.0 (whole repository, including trained models) | — | **Allowed** |
| ADTOF-pytorch (third-party port) | Detection model | No license declared | Unclear terms | Excluded |
| Omnizart drum checkpoints | Detection model | Code MIT; no license stated for the checkpoints | Unclear terms | Excluded |
| Self-trained CRNN | Detection model | Our code; the training data's terms apply (E-GMD, CC BY 4.0) | — | **Allowed** |
| Classical baseline | Detection | Our code | — | **Allowed** |
| Beat This! | Beat and downbeat tracker | Code and weights MIT | Authors note that some training audio is copyrighted or under limited CC licenses | **Allowed** |
| madmom | Beat and downbeat tracker | Code BSD; model files CC BY-NC-SA 4.0 | — | **Allowed** |
| librosa | Beat tracker, features | ISC | — | **Allowed** |
| Demucs (v4.1.0) | Separation model | Code MIT. The README says "the license of the weights is not clear"; trained on MUSDB (academic use only) plus internal Meta data | Unclear terms; research-only training data | Excluded |
| Open-Unmix `umxl` | Separation model | Code MIT; weights CC BY-NC-SA 4.0 | — | **Allowed** |
| Open-Unmix `umxhq` | Separation model | Code MIT; weights MIT | Trained on MUSDB18-HQ (academic use only) | **Allowed** |
| Spleeter | Separation model | MIT | Requires Python < 3.12 and TensorFlow (technical, not license) | Excluded |
| E-GMD | Dataset | CC BY 4.0 | — | **Allowed** |
| Groove MIDI Dataset | Dataset (MIDI) | CC BY 4.0 | — | **Allowed** |
| MDB Drums | Dataset | CC BY-NC-SA 4.0 (audio from MedleyDB) | — | **Allowed** |
| IDMT-SMT-Drums | Dataset | CC BY-NC-ND 4.0, "provided for evaluation purpose" | Evaluation only; no derivatives | **Allowed for evaluation only**; not used for training |
| ENST-Drums | Dataset | Signed user licence: "personal use of the Licensee only and solely for scientific purposes" | Research-only; registration (signed agreement) | Excluded |
| ADTOF datasets | Dataset | On request via Zenodo, stating academic affiliation and intended use; "internal non-commercial use"; "Do not redistribute, modify, or disassemble" | Registration; no-redistribution; no-modification | Excluded |
| MUSDB18 / MUSDB18-HQ | Dataset | "Can only be used for academic purposes" | Research-only | Excluded (not needed directly) |
| Drum sounds synthesized in code | Drum samples | Our code | — | **Allowed** |
| Third-party sample kits (for example Big Rusty Drums or Gogodze Phu Vol II, listed as CC0 by the SFZ Instruments index) | Drum samples | Only an index lists the license; not confirmed at the source | Unclear terms | Excluded until checked at the source |

## Recommendations

- **Detection (M0-4).** M0-4 compares three options:
  - the classical baseline;
  - the ADTOF pretrained model, with its weights converted to ONNX locally (ADTOF-pytorch is not used);
  - a CRNN trained on E-GMD.
- **Evaluation data (M0-3).** E-GMD and MDB Drums, IDMT-SMT-Drums for evaluation only, and your own recordings. The Groove MIDI Dataset supplies patterns for synthetic fixtures.
- **Beat tracking (M0-5).** M0-5 compares Beat This! and madmom. librosa is the fallback; it has no downbeats.
- **Separation (M2-6).** Open-Unmix `umxl` in the `[separation]` extra, with `umxhq` as the fallback. This replaces Demucs in the Technical Design Document §6.
- **Drum samples (M1-5, M6).** Drum sounds are synthesized in code for test fixtures and for `drumtx preview`. They are deterministic on every operating system, need no download, and can be committed. No third-party samples are bundled.

## Where third-party files live

Nothing third-party is committed to the repository.

- **Model weights** live in the per-user cache directory, under `drumtx/models`. The model registry (M2-5) records each model's license. The same directory holds locally converted and self-trained weights.
  - Linux: `~/.cache/drumtx/models`
  - macOS: `~/Library/Caches/drumtx/models`
  - Windows: `%LOCALAPPDATA%\drumtx\Cache\models`
- **Datasets** live outside the repository in `~/drumtx-data/<dataset>/`, keeping the original archives. Scripts and the benchmark runner take the path as an argument.

## Consequences

- **librosa and Python 3.11.** librosa 1.0.0 (August 2026) requires Python 3.12 or newer; 0.11.0 is the last release that supports 3.11. If M0-4 adopts librosa, it either pins `librosa<1.0` or raises the Python floor (decision 0002).
- **madmom installs from git.** Its last PyPI release (0.16.1, 2018) does not support current Python versions, so it would be installed from git. M0-5 checks whether that is workable on all three operating systems.
- **Revisiting this decision.** If the project is ever shared, every NC, SA, and evaluation-only item above must be revisited, as decision 0001 says.

## Sources

- madmom code and model files: <https://github.com/CPJKU/madmom/blob/main/LICENSE>
- madmom models repository: <https://github.com/CPJKU/madmom_models>
- Beat This! (license section of the README): <https://github.com/CPJKU/beat_this>
- ADTOF repository and models: <https://github.com/MZehren/ADTOF>
- ADTOF datasets: <https://zenodo.org/records/10084510>
- ADTOF-pytorch port: <https://github.com/xavriley/ADTOF-pytorch>
- Omnizart: <https://github.com/Music-and-Culture-Technology-Lab/omnizart>
- Demucs (license section of the README): <https://github.com/adefossez/demucs>
- Open-Unmix (README): <https://github.com/sigsep/open-unmix-pytorch>
- Open-Unmix `umxl` weights: <https://zenodo.org/records/5069601>
- Open-Unmix `umxhq` weights: <https://zenodo.org/records/3370489>
- Spleeter (PyPI `requires_python`): <https://github.com/deezer/spleeter>
- librosa: <https://github.com/librosa/librosa>
- E-GMD: <https://magenta.tensorflow.org/datasets/e-gmd>
- Groove MIDI Dataset: <https://magenta.tensorflow.org/datasets/groove>
- MDB Drums: <https://github.com/CarlSouthall/MDBDrums>
- IDMT-SMT-Drums: <https://www.idmt.fraunhofer.de/en/publications/datasets/drums.html>
- ENST-Drums licence: <http://perso.telecom-paristech.fr/~grichard/ENST-drums/ENST_Drums_License.pdf>
- MUSDB18: <https://sigsep.github.io/datasets/musdb.html>
- SFZ Instruments drum index: <https://sfzinstruments.github.io/drums>
