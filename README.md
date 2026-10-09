Faithful Word Baptist Sermon Downloader

A simple, cross-platform Python script for downloading and organizing MP3 sermons from the Faithful Word Baptist Church online archive.

Download sermons by individual month or an entire year. The script automatically retrieves sermon titles and speaker information from the website and creates consistently named files using the YYYYMMDD - Sermon Title.mp3 format. Guest speakers are appended to the filename, while Pastor Anderson’s sermons retain the simpler naming format.

Features include:

Download sermons by month (MMYYYY) or year (YYYY).
Automatically retrieve sermon titles and speaker names from the online archive.
Rename files into a consistent, date-based format.
Sanitize filenames for compatibility with Windows and Linux.
Skip existing files to help prevent accidental overwrites.
Preview the selected sermons and confirm before downloading.
Run on Windows or Linux using Python, without additional third-party packages.

Created to make building and maintaining a personal, searchable local sermon archive easier.

Website: http://thepreaching.com or https://www.faithfulwordbaptist.org/page5.html
## Usage

### Requirements

* Python 3.10 or newer
* An internet connection
* No third-party Python packages required

The script uses Python's standard library and works on both Linux and Windows.

### Running the Script

Open a terminal in the directory containing `fwb_sermons_by_month_or_year.py`.

**Linux:**

```bash
python3 fwb_sermons_by_month_or_year.py
```

**Windows (PowerShell or Command Prompt):**

```powershell
python fwb_sermons_by_month_or_year.py
```

### Selecting Sermons

The script prompts you to enter a month and year, or an entire year.

| Input    | Downloads                       |
| -------- | ------------------------------- |
| `112006` | November 2006                   |
| `012015` | January 2015                    |
| `2006`   | All available sermons from 2006 |
| `2015`   | All available sermons from 2015 |

Monthly selections use the `MMYYYY` format. Yearly selections use the four-digit `YYYY` format.

### File Naming

Downloaded MP3 files are automatically named using the sermon date and title:

```text
20061101 - Matthew 28.mp3
```

Guest preachers are identified in the archive and appended to the filename:

```text
20260802 - The Severity of Charity - Bro. Chris Segura.mp3
```

Pastor Anderson's name is omitted because he is the default speaker.

The script also removes characters that are invalid in filenames on Windows and Linux.

### Choosing a Download Directory

By default, files are saved in the current working directory.

To specify a destination directory, use the `--folder` option.

**Linux:**

```bash
python3 fwb_sermons_by_month_or_year.py --folder ~/Music/FWB-Sermons
```

**Windows:**

```powershell
python fwb_sermons_by_month_or_year.py --folder "C:\Users\YourName\Music\FWB-Sermons"
```

The destination directory is created automatically if it does not exist.

### Download Confirmation

Before downloading, the script displays the sermons it found and asks for confirmation.

```text
Download 42 MP3(s) to /home/user/Music/FWB-Sermons? [Y/n]:
```

Press **Enter** or type `Y` to proceed. Type `n` to cancel.

Existing files are skipped rather than overwritten, making it easier to download a year in multiple passes without replacing files you already have.

To skip the final confirmation prompt, use `--yes`:

```bash
python3 fwb_sermons_by_month_or_year.py --folder ~/Music/FWB-Sermons --yes
```

The script will still ask which month or year to download.

### Troubleshooting

* **No sermons found:** Verify the year or month you entered and make sure the online archive is accessible.
* **Download errors:** Check your internet connection and try again. Existing successful downloads will be skipped on the next run.
* **Python version:** Run `python3 --version` on Linux or `python --version` on Windows to check your installed version.

### Project Independence

This is an independent community utility and is not affiliated with, endorsed by, or maintained by Faithful Word Baptist Church.

**Sermon archive:** https://www.faithfulwordbaptist.org/page5.html
