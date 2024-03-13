# Shopify Tracker

## How to set up

Clone this repository, for example to user's $HOME

```shell
$ git clone https://github.com/longthp/shopify-tracker
```

### Installing venv with dependencies

```shell
$ python3 -m venv venv

$ venv/bin/python3 -m pip install -e .
```

### Populate SQLite database files

```shell
$ venv/bin/python3 run.py
```

## Run trackers

There's a CLI at `venv/bin/st-runner.py`, run `venv/bin/st-runner --help` for more options:

```shell
$ venv-test/bin/st-runner --help
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

### Schedule trackers using `cron`

```shell
# edit crontab for <username>
crontab -u <username> -e

# add cron command(s)
# e.g. run at 09:00 AM everyday
0 9 * * * cd </path/to/cloned/repo> && venv/bin/st-runner --run-all 2>&1 | logger -t shopify

```

### Some PATH(s) to look out for

- logs files are located at two places
  - `logs/tracker.log.jsonl` (json-line file, see `src/logger.py` for formatting)
  - `grep "shopify" /var/log/syslog` (redirected from `cron` command, used for checking error messages)

- sqlite db files are located at `data/sqlite`


## Launch the web interface

```shell
$ /venv/bin/python3 -m src.app.main
```

then open `http://127.0.0.1:8050` in web-browser on the same network.
