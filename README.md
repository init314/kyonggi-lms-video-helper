# Kyonggi LMS Video Helper

Small Windows scripts for opening Kyonggi University's LMS and selecting course videos.
Login credentials are read from Windows Credential Manager through `keyring`; no password is stored in this repository.

## Setup

```powershell
py -m pip install -r requirements.txt
py -m playwright install chromium
```

Run `lms_login.py` once to save the LMS account in Windows Credential Manager. Then run the helper you need:

```powershell
py download_lms_video.py
py watch_lms_lecture.py
```

The downloader asks for a course name and week, then opens and saves that week's videos one at a time in LMS order. Downloaded files are written to `downloads/`, which is excluded from Git. Videos exposed as direct MP4/WebM files are supported; streaming-only formats may be reported as failures.
