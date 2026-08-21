from __future__ import annotations

ANALYTICS_PAGE_STYLES = """
    <style>
    .analytics-kpi-row-spacer {
        height: 0.24rem;
    }
    .analytics-light-tape {
        min-height: 42px;
        border-radius: 10px;
        background: linear-gradient(180deg, #ffffff 0%, #f7f9fb 100%);
        border: 1px solid rgba(8, 33, 20, 0.08);
        display: flex;
        align-items: stretch;
        overflow: hidden;
        margin-bottom: 6px;
    }
    .analytics-light-tape-item {
        flex: 1 1 0;
        min-width: 0;
        padding: 0.3rem 0.46rem 0.26rem 0.46rem;
        border-right: 1px solid rgba(8, 33, 20, 0.08);
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .analytics-light-tape-item:last-child {
        border-right: none;
    }
    .analytics-light-tape-symbol {
        max-width: 120px;
        align-items: center;
        justify-content: center;
    }
    .analytics-light-tape-eyebrow {
        display: flex;
        align-items: center;
        gap: 0.22rem;
        margin-bottom: 0.06rem;
    }
    .analytics-light-tape-dot {
        width: 0.28rem;
        height: 0.28rem;
        border-radius: 999px;
        background: #02fb7e;
        flex-shrink: 0;
    }
    .analytics-light-tape-label {
        color: #082114;
        font-size: 0.48rem;
        font-weight: 600;
        line-height: 1.0;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        white-space: nowrap;
    }
    .analytics-light-tape-main {
        color: #000000;
        font-size: 0.92rem;
        font-weight: 700;
        line-height: 0.94;
        letter-spacing: -0.01em;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-bottom: 0.04rem;
    }
    .analytics-light-tape-main-row {
        display: flex;
        align-items: baseline;
        gap: 0.28rem;
        min-width: 0;
    }
    .analytics-light-tape-zscore {
        color: rgba(8, 33, 20, 0.68);
        font-size: 0.52rem;
        font-weight: 600;
        line-height: 1.0;
        white-space: nowrap;
        flex-shrink: 0;
    }
    .analytics-light-tape-zscore-stack {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 0.04rem;
        min-width: 0;
        flex-shrink: 0;
    }
    .analytics-light-tape-zmeta {
        display: flex;
        flex-direction: column;
        gap: 0.01rem;
        min-width: 0;
    }
    .analytics-light-tape-zmeta-line {
        color: rgba(8, 33, 20, 0.54);
        font-size: 0.4rem;
        font-weight: 400;
        line-height: 1.05;
        letter-spacing: 0.01em;
        white-space: nowrap;
        display: inline-flex;
        align-items: center;
        width: fit-content;
        padding: 0.06rem 0.28rem;
        border-radius: 999px;
        background: rgba(8, 33, 20, 0.06);
    }
    .analytics-light-tape-zmeta-line-green {
        color: #0b6b35;
        background: rgba(2, 251, 126, 0.18);
    }
    .analytics-light-tape-zmeta-line-red {
        color: #b42318;
        background: rgba(255, 95, 87, 0.18);
    }
    .analytics-light-tape-zmeta-line-blue {
        color: #155eef;
        background: rgba(21, 94, 239, 0.14);
    }
    .analytics-light-tape-zmeta-line-gray {
        color: #667085;
        background: rgba(102, 112, 133, 0.12);
    }
    .analytics-light-tape-sub {
        color: rgba(8, 33, 20, 0.62);
        font-size: 0.5rem;
        font-weight: 500;
        line-height: 0.98;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .analytics-market-tape {
        min-height: 42px;
        margin-top: 6px;
        border-radius: 10px;
        background: linear-gradient(180deg, #0d1117 0%, #11161d 100%);
        border: 1px solid rgba(255, 255, 255, 0.06);
        display: flex;
        align-items: stretch;
        overflow: hidden;
    }
    .analytics-market-tape-item {
        flex: 1 1 0;
        min-width: 0;
        padding: 0.32rem 0.48rem 0.28rem 0.48rem;
        border-right: 1px solid rgba(255, 255, 255, 0.08);
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .analytics-market-tape-item:last-child {
        border-right: none;
    }
    .analytics-market-tape-eyebrow {
        display: flex;
        align-items: center;
        margin-bottom: 0.06rem;
    }
    .analytics-market-tape-label {
        color: rgba(255, 255, 255, 0.72);
        font-size: 0.48rem;
        font-weight: 600;
        line-height: 1.0;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        white-space: nowrap;
    }
    .analytics-market-tape-main-row {
        display: flex;
        align-items: baseline;
        gap: 0.34rem;
        min-width: 0;
    }
    .analytics-market-tape-main {
        color: #f8fafc;
        font-size: 0.8rem;
        font-weight: 700;
        line-height: 0.92;
        letter-spacing: -0.01em;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-bottom: 0.05rem;
    }
    .analytics-market-tape-inline-percent {
        font-size: 0.54rem;
        font-weight: 700;
        line-height: 1;
        white-space: nowrap;
        flex-shrink: 0;
    }
    .analytics-market-tape-inline-percent-positive {
        color: #02fb7e;
    }
    .analytics-market-tape-inline-percent-negative {
        color: #ff5f57;
    }
    .analytics-market-tape-sub {
        color: rgba(255, 255, 255, 0.58);
        font-size: 0.46rem;
        font-weight: 500;
        line-height: 0.98;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .analytics-market-tape-sub-inline {
        display: inline-flex;
        align-items: baseline;
        gap: 0.28rem;
        white-space: nowrap;
    }
    .analytics-market-tape-item-positive .analytics-market-tape-main,
    .analytics-market-tape-item-positive .analytics-market-tape-sub {
        color: #02fb7e;
    }
    .analytics-market-tape-item-negative .analytics-market-tape-main,
    .analytics-market-tape-item-negative .analytics-market-tape-sub {
        color: #ff5f57;
    }
    .analytics-market-tape-item-market .analytics-market-tape-main {
        color: #8ab4f8;
    }
    .analytics-market-tape-item-paired {
        gap: 0.18rem;
    }
    .analytics-market-tape-pair {
        display: flex;
        flex-direction: column;
        gap: 0.02rem;
    }
    .analytics-market-tape-pair-label {
        color: rgba(255, 255, 255, 0.72);
        font-size: 0.45rem;
        font-weight: 600;
        line-height: 1;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        white-space: nowrap;
    }
    .analytics-market-tape-pair-value {
        color: #8ab4f8;
        font-size: 0.66rem;
        font-weight: 700;
        line-height: 1;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .analytics-diagnostic-strip {
        margin-top: 0.36rem;
        margin-bottom: 0.5rem;
    }
    .analytics-diagnostic-caption {
        margin-top: 0.12rem;
        margin-bottom: 0.24rem;
        font-size: 0.52rem;
        line-height: 1.2;
        font-weight: 400;
        font-style: italic;
        color: rgba(8, 33, 20, 0.58);
    }
    .analytics-reference-card-title {
        margin-bottom: 0.16rem;
        font-size: 0.46rem;
        line-height: 1.1;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #6f7a83;
    }
    .analytics-reference-card-copy {
        margin-top: 0.12rem;
        font-size: 0.44rem;
        line-height: 1.26;
        font-weight: 400;
        color: #5f6971;
    }
    .analytics-reference-divider {
        width: 1px;
        min-height: 100%;
        height: 100%;
        margin: 0 auto;
        background: rgba(8, 33, 20, 0.1);
    }
    div[data-testid="stLatex"] {
        margin-top: 0.02rem !important;
        margin-bottom: 0.02rem !important;
    }
    div[data-testid="stLatex"] .katex {
        font-size: 0.48em !important;
    }
    div[data-testid="stLatex"] .katex-display {
        margin: 0 !important;
        overflow-x: auto;
        overflow-y: hidden;
        padding: 0.02rem 0;
    }
    div[data-testid="stLatex"] .katex-display > .katex {
        white-space: nowrap;
    }
    .analytics-diagnostic-strip-dark {
        border-radius: 10px;
        overflow: hidden;
    }
    .analytics-diagnostic-symbol-item {
        justify-content: center;
    }
    .analytics-diagnostic-symbol-item-dark {
        justify-content: center;
        display: flex;
        align-items: center;
        min-width: 160px;
    }
    .analytics-diagnostic-light-item,
    .analytics-diagnostic-dark-item {
        display: flex;
        flex-direction: column;
        justify-content: center;
        gap: 0.12rem;
        min-height: 52px;
        padding-top: 0.18rem;
        padding-bottom: 0.18rem;
    }
    .analytics-diagnostic-title {
        width: 100%;
        text-transform: uppercase;
        letter-spacing: 0.02em;
        font-weight: 600;
        line-height: 1.0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .analytics-diagnostic-title-light {
        font-size: 0.48rem;
        color: #082114;
    }
    .analytics-diagnostic-title-dark {
        font-size: 0.48rem;
        color: rgba(255, 255, 255, 0.72);
    }
    .analytics-diagnostic-copy {
        display: block;
        overflow: visible;
        white-space: normal;
        text-wrap: balance;
        width: 100%;
    }
    .analytics-diagnostic-copy-light {
        font-size: 0.44rem;
        line-height: 1.14;
        font-weight: 400;
        color: rgba(8, 33, 20, 0.64);
    }
    .analytics-diagnostic-copy-dark {
        font-size: 0.44rem;
        line-height: 1.14;
        font-weight: 400;
        color: #02fb7e;
    }
    </style>
"""
