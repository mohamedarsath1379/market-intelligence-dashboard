import sys
from src.ingestion import constituents, prices, validate
from src.analytics import (returns, trend, contribution, breadth,
                           relative_strength, scanner, features, market_trend,
                           contribution_points, breadth_detail, rs_multi,
                           levels_events, candidates)

STEPS = [
    ("returns", returns.run), ("trend", trend.run),
    ("contribution", contribution.run), ("breadth", breadth.run),
    ("relative strength", relative_strength.run),
    ("features", features.run), ("market trend", market_trend.run),
    ("contribution points", contribution_points.run),
    ("breadth detail", breadth_detail.run),
    ("rs multi-period", rs_multi.run), ("price-level events", levels_events.run),
    ("candidates + rankings", candidates.run), ("scanner", scanner.run),
]


def main():
    if "analytics" not in sys.argv:       # "analytics" skips the download
        print("constituents");  constituents.run()
        print("prices -> bronze");  prices.run()
        print("validate -> silver");  validate.run()
    for i, (name, fn) in enumerate(STEPS, 1):
        print(f"{i}/{len(STEPS)} {name}")
        fn()
    print("Done.")

    # end-of-day alert (never breaks the data update)
    try:
        from src.alerts import telegram
        telegram.run()
    except Exception as e:
        print(f"[warn] alert failed: {e}")


if __name__ == "__main__":
    main()