# AgriQuant AI — Statistical Backtest Analysis
# R is preferred over Python for academic-grade financial statistics:
# PerformanceAnalytics, PortfolioAnalytics, rugarch for GARCH models
# Run: Rscript backtest_analysis.R

library(PerformanceAnalytics)
library(PortfolioAnalytics)
library(rugarch)
library(xts)
library(quantmod)
library(ggplot2)
library(dplyr)
library(lubridate)

# ============================================================
# LOAD BACKTEST RESULTS FROM PYTHON OUTPUT
# ============================================================

load_backtest_results <- function(path = "backtest_results.csv") {
  df <- read.csv(path, stringsAsFactors = FALSE)
  df$date <- as.Date(df$date)
  df$return <- as.numeric(df$return)
  return(df)
}

# ============================================================
# EQUITY CURVE & DRAWDOWN ANALYSIS
# ============================================================

build_equity_curve <- function(returns_df) {
  # Convert to xts for PerformanceAnalytics
  ret_xts <- xts(returns_df$return, order.by = returns_df$date)

  # Compute cumulative equity curve starting at $100k
  equity <- cumprod(1 + ret_xts) * 100000

  # Drawdown series
  dd <- Drawdowns(ret_xts)
  max_dd <- maxDrawdown(ret_xts)
  avg_dd <- mean(dd[dd < 0], na.rm = TRUE)

  # Drawdown duration
  dd_table <- table.Drawdowns(ret_xts, top = 10)

  cat("=== DRAWDOWN ANALYSIS ===\n")
  cat(sprintf("Max Drawdown:     %.2f%%\n", max_dd * 100))
  cat(sprintf("Average Drawdown: %.2f%%\n", avg_dd * 100))
  cat("\nTop 10 Drawdowns:\n")
  print(dd_table)

  return(list(equity = equity, drawdowns = dd, max_dd = max_dd))
}

# ============================================================
# SHARPE, SORTINO, CALMAR RATIOS
# ============================================================

compute_risk_metrics <- function(ret_xts, rf_rate = 0.05) {
  # Annualize (assuming daily returns, 252 trading days)
  ann_return <- Return.annualized(ret_xts, scale = 252)
  sharpe     <- SharpeRatio.annualized(ret_xts, Rf = rf_rate / 252,
                                        scale = 252)
  sortino    <- SortinoRatio(ret_xts, MAR = rf_rate / 252)
  calmar     <- CalmarRatio(ret_xts, scale = 252)
  omega      <- OmegaSharpeRatio(ret_xts)
  var_95     <- VaR(ret_xts, p = 0.95, method = "historical")
  cvar_95    <- CVaR(ret_xts, p = 0.95, method = "historical")

  metrics <- data.frame(
    Metric = c("Ann. Return", "Sharpe Ratio", "Sortino Ratio",
               "Calmar Ratio", "Omega Ratio", "VaR (95%)", "CVaR (95%)"),
    Value  = c(
      sprintf("%.1f%%", ann_return * 100),
      sprintf("%.2f",   sharpe),
      sprintf("%.2f",   sortino),
      sprintf("%.2f",   calmar),
      sprintf("%.2f",   omega),
      sprintf("%.2f%%", var_95 * 100),
      sprintf("%.2f%%", cvar_95 * 100)
    )
  )

  cat("\n=== RISK-ADJUSTED PERFORMANCE METRICS ===\n")
  print(metrics, row.names = FALSE)
  return(metrics)
}

# ============================================================
# GARCH VOLATILITY REGIME ANALYSIS
# ============================================================

fit_garch_model <- function(ret_xts) {
  # GJR-GARCH(1,1) with Student-t errors
  # GJR captures asymmetric volatility (bad news hits harder)
  spec <- ugarchspec(
    variance.model = list(
      model = "gjrGARCH",
      garchOrder = c(1, 1),
      submodel = NULL,
      external.regressors = NULL,
      variance.targeting = FALSE
    ),
    mean.model = list(
      armaOrder = c(1, 0),
      include.mean = TRUE
    ),
    distribution.model = "std"   # Student-t fat tails
  )

  tryCatch({
    fit <- ugarchfit(spec = spec, data = ret_xts,
                     solver = "hybrid", fit.control = list(stationarity = 1))

    # Volatility forecast 10 days ahead
    forecast_vol <- ugarchforecast(fit, n.ahead = 10)

    cat("\n=== GARCH(1,1) VOLATILITY MODEL ===\n")
    cat("Model: GJR-GARCH(1,1) with Student-t errors\n")
    show(fit)

    return(list(fit = fit, forecast = forecast_vol))
  }, error = function(e) {
    cat(sprintf("GARCH fitting error: %s\n", e$message))
    return(NULL)
  })
}

# ============================================================
# CROSS-COMMODITY CORRELATION BOOTSTRAP
# ============================================================

bootstrap_correlation <- function(returns_wide, n_boot = 2000,
                                   conf_level = 0.95) {
  # Bootstrap confidence intervals for correlation matrix
  n <- nrow(returns_wide)
  cols <- colnames(returns_wide)
  n_pairs <- length(cols) * (length(cols) - 1) / 2

  boot_cors <- matrix(NA, nrow = n_boot, ncol = n_pairs)

  for (i in 1:n_boot) {
    idx <- sample(n, n, replace = TRUE)
    boot_sample <- returns_wide[idx, ]
    cor_mat <- cor(boot_sample, use = "pairwise.complete.obs")

    # Extract upper triangle
    pair_idx <- 1
    for (r in 1:(length(cols)-1)) {
      for (cc in (r+1):length(cols)) {
        boot_cors[i, pair_idx] <- cor_mat[r, cc]
        pair_idx <- pair_idx + 1
      }
    }
  }

  # Compute CIs
  alpha <- (1 - conf_level) / 2
  ci_lower <- apply(boot_cors, 2, quantile, probs = alpha, na.rm = TRUE)
  ci_upper <- apply(boot_cors, 2, quantile, probs = 1 - alpha, na.rm = TRUE)
  ci_mean  <- apply(boot_cors, 2, mean, na.rm = TRUE)

  cat(sprintf("\n=== BOOTSTRAP CORRELATION CIs (n=%d, %.0f%% CI) ===\n",
              n_boot, conf_level * 100))

  pair_idx <- 1
  results <- list()
  for (r in 1:(length(cols)-1)) {
    for (cc in (r+1):length(cols)) {
      cat(sprintf("  %s/%s: %.3f [%.3f, %.3f]\n",
                  cols[r], cols[cc],
                  ci_mean[pair_idx],
                  ci_lower[pair_idx],
                  ci_upper[pair_idx]))
      results[[paste(cols[r], cols[cc], sep="/")]] <- list(
        mean = ci_mean[pair_idx],
        lower = ci_lower[pair_idx],
        upper = ci_upper[pair_idx]
      )
      pair_idx <- pair_idx + 1
    }
  }
  return(results)
}

# ============================================================
# MONTE CARLO SIMULATION
# ============================================================

monte_carlo_equity <- function(ann_return, ann_vol, n_years = 3,
                                n_sims = 5000, initial = 100000) {
  daily_ret <- ann_return / 252
  daily_vol <- ann_vol / sqrt(252)
  n_days    <- n_years * 252

  set.seed(42)
  simulations <- matrix(
    rnorm(n_days * n_sims, mean = daily_ret, sd = daily_vol),
    nrow = n_days, ncol = n_sims
  )

  equity_paths <- apply(simulations, 2, function(r) {
    cumprod(1 + r) * initial
  })

  final_values <- equity_paths[n_days, ]

  results <- list(
    median_final    = median(final_values),
    p5_final        = quantile(final_values, 0.05),
    p25_final       = quantile(final_values, 0.25),
    p75_final       = quantile(final_values, 0.75),
    p95_final       = quantile(final_values, 0.95),
    pct_profitable  = mean(final_values > initial) * 100
  )

  cat("\n=== MONTE CARLO SIMULATION ===\n")
  cat(sprintf("Simulations: %d | Horizon: %d years\n", n_sims, n_years))
  cat(sprintf("P5  final value:  $%s\n",
              format(round(results$p5_final), big.mark=",")))
  cat(sprintf("P25 final value:  $%s\n",
              format(round(results$p25_final), big.mark=",")))
  cat(sprintf("Median final:     $%s\n",
              format(round(results$median_final), big.mark=",")))
  cat(sprintf("P75 final value:  $%s\n",
              format(round(results$p75_final), big.mark=",")))
  cat(sprintf("P95 final value:  $%s\n",
              format(round(results$p95_final), big.mark=",")))
  cat(sprintf("%% profitable:     %.1f%%\n", results$pct_profitable))

  return(results)
}

# ============================================================
# MAIN
# ============================================================
main <- function() {
  cat("AgriQuant AI — Statistical Backtest Analysis\n")
  cat(paste(rep("=", 50), collapse=""), "\n\n")

  # Example usage (requires backtest_results.csv from backtest.py)
  if (file.exists("backtest_results.csv")) {
    results <- load_backtest_results()
    ret_xts <- xts(results$return, order.by = results$date)

    equity_data  <- build_equity_curve(results)
    risk_metrics <- compute_risk_metrics(ret_xts)
    garch_model  <- fit_garch_model(ret_xts)
    mc_results   <- monte_carlo_equity(ann_return = 0.65,
                                        ann_vol = 0.35,
                                        n_years = 3)
  } else {
    cat("Run backtest.py first to generate backtest_results.csv\n")
    cat("Then: Rscript backtest_analysis.R\n")

    # Demo with synthetic data
    set.seed(42)
    n_days <- 756  # 3 years
    demo_returns <- rnorm(n_days, mean = 0.002, sd = 0.015)
    demo_dates   <- seq(as.Date("2023-01-03"), by = "day",
                        length.out = n_days)
    demo_xts <- xts(demo_returns, order.by = demo_dates)

    compute_risk_metrics(demo_xts)
    monte_carlo_equity(ann_return = 0.65, ann_vol = 0.35)
  }
}

main()
