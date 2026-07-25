# Use GARP scoring for long-term fundamental screens, and skip it for ETFs

When a user asks "is this worth buying" from an annual/long-term holder's
perspective rather than today's technical read, we needed a fundamental
scoring model. Three were considered: classic value (low P/E, high
dividend, low debt), pure quality (ROE/margin/debt only, valuation
secondary), and GARP (P/E weighed against EPS growth, i.e. PEG-ish, plus
revenue growth and quality guardrails). We chose **GARP**: classic value
would flag nearly every large growth stock (Magnificent 7 included) as
"too expensive" regardless of how fast earnings are actually growing,
which isn't a useful signal for stocks whose whole thesis is growth.

Thresholds (trailing ttm, not forward estimates — `tradingview_screener`
doesn't expose reliable forward consensus fields):

| Measure | Sehat | Waspada |
|---|---|---|
| PEG-ish (P/E ÷ EPS growth %) | < 1.5 | > 2.5 |
| Revenue growth YoY | > 10% | < 0% |
| Gross margin | > 40% | < 20% |
| Debt/Equity | < 1.0 | > 2.0 |
| ROE | > 15% | < 5% |

**Layak**: PEG-ish sehat AND at least 2 of {margin, debt, ROE} sehat AND
revenue not shrinking. Otherwise **Perlu Ditinjau** or **Kurang Layak**.

For ETFs (`type == 'fund'`), GARP does not apply — a fund has no EPS or
revenue growth of its own, only its underlying holdings do, and
`tradingview_screener` doesn't expose a reliable weighted-average of a
fund's holdings. Rather than force a number that isn't there, ETFs get a
**fund profile** instead: expense ratio, AUM, and trailing 1Y/YTD return.

The final output pairs this GARP verdict with the existing per-symbol
technical rating (TradingView's `Recommend.All` consensus) into one
**verdict gabungan** — e.g. "fundamentally Layak but technically weak
today" reads as a long-term entry opportunity, not a reason to avoid the
stock.
