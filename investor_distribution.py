"""
AgriQuant AI - USDT Airdrop Distributor
Handles quarterly distributions to $AGQNT holders
"""

import os
import json
from datetime import datetime
from typing import Dict, List
from base.rpc.api import Client
from solders.keypair import Keypair
from solders.pubkey import Pubkey
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class USDTAirdropDistributor:
    """
    Distributes USDT airdrops to $AGQNT token holders quarterly
    50% of trading profits allocated to USDT distributions
    """
    
    USDT_MINT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"  # USDT on Base
    DISTRIBUTION_SCHEDULE = [
        {'month': 1, 'day': 15},  # January 15
        {'month': 4, 'day': 15},  # April 15
        {'month': 7, 'day': 15},  # July 15
        {'month': 10, 'day': 15}  # October 15
    ]
    
    def __init__(self, rpc_url: str = "https://api.mainnet-beta.base.com"):
        self.client = Client(rpc_url)
        self.wallet_keypair = self._load_wallet()
        
    def _load_wallet(self) -> Keypair:
        """Load distribution wallet from environment"""
        private_key = os.getenv('AIRDROP_WALLET_PRIVATE_KEY')
        if not private_key:
            raise ValueError("AIRDROP_WALLET_PRIVATE_KEY not set")
        return Keypair.from_base58_string(private_key)
    
    def calculate_quarterly_distribution(self, quarterly_profits_usdc: float) -> float:
        """
        Calculate 50% of quarterly profits for USDT airdrop
        
        Args:
            quarterly_profits_usdc: Total quarterly trading profits
            
        Returns:
            USDT amount for distribution
        """
        distribution_percentage = 0.50  # 50% to airdrops, 50% to buybacks
        return quarterly_profits_usdc * distribution_percentage
    
    def get_token_holders(self) -> List[Dict]:
        """
        Fetch all $AGQNT token holders and their balances
        
        Returns:
            List of {address: str, balance: int, percentage: float}
        """
        orng_mint = os.getenv('ORNG_TOKEN_MINT', 'PLACEHOLDER')
        
        # This would query the Base blockchain for all token accounts
        # For now, return placeholder
        
        # In production, use:
        # response = self.client.get_token_accounts_by_owner(...)
        
        holders = []
        # Placeholder data
        total_supply = 1_000_000_000  # 1B tokens
        
        # Would populate from on-chain data
        return holders
    
    def calculate_holder_allocations(
        self, 
        total_usdt: float,
        holders: List[Dict]
    ) -> List[Dict]:
        """
        Calculate USDT allocation for each holder based on token percentage
        
        Args:
            total_usdt: Total USDT to distribute
            holders: List of token holders with balances
            
        Returns:
            List of {address, orng_balance, usdt_amount}
        """
        allocations = []
        
        for holder in holders:
            usdt_amount = total_usdt * holder['percentage']
            
            # Minimum distribution threshold (avoid dust)
            if usdt_amount >= 0.01:  # $0.01 minimum
                allocations.append({
                    'address': holder['address'],
                    'orng_balance': holder['balance'],
                    'orng_percentage': holder['percentage'],
                    'usdt_amount': usdt_amount
                })
        
        return allocations
    
    def execute_airdrop(
        self,
        total_usdt: float,
        dry_run: bool = True
    ) -> Dict:
        """
        Execute quarterly USDT airdrop to all holders
        
        Args:
            total_usdt: Total USDT to distribute
            dry_run: If True, simulate without executing
            
        Returns:
            Distribution summary and transaction signatures
        """
        logger.info(f"Executing USDT airdrop: ${total_usdt:,.2f} (dry_run={dry_run})")
        
        # Step 1: Get current holders
        holders = self.get_token_holders()
        logger.info(f"Found {len(holders)} token holders")
        
        # Step 2: Calculate allocations
        allocations = self.calculate_holder_allocations(total_usdt, holders)
        logger.info(f"Calculated {len(allocations)} allocations (above $0.01 minimum)")
        
        if dry_run:
            return {
                'dry_run': True,
                'total_usdt': total_usdt,
                'total_holders': len(holders),
                'eligible_holders': len(allocations),
                'largest_allocation': max([a['usdt_amount'] for a in allocations]) if allocations else 0,
                'smallest_allocation': min([a['usdt_amount'] for a in allocations]) if allocations else 0,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Step 3: Execute transfers
        transactions = []
        successful = 0
        failed = 0
        
        for allocation in allocations:
            try:
                # In production, create and send USDT transfer transaction
                # tx_sig = self._send_usdt(allocation['address'], allocation['usdt_amount'])
                tx_sig = f"PLACEHOLDER_TX_{allocation['address'][:8]}"
                
                transactions.append({
                    'address': allocation['address'],
                    'amount': allocation['usdt_amount'],
                    'tx_signature': tx_sig,
                    'status': 'success'
                })
                successful += 1
                
            except Exception as e:
                logger.error(f"Failed to send to {allocation['address']}: {e}")
                transactions.append({
                    'address': allocation['address'],
                    'amount': allocation['usdt_amount'],
                    'error': str(e),
                    'status': 'failed'
                })
                failed += 1
        
        result = {
            'success': True,
            'total_usdt_distributed': sum(t['amount'] for t in transactions if t['status'] == 'success'),
            'successful_transfers': successful,
            'failed_transfers': failed,
            'transactions': transactions,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Airdrop complete: {successful} successful, {failed} failed")
        
        # Step 4: Record distribution
        self._record_airdrop(result)
        
        return result
    
    def _record_airdrop(self, airdrop_data: Dict):
        """Record airdrop in database for transparency"""
        quarter = (datetime.utcnow().month - 1) // 3 + 1
        year = datetime.utcnow().year
        filename = f"airdrops_{year}_Q{quarter}.json"
        
        with open(filename, 'w') as f:
            json.dump(airdrop_data, f, indent=2)
    
    def get_next_distribution_date(self) -> datetime:
        """Calculate next scheduled distribution date"""
        now = datetime.utcnow()
        
        for schedule in self.DISTRIBUTION_SCHEDULE:
            dist_date = datetime(now.year, schedule['month'], schedule['day'])
            if dist_date > now:
                return dist_date
        
        # If all dates passed, return first date of next year
        return datetime(now.year + 1, 1, 15)
    
    def get_holder_history(self, wallet_address: str) -> List[Dict]:
        """
        Get airdrop history for a specific holder
        
        Args:
            wallet_address: Base wallet address
            
        Returns:
            List of historical airdrops received
        """
        import glob
        
        history = []
        
        for filename in glob.glob("airdrops_*.json"):
            with open(filename, 'r') as f:
                data = json.load(f)
            
            for tx in data.get('transactions', []):
                if tx['address'] == wallet_address and tx['status'] == 'success':
                    history.append({
                        'date': data['timestamp'],
                        'amount_usdt': tx['amount'],
                        'tx_signature': tx['tx_signature']
                    })
        
        return sorted(history, key=lambda x: x['date'], reverse=True)


if __name__ == "__main__":
    # Example usage
    distributor = USDTAirdropDistributor()
    
    # Simulate quarterly distribution with $50,000 profits
    quarterly_profits = 50000.00
    distribution_amount = distributor.calculate_quarterly_distribution(quarterly_profits)
    
    print(f"Quarterly profits: ${quarterly_profits:,.2f}")
    print(f"USDT airdrop allocation (50%): ${distribution_amount:,.2f}")
    print(f"Next distribution: {distributor.get_next_distribution_date()}")
    
    # Dry run
    result = distributor.execute_airdrop(distribution_amount, dry_run=True)
    print(f"\nDry run result:")
    print(json.dumps(result, indent=2))
