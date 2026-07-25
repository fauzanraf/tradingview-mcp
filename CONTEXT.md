# tradingview-mcp

An MCP server that exposes TradingView market data — screeners, technical
indicators, backtests, and news — as tools an LLM can call.

## Language

**Rating teknikal (komposit BB)**:
The −3…+3 Bollinger/indicator composite this project computes itself
(`fetch_trending_analysis`, exposed via the `rating_filter` tool). Specific
to crypto + the exchanges listed in `EXCHANGE_SCREENER`; not available for
IDX today.
_Avoid_: "rating" alone, "sinyal" alone — both are ambiguous with the two
other rating systems below.

**Rating konsensus TradingView**:
TradingView's own `Recommend.All` summary (STRONG_BUY … STRONG_SELL),
fetched via `tradingview_ta.TA_Handler(...).get_analysis().summary` for a
named symbol. Independent of this project's composite rating above — the
two use different inputs and can disagree on the same symbol.
_Avoid_: confusing with "rating teknikal (komposit BB)".

**Skor fundamental (GARP)**:
A long-term-holder scoring model (Growth-At-Reasonable-Price) this project
computes from `tradingview_screener` fundamentals: PEG-ish (P/E ÷ EPS
growth %), revenue growth YoY, gross margin, debt/equity, ROE. Produces one
of **Layak**, **Perlu Ditinjau**, or **Kurang Layak**. Applies to individual
equities only — see ADR 0001 for why ETFs are scored differently.
_Avoid_: "value score", "fundamental rating" — GARP is a specific rubric,
not a generic label.

**Verdict gabungan**:
The pairing of Rating konsensus TradingView (today's technical read) with
Skor fundamental GARP (the long-term read) for the same symbol, used to
tell "cheap and falling" apart from "expensive and rising" for a long-term
holder. Not a new number — a juxtaposition of the two ratings above.

**Profil dana (fund profile)**:
For ETFs (`type == 'fund'`), the substitute for a GARP score: expense
ratio, AUM, and trailing 1Y/YTD return. ETFs don't carry their own EPS or
revenue growth, so GARP's inputs don't apply to them — see ADR 0001.
