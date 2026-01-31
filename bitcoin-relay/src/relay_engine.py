"""
Relay Engine - Background worker that monitors blocks and processes relays.
"""
import threading
import time
import logging
from typing import Optional, Dict, List, Any

from .config import BLOCK_POLL_INTERVAL
from .bitcoin_utils import BitcoinAPI, WalletManager
from .encryption import KeyEncryption
from .database import (
    get_all_relay_chains, get_relay_hops, update_hop_funded,
    update_hop_relayed, update_chain_amounts, update_chain_status,
    get_last_block_height, update_block_height, log_transaction,
    update_hop_status
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('RelayEngine')


class RelayEngine:
    """
    Background engine that monitors blocks and processes relays.
    
    The engine runs in a separate thread and:
    1. Polls the blockchain for new blocks
    2. Checks intake addresses for incoming funds
    3. Relays funds through hops according to Fibonacci delays
    4. Sends final amounts to destination addresses
    """
    
    def __init__(self, network: str, password: str):
        """
        Initialize the relay engine.
        
        Args:
            network: 'testnet' or 'mainnet'
            password: Master password for decrypting private keys
        """
        self.network = network
        self.password = password
        self.api = BitcoinAPI(network)
        self.wallet = WalletManager(network)
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        logger.info(f"Relay engine initialized for {network}")
    
    def start(self):
        """Start the relay engine in a background thread."""
        if self.is_running:
            logger.warning("Engine already running")
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.is_running = True
        logger.info("Relay engine started")
    
    def stop(self):
        """Stop the relay engine."""
        logger.info("Stopping relay engine...")
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        self.is_running = False
        logger.info("Relay engine stopped")
    
    def _run(self):
        """Main engine loop."""
        logger.info("Relay engine loop started")
        
        while not self._stop_event.is_set():
            try:
                self._process_cycle()
            except Exception as e:
                logger.error(f"Error in relay cycle: {e}", exc_info=True)
            
            # Wait before next poll
            self._stop_event.wait(BLOCK_POLL_INTERVAL)
        
        logger.info("Relay engine loop ended")
    
    def _process_cycle(self):
        """Process one cycle of checking and relaying."""
        # Get current block height
        try:
            current_block = self.api.get_block_height()
        except Exception as e:
            logger.error(f"Failed to get block height: {e}")
            return
        
        # Get active chains for this network
        chains = get_all_relay_chains(self.network)
        active_chains = [c for c in chains if c['status'] == 'active']
        
        if not active_chains:
            logger.debug("No active chains to process")
            update_block_height(self.network, current_block)
            return
        
        logger.info(f"Processing {len(active_chains)} active chains at block {current_block}")
        
        # Process each active chain
        for chain in active_chains:
            try:
                self._process_chain(chain, current_block)
            except Exception as e:
                logger.error(f"Error processing chain {chain['id']}: {e}", exc_info=True)
        
        # Update tracked block height
        update_block_height(self.network, current_block)
    
    def _process_chain(self, chain: Dict[str, Any], current_block: int):
        """
        Process a single relay chain.
        
        Args:
            chain: Chain data from database
            current_block: Current blockchain height
        """
        chain_id = chain['id']
        hops = get_relay_hops(chain_id)
        
        if not hops:
            logger.warning(f"Chain {chain_id} has no hops")
            return
        
        # Step 1: Check if intake address has received funds (first hop)
        first_hop = hops[0]
        if first_hop['status'] == 'waiting' and chain['amount_received_sats'] is None:
            self._check_intake(chain, first_hop, current_block)
            # Refresh hops after potential update
            hops = get_relay_hops(chain_id)
        
        # Step 2: Process hops that are ready to relay
        for hop in hops:
            if hop['status'] == 'pending_relay':
                if current_block >= (hop['relay_at_block'] or 0):
                    self._relay_hop(chain, hop, hops, current_block)
        
        # Step 3: Check if chain is complete
        hops = get_relay_hops(chain_id)  # Refresh
        if self._is_chain_complete(hops):
            self._complete_chain(chain, hops)
    
    def _check_intake(self, chain: Dict[str, Any], first_hop: Dict[str, Any], current_block: int):
        """
        Check if the intake address has received funds.
        
        Args:
            chain: Chain data
            first_hop: First hop data
            current_block: Current blockchain height
        """
        intake_address = chain['intake_address']
        chain_id = chain['id']
        
        logger.debug(f"Checking intake address {intake_address} for chain {chain_id}")
        
        try:
            confirmed, unconfirmed = self.api.get_address_balance(intake_address)
            
            if confirmed > 0:
                logger.info(f"Chain {chain_id}: Funds received! {confirmed} sats confirmed")
                
                # Get transaction details
                txs = self.api.get_address_transactions(intake_address)
                txid = txs[0]['txid'] if txs else 'unknown'
                
                # Update chain with received amount
                update_chain_amounts(chain_id, amount_received_sats=confirmed)
                
                # Schedule first hop relay
                delay_blocks = first_hop['delay_blocks']
                relay_at_block = current_block + delay_blocks
                
                update_hop_funded(
                    hop_id=first_hop['id'],
                    incoming_txid=txid,
                    incoming_amount_sats=confirmed,
                    confirmed_at_block=current_block,
                    relay_at_block=relay_at_block
                )
                
                log_transaction(
                    chain_id=chain_id,
                    event_type='funds_received',
                    hop_id=first_hop['id'],
                    txid=txid,
                    amount_sats=confirmed,
                    block_height=current_block,
                    details=f"Relay scheduled for block {relay_at_block} (delay: {delay_blocks})"
                )
                
                logger.info(f"Chain {chain_id}: First relay scheduled for block {relay_at_block}")
                
            elif unconfirmed > 0:
                logger.info(f"Chain {chain_id}: {unconfirmed} sats pending confirmation")
                
        except Exception as e:
            logger.error(f"Error checking intake for chain {chain_id}: {e}")
    
    def _relay_hop(
        self,
        chain: Dict[str, Any],
        hop: Dict[str, Any],
        all_hops: List[Dict[str, Any]],
        current_block: int
    ):
        """
        Relay funds from one hop to the next.
        
        Args:
            chain: Chain data
            hop: Current hop data
            all_hops: All hops in the chain
            current_block: Current blockchain height
        """
        chain_id = chain['id']
        hop_id = hop['id']
        hop_number = hop['hop_number']
        
        logger.info(f"Chain {chain_id}: Relaying hop {hop_number + 1}")
        
        try:
            # Decrypt private key
            privkey = KeyEncryption.decrypt(hop['privkey_encrypted'], self.password)
            
            # Determine destination
            if hop_number < len(all_hops) - 1:
                # Send to next hop
                next_hop = all_hops[hop_number + 1]
                destination = next_hop['address']
                destination_type = f"hop {hop_number + 2}"
            else:
                # Final hop - send to final destination
                destination = chain['final_address']
                destination_type = "final destination"
            
            logger.info(f"Chain {chain_id}: Sending to {destination_type}")
            
            # Get fee estimate
            fees = self.api.get_fee_estimates()
            fee_sats = fees['medium'].estimated_fee_sats
            
            # Create and broadcast transaction
            tx_hex, amount_sent = self.wallet.create_transaction(
                wif=privkey,
                to_address=destination,
                amount_sats=0,  # Ignored with send_all
                fee_sats=fee_sats,
                send_all=True
            )
            
            txid = self.api.broadcast_transaction(tx_hex)
            
            logger.info(f"Chain {chain_id}: Broadcast tx {txid}, sent {amount_sent} sats")
            
            # Update current hop as relayed
            update_hop_relayed(
                hop_id=hop_id,
                outgoing_txid=txid,
                outgoing_amount_sats=amount_sent,
                outgoing_fee_sats=fee_sats
            )
            
            log_transaction(
                chain_id=chain_id,
                event_type='hop_relayed',
                hop_id=hop_id,
                txid=txid,
                amount_sats=amount_sent,
                fee_sats=fee_sats,
                block_height=current_block,
                details=f"Relayed to {destination_type}"
            )
            
            # If not final hop, update next hop
            if hop_number < len(all_hops) - 1:
                next_hop = all_hops[hop_number + 1]
                delay_blocks = next_hop['delay_blocks']
                relay_at_block = current_block + delay_blocks
                
                update_hop_funded(
                    hop_id=next_hop['id'],
                    incoming_txid=txid,
                    incoming_amount_sats=amount_sent,
                    confirmed_at_block=current_block,
                    relay_at_block=relay_at_block
                )
                
                logger.info(f"Chain {chain_id}: Next relay scheduled for block {relay_at_block}")
            
            # Update chain progress
            update_chain_amounts(chain_id, current_hop=hop_number + 1)
            
        except Exception as e:
            logger.error(f"Chain {chain_id}: Relay failed for hop {hop_number + 1}: {e}")
            
            update_hop_status(hop_id, 'failed')
            log_transaction(
                chain_id=chain_id,
                event_type='relay_failed',
                hop_id=hop_id,
                details=str(e)
            )
    
    def _is_chain_complete(self, hops: List[Dict[str, Any]]) -> bool:
        """Check if all hops have been relayed."""
        return all(h['status'] == 'relayed' for h in hops)
    
    def _complete_chain(self, chain: Dict[str, Any], hops: List[Dict[str, Any]]):
        """Mark a chain as completed."""
        chain_id = chain['id']
        
        # Calculate totals
        total_fees = sum(h.get('outgoing_fee_sats', 0) or 0 for h in hops)
        final_amount = hops[-1].get('outgoing_amount_sats', 0) if hops else 0
        
        update_chain_amounts(
            chain_id,
            amount_sent_sats=final_amount,
            total_fees_sats=total_fees
        )
        
        update_chain_status(chain_id, 'completed')
        
        log_transaction(
            chain_id=chain_id,
            event_type='chain_completed',
            amount_sats=final_amount,
            fee_sats=total_fees,
            details=f"Successfully relayed to {chain['final_address']}"
        )
        
        logger.info(
            f"Chain {chain_id}: COMPLETED! "
            f"Received: {chain.get('amount_received_sats', 0)} sats, "
            f"Sent: {final_amount} sats, "
            f"Fees: {total_fees} sats"
        )
