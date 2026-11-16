"""Command line:  python -m floodml <command>"""
import argparse
import sys
from datetime import date, timedelta

from . import config


def _doctor(args):
    print("floodml self-check")
    for mod in ("pandas", "numpy", "sklearn", "joblib", "requests"):
        try:
            __import__(mod)
            print(f"  [ok]   package {mod}")
        except ImportError:
            print(f"  [FAIL] package {mod} is missing - run: pip install -r requirements.txt")
    print("  Checking NASA POWER (internet needed) ...")
    from .power_api import PowerError, build_plan
    try:
        build_plan(log=print)
        print("  [ok]   NASA POWER reachable")
    except PowerError as exc:
        print(f"  [FAIL] {exc}")
    n = len(list(config.POWER_DIR.glob("[0-9]*.csv")))
    print(f"  cached NASA files: {n} (expected 70)")
    from .mysql_export import MySQLUnavailable, connect_mysql
    try:
        db = connect_mysql()
        db.close()
        print("  [ok]   MySQL reachable (daily data can be exported)")
    except MySQLUnavailable as exc:
        print(f"  [info] MySQL not available: {exc}")
    print(f"  events file: {'ok' if config.EVENTS_CSV.exists() else 'MISSING'}")
    print(f"  dataset: {'ok' if config.DATASET_CSV.exists() else 'not built yet'}")
    print(f"  trained model: {'ok' if config.MODEL_PATH.exists() else 'not trained yet'}")


def _download(args):
    from .download import download_all
    start = date.fromisoformat(args.start) - timedelta(days=config.WARMUP_DAYS)
    end = date.fromisoformat(args.end) if args.end else date.today() - timedelta(days=1)
    download_all(start, end, workers=args.workers, force=args.force)


def _labels(args):
    from .labels import build_labels
    df = build_labels()
    print(f"{df['event_id'].nunique()} events -> {len(df)} flooded district-days "
          f"in {df['district'].nunique()} districts ({df['date'].min()} to {df['date'].max()})")
    print(df.groupby("confidence").size().to_string())


def _dataset(args):
    from .dataset import build_dataset
    df = build_dataset(start=args.start, end=args.until)
    print(f"Saved {config.DATASET_CSV}")
    print(f"{len(df):,} district-days | {df['district'].nunique()} districts | "
          f"{df['date'].min().date()} to {df['date'].max().date()}")
    print(f"Flood days: {int(df['flooded'].sum()):,} ({df['flooded'].mean():.2%}) | "
          f"recession-buffer days: {(df['label_status'] == 'recession_buffer').sum():,}")


def _export_mysql(args, only="all", recent_days=None, soft=False):
    """Export to MySQL. With soft=True a missing MySQL is only a warning (used after predict/all)."""
    from .mysql_export import MySQLUnavailable, run_export
    try:
        run_export(only=only, since=getattr(args, "since", None), recent_days=recent_days)
    except MySQLUnavailable as exc:
        if not soft:
            raise
        print(f"\nMySQL export skipped: {exc}\nRun  python -m floodml export-mysql  later when MySQL is running.")


def _analyze(args):
    from .analysis import run_analysis
    run_analysis()
    from . import config
    print(f"\nRead the findings: {config.OUT / 'flood_drivers.md'}")


def _train(args):
    from .train import run_training
    m = run_training(horizon=args.horizon)
    o = m["overall_out_of_fold"]
    print(f"\nModel PR-AUC {o['pr_auc']} vs simple rain rule {o['baseline_rain3d_pr_auc']}  |  "
          f"ROC-AUC {o['roc_auc']} vs {o['baseline_rain3d_roc_auc']}")
    print(f"Event hit rate {m['event_district_hit_rate']}, median lead {m['median_lead_days']} days, "
          f"false-alert days/district/year {m['false_alert_days_per_district_year']}")
    print(f"Read the full report: {config.REPORT_MD}")


def _predict(args):
    from .predict import run_predict
    out = run_predict(refresh=not args.no_refresh, workers=args.workers)
    print(out.head(10)[["rank", "district", "division", "risk_level", "probability", "rain_3d_mm"]].to_string(index=False))
    if getattr(args, "mysql", False):
        _export_mysql(args, recent_days=120, soft=True)


def _all(args):
    _download(args)
    _labels(args)
    _dataset(args)
    _analyze(args)
    _train(args)
    args.no_refresh = True
    mysql = args.mysql
    args.mysql = False
    _predict(args)
    if mysql:
        _export_mysql(args, soft=True)


def _export_cmd(args):
    _export_mysql(args, only=args.only, recent_days=args.recent_days)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="floodml", description="Bangladesh district flood-risk model (NASA POWER daily data)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, *, dates=False, horizon=False, workers=False):
        if dates:
            p.add_argument("--start", default=config.DEFAULT_START, help="first day of the study period")
            p.add_argument("--end", default=None, help="last day to download (default: yesterday)")
            p.add_argument("--until", default=config.LABELS_COMPLETE_UNTIL, help="last day with complete flood labels")
        if horizon:
            p.add_argument("--horizon", type=int, default=config.HORIZON_DAYS, help="warn for floods in the next N days")
        if workers:
            p.add_argument("--workers", type=int, default=4, help="parallel NASA requests (be polite: 4)")

    sub.add_parser("doctor", help="check packages, internet and data").set_defaults(fn=_doctor)
    p = sub.add_parser("download", help="download NASA POWER daily data (resumable)")
    common(p, dates=True, workers=True)
    p.add_argument("--force", action="store_true", help="re-download everything")
    p.set_defaults(fn=_download)
    sub.add_parser("labels", help="build flood-day labels from bd_flood_events.csv").set_defaults(fn=_labels)
    p = sub.add_parser("dataset", help="build the full training CSV")
    common(p, dates=True)
    p.set_defaults(fn=_dataset)
    sub.add_parser("analyze", help="what rainfall and environment did NASA see when floods began? (report)").set_defaults(fn=_analyze)
    p = sub.add_parser("train", help="train + validate the model, write the report")
    common(p, horizon=True)
    p.set_defaults(fn=_train)
    p = sub.add_parser("predict", help="score all 64 districts with the newest data")
    common(p, workers=True)
    p.add_argument("--no-refresh", action="store_true", help="do not download new data first")
    p.add_argument("--mysql", action="store_true", help="afterwards also export recent data + predictions to MySQL")
    p.set_defaults(fn=_predict)
    p = sub.add_parser("all", help="download -> labels -> dataset -> analyze -> train -> predict")
    common(p, dates=True, horizon=True, workers=True)
    p.add_argument("--force", action="store_true")
    p.add_argument("--mysql", action="store_true", help="afterwards also export everything to MySQL")
    p.set_defaults(fn=_all)

    p = sub.add_parser("export-mysql", help="write daily data, labels and predictions into MySQL (tables bd_*)")
    p.add_argument("--only", choices=["all", "daily", "labels", "predictions"], default="all")
    p.add_argument("--since", default=None, help="only daily rows from this date (YYYY-MM-DD)")
    p.add_argument("--recent-days", type=int, default=None, help="only the last N days of daily data")
    p.set_defaults(fn=_export_cmd)

    args = ap.parse_args(argv)
    try:
        args.fn(args)
    except (FileNotFoundError, ValueError) as exc:
        sys.exit(f"\nERROR: {exc}")
    except Exception as exc:                                  # noqa: BLE001
        from .mysql_export import MySQLUnavailable
        from .power_api import PowerError
        if isinstance(exc, MySQLUnavailable):
            sys.exit(f"\nMySQL problem: {exc}")
        if isinstance(exc, PowerError):
            sys.exit(f"\nNASA POWER problem: {exc}\nCheck your internet connection and run the command again "
                     "(downloads resume where they stopped).")
        raise


if __name__ == "__main__":
    main()
