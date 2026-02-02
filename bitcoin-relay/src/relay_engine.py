"""
Relay Engine - Background worker that monitors blocks and processes relays.
Includes auto-recovery for stuck/failed chains.
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
    update_hop_status, get_relay_chain
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
    Includes auto-recovery for stuck or failed transactions.
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
        self.last_error: Optional[str] = None
        self.processing_status: Dict[int, str] = {}  # chain_id -> status message
        
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
    
    def get_status(self) -> Dict[str, Any]:
        """Get current engine status for UI."""
        return {
            'running': self.is_running,
            'network': self.network,
            'last_error': self.last_error,
            'processing': self.processing_status.copy()
        }
    
    def _run(self):
        """Main engine loop."""
        logger.info("Relay engine loop started")
        
        while not self._stop_event.is_set():
            try:
                self._process_cycle()
                self.last_error = None
            except Exception as e:
                self.last_error = str(e)
                logger.error(f"Error in relay cycle: {e}", exc_info=True)
            
            # Wait before next poll (check every 30 seconds for faster response)
            self._stop_event.wait(30)
        
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
                self.processing_status[chain['id']] = f"Error: {str(e)}"
        
        # Update tracked block height
        update_block_height(self.network, current_block)
    
    def _process_chain(self, chain: Dict[str, Any], current_block: int):
        """Process a single relay chain with auto-recovery."""
        chain_id = chain['id']
        hops = get_relay_hops(chain_id)
        
        if not hops:
            logger.warning(f"Chain {chain_id} has no hops")
            return
        
        self.processing_status[chain_id] = "Checking..."
        
        # Step 1: Check intake address for funds
        intake_balance = self.api.get_address_balance(chain['intake_address'])
        intake_confirmed = intake_balance[0]
        
        # Step 2: Find where funds currently are and relay them
        funds_location = self._find_funds_location(chain, hops)
        
        if funds_location:
            location_type, location_data, balance = funds_location
            self.processing_status[chain_id] = f"Funds at {location_type}: {balance} sats"
            
            # Attempt to relay from current location
            self._relay_from_location(chain, hops, location_type, location_data, balance, current_block)
        else:
            # No funds found anywhere - check if chain is complete
            final_balance = self.api.get_address_balance(chain['final_address'])
            if final_balance[0] > 0 or final_balance[1] > 0:
                self._complete_chain(chain, hops)
            elif intake_confirmed == 0 and intake_balance[1] == 0:
                self.processing_status[chain_id] = "Waiting for funds at intake"
            else:
                self.processing_status[chain_id] = "Funds in transit"
    
    def _find_funds_location(self, chain: Dict, hops: List[Dict]) -> Optional[tuple]:
        """
        Find where the funds currently are in the relay chain.
        Returns: (location_type, location_data, confirmed_balance) or None
        """
        # Check intake address first
        intake_balance = self.api.get_address_balance(chain['intake_address'])
        if intake_balance[0] > 0:  # Confirmed balance at intake
            return ('intake', chain, intake_balance[0])
        
        # Check each hop
        for i, hop in enumerate(hops):
            hop_balance = self.api.get_address_balance(hop['address'])
            if hop_balance[0] > 0:  # Confirmed balance
                return (f'hop_{i+1}', hop, hop_balance[0])
        
        return None
    
    def _relay_from_location(self, chain: Dict, hops: List[Dict], 
                             location_type: str, location_data: Dict,
                             balance: int, current_block: int):
        """Relay funds from their current location to the next destination."""
        chain_id = chain['id']
        
        try:
            # Determine source and destination
            if location_type == 'intake':
                # Relay from intake to first hop
                source_privkey_enc = chain['intake_privkey_encrypted']
                destination = hops[0]['address']
                dest_hop_index = 0
                desc = "Intake -> Hop 1"
            else:
                # Relay from hop N to hop N+1 or final
                hop_index = int(location_type.split('_')[1]) - 1
                source_privkey_enc = hops[hop_index]['privkey_encrypted']
                
                if hop_index < len(hops) - 1:
                    destination = hops[hop_index + 1]['address']
                    dest_hop_index = hop_index + 1
                    desc = f"Hop {hop_index + 1} -> Hop {hop_index + 2}"
                else:
                    destination = chain['final_address']
                    dest_hop_index = -1  # Final destination
                    desc = f"Hop {hop_index + 1} -> Final"
            
            self.processing_status[chain_id] = f"Relaying: {desc}"
            logger.info(f"Chain {chain_id}: {desc}")
            
            # Decrypt private key
            privkey = KeyEncryption.decrypt(source_privkey_enc, self.password)
            
            # Get fee estimate
            fees = self.api.get_fee_estimates()
            fee_sats = max(fees['medium'].estimated_fee_sats, 200)  # Minimum 200 sats
            
            # Create and broadcast transaction
            key = self.wallet.get_key_from_wif(privkey)
            actual_balance = int(key.get_balance('satoshi'))
            
            if actual_balance <= fee_sats:
                logger.warning(f"Chain {chain_id}: Insufficient balance ({actual_balance}) for fee ({fee_sats})")
                self.processing_status[chain_id] = f"Insufficient balance: {actual_balance} sats"
                return
            
            amount_to_send = actual_balance - fee_sats
            
            outputs = [(destination, amount_to_send, 'satoshi')]
            tx_hex = key.create_transaction(outputs, fee=fee_sats, absolute_fee=True)
            txid = self.api.broadcast_transaction(tx_hex)
            
            logger.info(f"Chain {chain_id}: Broadcast {desc} - TXID: {txid}")
            self.processing_status[chain_id] = f"Sent: {desc} ({amount_to_send} sats)"
            
            # Update database
            if location_type == 'intake':
                # Update chain received amount
                update_chain_amounts(chain_id, amount_received_sats=actual_balance)
                
                # Update first hop as funded
                update_hop_funded(
                    hop_id=hops[0]['id'],
                    incoming_txid=txid,
                    incoming_amount_sats=amount_to_send,
                    confirmed_at_block=current_block,
                    relay_at_block=current_block
                )
            else:
                hop_index = int(location_type.split('_')[1]) - 1
                
                # Update source hop as relayed
                update_hop_relayed(
                    hop_id=hops[hop_index]['id'],
                    outgoing_txid=txid,
                    outgoing_amount_sats=amount_to_send,
                    outgoing_fee_sats=fee_sats
                )
                
                # Update destination hop as funded (if not final)
                if dest_hop_index >= 0:
                    update_hop_funded(
                        hop_id=hops[dest_hop_index]['id'],
                        incoming_txid=txid,
                        incoming_amount_sats=amount_to_send,
                        confirmed_at_block=current_block,
                        relay_at_block=current_block
                    )
                
                # Update chain progress
                update_chain_amounts(chain_id, current_hop=hop_index + 1)
            
            # Log transaction
            log_transaction(
                chain_id=chain_id,
                event_type='relay_sent',
                txid=txid,
                amount_sats=amount_to_send,
                fee_sats=fee_sats,
                block_height=current_block,
                details=desc
            )
            
            # Check if this was the final relay
            if dest_hop_index == -1:
                self._complete_chain(chain, hops)
            
        except Exception as e:
            logger.error(f"Chain {chain_id}: Relay failed - {e}")
            self.processing_status[chain_id] = f"Relay failed: {str(e)[:50]}"
            
            log_transaction(
                chain_id=chain_id,
                event_type='relay_error',
                details=str(e)
            )
    
    def _complete_chain(self, chain: Dict, hops: List[Dict]):
        """Mark a chain as completed."""
        chain_id = chain['id']
        
        # Calculate totals
        total_fees = sum(h.get('outgoing_fee_sats', 0) or 0 for h in hops)
        
        # Get final amount from last hop or final destination
        final_balance = self.api.get_address_balance(chain['final_address'])
        final_amount = final_balance[0] + final_balance[1]
        
        if final_amount == 0:
            # Try to get from last hop's outgoing amount
            for hop in reversed(hops):
                if hop.get('outgoing_amount_sats'):
                    final_amount = hop['outgoing_amount_sats']
                    break
        
        update_chain_amounts(
            chain_id,
            amount_sent_sats=final_amount,
            total_fees_sats=total_fees
        )
        
        update_chain_status(chain_id, 'completed')
        
        # Mark all hops as relayed
        for hop in hops:
            if hop['status'] != 'relayed':
                update_hop_status(hop['id'], 'relayed')
        
        log_transaction(
            chain_id=chain_id,
            event_type='chain_completed',
            amount_sats=final_amount,
            fee_sats=total_fees,
            details=f"Successfully relayed to {chain['final_address']}"
        )
        
        self.processing_status[chain_id] = "COMPLETED"
        
        logger.info(
            f"Chain {chain_id}: COMPLETED! "
            f"Received: {chain.get('amount_received_sats', 0)} sats, "
            f"Sent: {final_amount} sats, "
            f"Fees: {total_fees} sats"
        )


def manual_relay_chain(chain_id: int, password: str) -> Dict[str, Any]:
    """
    Manually process all pending relays for a chain.
    Useful for recovering stuck chains.
    
    Returns dict with results of each relay attempt.
    """
    from .database import get_relay_chain, get_relay_hops
    
    chain = get_relay_chain(chain_id)
    if not chain:
        return {'error': 'Chain not found'}
    
    hops = get_relay_hops(chain_id)
    if not hops:
        return {'error': 'No hops found'}
    
    api = BitcoinAPI(chain['network'])
    wallet = WalletManager(chain['network'])
    
    results = []
    current_block = api.get_block_height()
    
    # Find funds and relay through entire chain
    addresses = [
        ('intake', chain['intake_address'], chain['intake_privkey_encrypted']),
    ]
    for i, hop in enumerate(hops):
        addresses.append((f'hop_{i+1}', hop['address'], hop['privkey_encrypted']))
    
    # Determine destinations
    destinations = [hops[0]['address']]  # intake -> hop1
    for i in range(len(hops) - 1):
        destinations.append(hops[i + 1]['address'])  # hopN -> hopN+1
    destinations.append(chain['final_address'])  # last hop -> final
    
    for i, (name, address, privkey_enc) in enumerate(addresses):
        balance = api.get_address_balance(address)
        confirmed = balance[0]
        
        if confirmed > 0:
            try:
                privkey = KeyEncryption.decrypt(privkey_enc, password)
                key = wallet.get_key_from_wif(privkey)
                actual_balance = int(key.get_balance('satoshi'))
                
                fee = 200
                amount = actual_balance - fee
                
                if amount <= 0:
                    results.append({
                        'step': name,
                        'status': 'skipped',
                        'reason': f'Insufficient balance: {actual_balance}'
                    })
                    continue
                
                destination = destinations[i]
                outputs = [(destination, amount, 'satoshi')]
                tx_hex = key.create_transaction(outputs, fee=fee, absolute_fee=True)
                txid = api.broadcast_transaction(tx_hex)
                
                results.append({
                    'step': name,
                    'status': 'success',
                    'txid': txid,
                    'amount': amount,
                    'destination': destination
                })
                
                # Update database
                if name == 'intake':
                    update_chain_amounts(chain_id, amount_received_sats=actual_balance)
                    update_hop_funded(
                        hop_id=hops[0]['id'],
                        incoming_txid=txid,
                        incoming_amount_sats=amount,
                        confirmed_at_block=current_block,
                        relay_at_block=current_block
                    )
                else:
                    hop_index = int(name.split('_')[1]) - 1
                    update_hop_relayed(
                        hop_id=hops[hop_index]['id'],
                        outgoing_txid=txid,
                        outgoing_amount_sats=amount,
                        outgoing_fee_sats=fee
                    )
                    if hop_index < len(hops) - 1:
                        update_hop_funded(
                            hop_id=hops[hop_index + 1]['id'],
                            incoming_txid=txid,
                            incoming_amount_sats=amount,
                            confirmed_at_block=current_block,
                            relay_at_block=current_block
                        )
                
                log_transaction(
                    chain_id=chain_id,
                    event_type='manual_relay',
                    txid=txid,
                    amount_sats=amount,
                    fee_sats=fee,
                    block_height=current_block,
                    details=f"Manual relay from {name}"
                )
                
            except Exception as e:
                results.append({
                    'step': name,
                    'status': 'error',
                    'error': str(e)
                })
        else:
            results.append({
                'step': name,
                'status': 'no_funds',
                'balance': balance
            })
    
    return {'chain_id': chain_id, 'results': results}
