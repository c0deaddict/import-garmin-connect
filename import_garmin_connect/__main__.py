import argparse
import traceback
import json
import logging

from influxdb import InfluxDBClient
from datetime import datetime, timedelta

from . import garmin


all_sources = [
    "summary",
    "activities",
    "sleep",
    "steps",
    "heartrate",
    "weight",
    "hydration",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", help="Garmin Connect username/email", required=True)
    parser.add_argument("--password", help="Garmin Connect password", required=True)
    parser.add_argument("--profile", help="Profile name", required=True)

    parser.add_argument("--influx-host", help="InfluxDB host", default="localhost")
    parser.add_argument("--influx-port", help="InfluxDB port", type=int, default=8086)
    parser.add_argument("--influx-db", help="InfluxDB database", default="garmin")

    parser.add_argument(
        "--date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
        help="Date to import (in format YYYY-MM-DD default: today)",
        default=None,
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of days to import, starting at given date",
    )
    parser.add_argument(
        "-s", "--source", action="append", help="Only import these sources"
    )
    parser.add_argument(
        "-t",
        "--test",
        action="store_true",
        help="Log measurements and do not write to InfluxDB.",
    )
    parser.add_argument("--log", default="INFO", help="Logging level")

    args = parser.parse_args()

    # https://docs.python.org/3/howto/logging.html
    numeric_level = getattr(logging, args.log.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError("Invalid log level: %s" % args.log)
    logging.basicConfig(level=numeric_level)

    if not args.test:
        influx = InfluxDBClient(host=args.influx_host, port=args.influx_port)
        influx.switch_database(args.influx_db)

    logging.info(f"Authenticating to Garmin as {args.user} ...")
    session = garmin.authenticate(args.user, args.password)
    display_name = garmin.find_display_name(session)
    logging.info(f"You have display_name: {display_name}")

    if args.date is None:
        start_date = datetime.now()
    else:
        start_date = args.date

    if args.source is None:
        sources = all_sources
    else:
        sources = [s for s in args.source if s in all_sources]

    tags = {"profile": args.profile}

    for date in (start_date + timedelta(n) for n in range(args.days)):
        for source in sources:
            try:
                logging.info(
                    f"Importing data about {source} on {date.strftime('%Y-%m-%d')}"
                )
                fetcher = getattr(garmin, "fetch_" + source)
                converter = getattr(garmin, "convert_" + source)
                data = fetcher(session, display_name, date)
                points = converter(date, data, tags)
                if not args.test:
                    influx.write_points(list(points))
                else:
                    for p in points:
                        logging.info(json.dumps(p))
            except:
                logging.error(f"Error importing from source {source}:")
                traceback.print_exc()


if __name__ == "__main__":
    main()
