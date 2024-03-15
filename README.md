# Shopify Tracker

## How to set up

Clone this repository, for example to user's `$HOME`

```shell
$ git clone https://github.com/longthp/shopify-tracker /home/$USER/shopify-tracker
$ cd /home/$USER/shopify-tracker
```

### Installing venv with dependencies

```shell
$ python3 -m venv venv

$ venv/bin/python3 -m pip install -e .
```

### Populate SQLite database files

```shell
$ venv/bin/python3 migrate.py
```

this will load the previously ran data files into `data/sqlite/*.db`.

## Run trackers

There's a CLI at `venv/bin/st-runner.py`, run `venv/bin/st-runner --help` for more options:

```shell
$ venv/bin/st-runner --help
usage: st-runner [-h] [--list-trackers] [--run-all] [--run-from RUN_FROM] [--run RUN] [--test TEST]

optional arguments:
  -h, --help            show this help message and exit
  --list-trackers, --list, -l
                        list all pre-configured trackers
  --run-all             run all trackers in configured order
  --run-from RUN_FROM   run from <tracker_id> upto the last tracker in the list
  --run RUN             run tracker by id. use `--list-trackers` for a list of available trackers
  --test TEST, -t TEST  override SQLITE_DB_ROOT with specified path
```

### Test run

```shell
$ mkdir -p /tmp/foo
$ venv/bin/st-runner --run 1 --test /tmp/foo
```

### Schedule trackers using `cron`

```shell
# edit crontab for current user
$ crontab -u $USER -e

# add cron command(s)
# e.g. run at 09:00 AM everyday
0 9 * * * cd </path/to/cloned/repo> && venv/bin/st-runner --run-all 2>&1 | logger -t shopify

```

### Some PATH(s) to look out for

- logs files are located at two places
  - `logs/tracker.log.jsonl` (json-line file, see `src/logger.py` for formatting)
  - `grep "shopify" /var/log/syslog` (redirected from `cron` command, used for checking error messages)

- sqlite db files are located at `data/sqlite`


## Setup front-end interfaces

### Google Sheets

To use Google Sheets as front-end, setup the following requirements:

1. `src/config/creds.json`
- this is the credential file for Google Service Account
- follow these steps from [gspread's guide](https://docs.gspread.org/en/latest/oauth2.html#for-bots-using-service-account)
- copy and paste JSON credentials into `src/config/creds.json`

2. `src/config/sheets.json`
- this is used for defining spreadsheets (i.e. which spreadsheet should have which trackers)
- for example, to setup 02 separate outputting sheets, each sheet has 02 trackers:
  - first, create 02 Google Sheets with desired names
  - second, populate `src/config/sheets.json` with the following contents:
  ```json
  {
      "spreadsheets": [
          {
              "key_id": "19qbejOYgTCmwDNOLa5b5W6VLXtWSR38-AgxbQW0i0Ow",
              "tracker_urls": [
                  "https://776bc.com",
                  "https://budgysmuggler.com.au",
              ]
          },
          {
              "key_id": "1dyfIRuIuBBqyulafWy2_eMLAg98EbwewNTdaemKgq30",
              "tracker_urls": [
                  "https://www.twinsix.com/",
                  "https://hyperfly.com/",
              ]
          }
      ]
  }
  ```

then there's also a CLI script at `src/sheet.py` used for populating the configured sheets.

We can also setup this script as another `cron`, by editing the `crontab`:

```shell
$ crontab -u $USER -e

# this should run at every 60 minutes
0 * * * * cd </path/to/cloned/repo> && venv/bin/st-sheet --run-all 2>&1 | logger -t shopify-sheets
```

### Dash Web Application

```shell
$ venv/bin/python3 -m src.app.main
```

then open `http://127.0.0.1:8050` in a web-browser on the same network.
