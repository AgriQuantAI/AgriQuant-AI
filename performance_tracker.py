"""
AgriQuant AI - Trading Performance Tracker
Tracks and reports ag commodity futures trading performance metrics
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import statistics
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PerformanceTracker:
    """
    Tracks trading performance metrics for transparency reporting
    Calculates accuracy, profitability, risk metrics
    """
    
    def __init__(self, database_path: str = "trading_history.json"):
        self.database_path = database_path
        self.trades = self._load_trades()
    
    def _load_trades(self) -> List[Dict]:
        """Load trade history from database"""
        try:
            with open(self.database_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return []
    
    def record_trade(
        self,
        prediction_id: str,
        entry_date: str,
        entry_price: float,
        position_size_usd: float,
        direction: str,  # 'long' or 'short'
        exit_date: Optional[str] = None,
        exit_price: Optional[float] = None,
        pnl_usd: Optional[float] = None,
        prediction_correct: Optional[bool] = None
    ):
        """
        Record a trade in the history
        
        Args:
            prediction_id: Link to weather prediction
            entry_date: Trade entry date (ISO format)
            entry_price: ag commodity futures entry price
            position_size_usd: Position size in USD
            direction: 'long' or 'short'
            exit_date: Trade exit date (if closed)
            exit_price: ag commodity futures exit price (if closed)
            pnl_usd: Profit/loss in USD (if closed)
            prediction_correct: Was weather prediction accurate?
        """
        trade = {
            'trade_id': f"TRADE_{len(self.trades) + 1:04d}",
            'prediction_id': prediction_id,
            'entry_date': entry_date,
            'entry_price': entry_price,
            'position_size_usd': position_size_usd,
            'direction': direction,
            'exit_date': exit_date,
            'exit_price': exit_price,
            'pnl_usd': pnl_usd,
            'prediction_correct': prediction_correct,
            'status': 'closed' if exit_date else 'open'
        }
        
        self.trades.append(trade)
        self._save_trades()
        
        logger.info(f"Recorded trade: {trade['trade_id']} - {direction} at {entry_price}")
    
    def _save_trades(self):
        """Save trades to database"""
        with open(self.database_path, 'w') as f:
            json.dump(self.trades, f, indent=2)
    
    def calculate_metrics(self, days: Optional[int] = None) -> Dict:
        """
        Calculate performance metrics
        
        Args:
            days: Calculate for last N days (None = all time)
            
        Returns:
            Dictionary of performance metrics
        """
        # Filter trades by date if specified
        if days:
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
            trades = [t for t in self.trades if t['entry_date'] >= cutoff]
        else:
            trades = self.trades
        
        closed_trades = [t for t in trades if t['status'] == 'closed']
        
        if not closed_trades:
            return {'error': 'No closed trades found'}
        
        # Calculate metrics
        total_trades = len(closed_trades)
        winning_trades = [t for t in closed_trades if t['pnl_usd'] > 0]
        losing_trades = [t for t in closed_trades if t['pnl_usd'] <= 0]
        
        total_pnl = sum(t['pnl_usd'] for t in closed_trades)
        avg_win = statistics.mean([t['pnl_usd'] for t in winning_trades]) if winning_trades else 0
        avg_loss = statistics.mean([t['pnl_usd'] for t in losing_trades]) if losing_trades else 0
        
        # Prediction accuracy (for trades where we have prediction outcome)
        trades_with_prediction = [t for t in closed_trades if t['prediction_correct'] is not None]
        correct_predictions = [t for t in trades_with_prediction if t['prediction_correct']]
        
        # Calculate returns
        returns = []
        for trade in closed_trades:
            if trade['position_size_usd'] > 0:
                return_pct = (trade['pnl_usd'] / trade['position_size_usd']) * 100
                returns.append(return_pct)
        
        # Risk metrics
        if len(returns) > 1:
            avg_return = statistics.mean(returns)
            std_return = statistics.stdev(returns)
            sharpe = (avg_return / std_return) * (252 ** 0.5) if std_return > 0 else 0  # Annualized
        else:
            avg_return = returns[0] if returns else 0
            std_return = 0
            sharpe = 0
        
        max_drawdown = self._calculate_max_drawdown(closed_trades)
        
        return {
            'period_days': days if days else 'all_time',
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / total_trades if total_trades > 0 else 0,
            'total_pnl_usd': total_pnl,
            'avg_win_usd': avg_win,
            'avg_loss_usd': avg_loss,
            'profit_factor': abs(avg_win / avg_loss) if avg_loss != 0 else 0,
            'prediction_accuracy': len(correct_predictions) / len(trades_with_prediction) if trades_with_prediction else None,
            'avg_return_pct': avg_return,
            'std_return_pct': std_return,
            'sharpe_ratio': sharpe,
            'max_drawdown_pct': max_drawdown,
            'total_capital_traded': sum(t['position_size_usd'] for t in closed_trades),
            'calculated_at': datetime.utcnow().isoformat()
        }
    
    def _calculate_max_drawdown(self, trades: List[Dict]) -> float:
        """Calculate maximum drawdown percentage"""
        if not trades:
            return 0
        
        # Sort by exit date
        sorted_trades = sorted(trades, key=lambda x: x['exit_date'])
        
        # Calculate cumulative PnL
        cumulative_pnl = []
        running_total = 0
        
        for trade in sorted_trades:
            running_total += trade['pnl_usd']
            cumulative_pnl.append(running_total)
        
        # Find max drawdown
        peak = cumulative_pnl[0]
        max_dd = 0
        
        for pnl in cumulative_pnl:
            if pnl > peak:
                peak = pnl
            dd = ((peak - pnl) / peak * 100) if peak > 0 else 0
            max_dd = max(max_dd, dd)
        
        return max_dd
    
    def generate_monthly_report(self, year: int, month: int) -> Dict:
        """
        Generate comprehensive monthly report
        
        Args:
            year: Year (e.g., 2026)
            month: Month (1-12)
            
        Returns:
            Monthly performance report
        """
        # Filter trades for the month
        start_date = datetime(year, month, 1).isoformat()
        if month == 12:
            end_date = datetime(year + 1, 1, 1).isoformat()
        else:
            end_date = datetime(year, month + 1, 1).isoformat()
        
        monthly_trades = [
            t for t in self.trades
            if start_date <= t['entry_date'] < end_date and t['status'] == 'closed'
        ]
        
        if not monthly_trades:
            return {'error': f'No trades found for {year}-{month:02d}'}
        
        # Calculate metrics
        metrics = self.calculate_metrics(days=30)  # Approximate
        
        # Add month-specific data
        report = {
            'year': year,
            'month': month,
            'month_name': datetime(year, month, 1).strftime('%B'),
            **metrics,
            'trades': monthly_trades
        }
        
        # Save report
        filename = f"reports/monthly_{year}_{month:02d}.json"
        import os
        os.makedirs('reports', exist_ok=True)
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Monthly report generated: {filename}")
        
        return report
    
    def get_open_positions(self) -> List[Dict]:
        """Get all currently open positions"""
        return [t for t in self.trades if t['status'] == 'open']
    
    def export_for_audit(self, output_file: str = "audit_export.csv"):
        """Export all trades in CSV format for CPA audit"""
        import csv
        
        with open(output_file, 'w', newline='') as f:
            if not self.trades:
                return
            
            fieldnames = list(self.trades[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            writer.writeheader()
            for trade in self.trades:
                writer.writerow(trade)
        
        logger.info(f"Audit export saved to: {output_file}")


if __name__ == "__main__":
    # Example usage
    tracker = PerformanceTracker()
    
    # Record example trades
    tracker.record_trade(
        prediction_id="PRED_20260115_001",
        entry_date="2026-01-12T10:00:00Z",
        entry_price=425.50,
        position_size_usd=50000,
        direction="long",
        exit_date="2026-01-16T15:00:00Z",
        exit_price=445.20,
        pnl_usd=9000,
        prediction_correct=True
    )
    
    # Calculate metrics
    metrics = tracker.calculate_metrics()
    print("\nPerformance Metrics:")
    print(json.dumps(metrics, indent=2))
    
    # Generate monthly report
    report = tracker.generate_monthly_report(2026, 1)
    print("\nMonthly Report:")
    print(json.dumps(report, indent=2))
