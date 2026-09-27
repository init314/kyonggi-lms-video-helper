# Third-party notices

## study-ssalmeok

- Upstream: https://github.com/Sharon77770/study-ssalmeok
- Reference revision: `e79a9ff` (Create LICENSE)
- Copyright (c) 2026 주민재
- License: MIT; the original notice and license text are preserved verbatim in
  [licenses/study-ssalmeok-LICENSE.txt](licenses/study-ssalmeok-LICENSE.txt).

The original transcription, transcript cleaning, chunking, prompt generation,
GUI, domain models, tests, and packaging configuration were incorporated and
adapted from this project. Relevant files are under `src/`, `tests/`, and
`scripts/`, together with `StudySsalmeok.spec`, `build_exe.bat`, and
`pyproject.toml`.

The integrated version adds the LMS download pipeline, concurrent downloading
of the next lecture while transcription runs, virtual-monitor placement,
main-monitor controls, and cancellation. The LMS downloader was adapted from
this repository's existing `download_lms_video.py`.

This notice records the origin and license of the incorporated study-ssalmeok
code; it does not attribute the pre-existing LMS helper scripts to that project.
