from vibefinance.data.market_sim import generate_market, validate_market


def load_market(ticker: str, live: bool = False):
    if live:
        try:
            import yfinance as yf
            frame = yf.download(ticker, period="2y", progress=False, auto_adjust=True, timeout=5)
            if hasattr(frame.columns, "levels"):
                frame.columns = frame.columns.get_level_values(0)
            frame = frame.rename(columns=str.lower).reset_index().rename(columns={"Date": "date"})
            validate_market(frame)
            frame.attrs.update(mode="live", source_id=f"market:{ticker}:yfinance")
            return frame, None
        except Exception as exc:
            return generate_market(ticker), f"Live feed unavailable ({type(exc).__name__}); using seeded simulation."
    return generate_market(ticker), None
