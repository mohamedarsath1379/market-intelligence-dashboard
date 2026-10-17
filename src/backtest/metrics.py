import numpy as np


def summarize(t):
    if t is None or len(t) == 0:
        return {"trades": 0}
    r = t["ret_pct"]
    wins = r[r > 0]
    losses = r[r <= 0]
    eq = np.concatenate(
        [[0.0], t.sort_values("exit_date")["ret_pct"].cumsum().to_numpy()])
    max_dd = (eq - np.maximum.accumulate(eq)).min()
    gross_loss = losses.sum()
    return {
        "trades": int(len(r)),
        "win_rate_pct": round(len(wins) / len(r) * 100, 1),
        "avg_return_pct": round(r.mean(), 3),      # expectancy per trade, after costs
        "median_return_pct": round(r.median(), 3),
        "avg_win_pct": round(wins.mean(), 3) if len(wins) else 0.0,
        "avg_loss_pct": round(losses.mean(), 3) if len(losses) else 0.0,
        "profit_factor": round(wins.sum() / abs(gross_loss), 2) if gross_loss < 0 else None,
        "max_drawdown_pts": round(float(max_dd), 2),  # on cumulative sum of trade returns
        "worst_trade_pct": round(r.min(), 2),
    }