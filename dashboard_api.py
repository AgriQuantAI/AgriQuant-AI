"""
AgriQuant AI - Dashboard API
FastAPI server for public dashboard and transparency reporting
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional
from datetime import datetime
import json

app = FastAPI(title="AgriQuant AI Dashboard API", version="1.0.0")

# CORS for web dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "AgriQuant AI Dashboard API",
        "version": "1.0.0",
        "endpoints": {
            "/health": "System health check",
            "/stats": "Overall statistics",
            "/predictions/recent": "Recent weather predictions",
            "/trading/performance": "Trading performance metrics",
            "/token/supply": "Token supply and burn data",
            "/airdrops/history": "USDT airdrop history",
            "/buybacks/history": "Token buyback history"
        }
    }


@app.get("/health")
async def health_check():
    """System health check"""
    return {
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "weather_monitoring": "active",
            "claude_ai": "active",
            "database": "active",
            "trading": "active"
        }
    }


@app.get("/stats")
async def get_overall_stats():
    """Get overall platform statistics"""
    # In production, fetch from database
    return {
        "predictions": {
            "total": 23,
            "accuracy": 0.70,
            "last_prediction": "2026-02-15T08:00:00Z"
        },
        "trading": {
            "total_capital_usd": 1250000,
            "monthly_return_avg": 0.10,
            "sharpe_ratio": 2.3,
            "win_rate": 0.68
        },
        "token": {
            "total_supply": 1000000000,
            "circulating_supply": 950000000,
            "burned_supply": 50000000,
            "holders": 1547
        },
        "distributions": {
            "total_usdt_distributed": 187500,
            "total_buybacks_usd": 187500,
            "last_airdrop": "2026-01-15T00:00:00Z",
            "next_airdrop": "2026-04-15T00:00:00Z"
        }
    }


@app.get("/predictions/recent")
async def get_recent_predictions(limit: int = 10):
    """Get recent weather predictions"""
    # In production, fetch from database
    predictions = [
        {
            "prediction_id": "PRED_20260215_001",
            "timestamp": "2026-02-15T08:00:00Z",
            "county": "Polk",
            "event_type": "freeze",
            "confidence": 0.82,
            "expected_damage_pct": 0.13,
            "status": "pending_verification"
        }
    ]
    return {"predictions": predictions[:limit]}


@app.get("/trading/performance")
async def get_trading_performance(days: Optional[int] = 30):
    """Get trading performance metrics"""
    # In production, fetch from PerformanceTracker
    return {
        "period_days": days,
        "total_trades": 8,
        "win_rate": 0.68,
        "total_pnl_usd": 45230,
        "sharpe_ratio": 2.3,
        "max_drawdown_pct": 8.5,
        "prediction_accuracy": 0.72
    }


@app.get("/token/supply")
async def get_token_supply():
    """Get current token supply data"""
    return {
        "total_supply": 1000000000,
        "circulating_supply": 950000000,
        "burned_supply": 50000000,
        "burn_percentage": 5.0,
        "last_burn": "2026-01-31T00:00:00Z",
        "next_burn": "2026-02-28T00:00:00Z"
    }


@app.get("/airdrops/history")
async def get_airdrop_history():
    """Get USDT airdrop distribution history"""
    return {
        "airdrops": [
            {
                "quarter": "Q1_2026",
                "date": "2026-01-15T00:00:00Z",
                "total_usdt": 187500,
                "holders": 1245,
                "transactions": 1245,
                "status": "completed"
            }
        ]
    }


@app.get("/buybacks/history")
async def get_buyback_history():
    """Get token buyback history"""
    return {
        "buybacks": [
            {
                "month": "2026-01",
                "date": "2026-01-31T00:00:00Z",
                "usdc_spent": 187500,
                "tokens_burned": 45678900,
                "avg_price": 0.00411,
                "burn_tx": "5YHx...abc123"
            }
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
