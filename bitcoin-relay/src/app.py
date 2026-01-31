"""
Bitcoin Relay - Personal Fund Privacy Tool
Main Flask application with web interface and API.
"""
import os
import json
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from functools import wraps

from .config import NETWORKS, MAX_HOPS, MIN_HOPS, SECRET_KEY
from .database import (
    init_database, get_master_password_hash, set_master_password_hash,
    get_active_network, set_active_network, create_relay_chain,
    get_relay_chain, get_all_relay_chains, update_chain_status,
    create_relay_hop, get_relay_hops, get_transaction_log, log_transaction
)
from .encryption import (
    KeyEncryption, generate_password_hash, verify_password_hash
)
from .bitcoin_utils import (
    BitcoinAPI, WalletManager, calculate_fibonacci_delays,
    estimate_total_fees, estimate_relay_timing
)
from .relay_engine import RelayEngine


def create_app():
    """Application factory."""
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.secret_key = SECRET_KEY
    
    # Initialize database
    init_database()
    
    # Global relay engine state
    app.relay_engine = None
    app.engine_lock = threading.Lock()
    
    def password_required(f):
        """Decorator to require password authentication."""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'password' not in session:
                return jsonify({'error': 'Authentication required'}), 401
            return f(*args, **kwargs)
        return decorated_function

    # ========================================================================
    # Web Interface Routes
    # ========================================================================

    @app.route('/')
    def index():
        """Main dashboard page."""
        return render_template('index.html')

    # ========================================================================
    # Authentication API
    # ========================================================================

    @app.route('/api/auth/status', methods=['GET'])
    def auth_status():
        """Check authentication status and if password is set."""
        password_hash = get_master_password_hash()
        return jsonify({
            'password_set': password_hash is not None,
            'authenticated': 'password' in session
        })

    @app.route('/api/auth/setup', methods=['POST'])
    def auth_setup():
        """Set up master password (first time only)."""
        if get_master_password_hash() is not None:
            return jsonify({'error': 'Password already set'}), 400
        
        data = request.json
        password = data.get('password')
        confirm = data.get('confirm')
        
        if not password or len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        
        if password != confirm:
            return jsonify({'error': 'Passwords do not match'}), 400
        
        # Store password hash
        password_hash = generate_password_hash(password)
        set_master_password_hash(password_hash)
        
        # Log user in
        session['password'] = password
        session.permanent = True
        
        return jsonify({'success': True})

    @app.route('/api/auth/login', methods=['POST'])
    def auth_login():
        """Authenticate with master password."""
        data = request.json
        password = data.get('password')
        
        if not password:
            return jsonify({'error': 'Password required'}), 400
        
        stored_hash = get_master_password_hash()
        if not stored_hash:
            return jsonify({'error': 'No password set - please set up first'}), 400
        
        if not verify_password_hash(password, stored_hash):
            return jsonify({'error': 'Invalid password'}), 401
        
        session['password'] = password
        session.permanent = True
        
        return jsonify({'success': True})

    @app.route('/api/auth/logout', methods=['POST'])
    def auth_logout():
        """Log out and clear session."""
        session.clear()
        return jsonify({'success': True})

    # ========================================================================
    # Network API
    # ========================================================================

    @app.route('/api/network', methods=['GET'])
    @password_required
    def get_network():
        """Get current network setting."""
        network = get_active_network()
        return jsonify({
            'network': network,
            'config': NETWORKS[network]
        })

    @app.route('/api/network', methods=['POST'])
    @password_required
    def switch_network():
        """Switch between testnet and mainnet."""
        data = request.json
        network = data.get('network')
        
        if network not in ('testnet', 'mainnet'):
            return jsonify({'error': 'Invalid network'}), 400
        
        set_active_network(network)
        
        # Restart relay engine with new network if running
        with app.engine_lock:
            if app.relay_engine and app.relay_engine.is_running:
                app.relay_engine.stop()
                app.relay_engine = RelayEngine(network, session['password'])
                app.relay_engine.start()
        
        return jsonify({
            'success': True,
            'network': network,
            'config': NETWORKS[network]
        })

    # ========================================================================
    # Fee Estimation API
    # ========================================================================

    @app.route('/api/fees', methods=['GET'])
    @password_required
    def get_fees():
        """Get current fee estimates."""
        network = get_active_network()
        api = BitcoinAPI(network)
        
        try:
            fees = api.get_fee_estimates()
            return jsonify({
                'network': network,
                'estimates': {
                    k: {
                        'fee_rate_sat_vb': v.fee_rate_sat_vb,
                        'estimated_fee_sats': v.estimated_fee_sats,
                        'priority': v.priority
                    }
                    for k, v in fees.items()
                }
            })
        except Exception as e:
            return jsonify({'error': f'Failed to get fee estimates: {str(e)}'}), 500

    @app.route('/api/fees/estimate', methods=['POST'])
    @password_required
    def estimate_fees_route():
        """Estimate total fees for a relay chain."""
        data = request.json
        num_hops = data.get('num_hops', 3)
        fee_priority = data.get('fee_priority', 'medium')
        
        if num_hops < MIN_HOPS or num_hops > MAX_HOPS:
            return jsonify({'error': f'Hops must be between {MIN_HOPS} and {MAX_HOPS}'}), 400
        
        network = get_active_network()
        api = BitcoinAPI(network)
        
        try:
            fees = api.get_fee_estimates()
            if fee_priority not in fees:
                fee_priority = 'medium'
            
            fee_estimate = fees[fee_priority]
            fee_breakdown = estimate_total_fees(num_hops, fee_estimate)
            timing = estimate_relay_timing(num_hops)
            
            return jsonify({
                'network': network,
                'num_hops': num_hops,
                'fee_priority': fee_priority,
                'fees': fee_breakdown,
                'timing': timing
            })
        except Exception as e:
            return jsonify({'error': f'Failed to estimate fees: {str(e)}'}), 500

    # ========================================================================
    # Chain Management API
    # ========================================================================

    @app.route('/api/chains', methods=['GET'])
    @password_required
    def list_chains():
        """List all relay chains."""
        network = request.args.get('network', get_active_network())
        chains = get_all_relay_chains(network)
        
        # Add hop information
        for chain in chains:
            chain['hops'] = get_relay_hops(chain['id'])
        
        return jsonify({
            'network': network,
            'chains': chains
        })

    @app.route('/api/chains', methods=['POST'])
    @password_required
    def create_chain_route():
        """Create a new relay chain."""
        data = request.json
        password = session['password']
        
        name = data.get('name', f"Relay {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        num_hops = data.get('num_hops', 3)
        final_address = data.get('final_address')
        fee_priority = data.get('fee_priority', 'medium')
        dry_run = data.get('dry_run', False)
        
        # Validation
        if num_hops < MIN_HOPS or num_hops > MAX_HOPS:
            return jsonify({'error': f'Hops must be between {MIN_HOPS} and {MAX_HOPS}'}), 400
        
        network = get_active_network()
        wallet = WalletManager(network)
        
        # Validate final address if provided
        if final_address:
            if not wallet.validate_address(final_address):
                return jsonify({'error': 'Invalid final address for this network'}), 400
        
        try:
            # Generate intake address
            intake_address, intake_privkey = wallet.generate_key_pair()
            intake_privkey_enc = KeyEncryption.encrypt(intake_privkey, password)
            
            # Generate or use final address
            final_is_generated = False
            final_privkey_enc = None
            
            if not final_address:
                final_address, final_privkey = wallet.generate_key_pair()
                final_privkey_enc = KeyEncryption.encrypt(final_privkey, password)
                final_is_generated = True
            
            # Calculate delays
            delays = calculate_fibonacci_delays(num_hops)
            
            if dry_run:
                return jsonify({
                    'dry_run': True,
                    'network': network,
                    'name': name,
                    'intake_address': intake_address,
                    'final_address': final_address,
                    'final_is_generated': final_is_generated,
                    'num_hops': num_hops,
                    'delays': delays
                })
            
            # Create chain in database
            chain_id = create_relay_chain(
                name=name,
                network=network,
                intake_address=intake_address,
                intake_privkey_encrypted=intake_privkey_enc,
                final_address=final_address,
                final_is_generated=final_is_generated,
                final_privkey_encrypted=final_privkey_enc,
                total_hops=num_hops
            )
            
            # Create intermediate hops
            hop_addresses = []
            for i in range(num_hops):
                hop_address, hop_privkey = wallet.generate_key_pair()
                hop_privkey_enc = KeyEncryption.encrypt(hop_privkey, password)
                
                create_relay_hop(
                    chain_id=chain_id,
                    hop_number=i,
                    address=hop_address,
                    privkey_encrypted=hop_privkey_enc,
                    delay_blocks=delays[i]
                )
                
                hop_addresses.append({
                    'hop_number': i,
                    'address': hop_address,
                    'delay_blocks': delays[i]
                })
            
            # Log creation
            log_transaction(
                chain_id=chain_id,
                event_type='chain_created',
                details=json.dumps({
                    'num_hops': num_hops,
                    'fee_priority': fee_priority
                })
            )
            
            # Get fee estimate
            api = BitcoinAPI(network)
            fees = api.get_fee_estimates()
            fee_estimate = fees.get(fee_priority, fees['medium'])
            fee_breakdown = estimate_total_fees(num_hops, fee_estimate)
            timing = estimate_relay_timing(num_hops)
            
            return jsonify({
                'success': True,
                'chain_id': chain_id,
                'network': network,
                'name': name,
                'intake_address': intake_address,
                'final_address': final_address,
                'final_is_generated': final_is_generated,
                'hops': hop_addresses,
                'fees': fee_breakdown,
                'timing': timing
            })
            
        except Exception as e:
            return jsonify({'error': f'Failed to create chain: {str(e)}'}), 500

    @app.route('/api/chains/<int:chain_id>', methods=['GET'])
    @password_required
    def get_chain_route(chain_id):
        """Get details of a specific chain."""
        chain = get_relay_chain(chain_id)
        if not chain:
            return jsonify({'error': 'Chain not found'}), 404
        
        chain['hops'] = get_relay_hops(chain_id)
        chain['log'] = get_transaction_log(chain_id)
        
        return jsonify(chain)

    @app.route('/api/chains/<int:chain_id>/cancel', methods=['POST'])
    @password_required
    def cancel_chain_route(chain_id):
        """Cancel a pending chain."""
        chain = get_relay_chain(chain_id)
        if not chain:
            return jsonify({'error': 'Chain not found'}), 404
        
        if chain['status'] not in ('pending', 'active'):
            return jsonify({'error': 'Can only cancel pending or active chains'}), 400
        
        update_chain_status(chain_id, 'cancelled')
        log_transaction(chain_id, 'chain_cancelled')
        
        return jsonify({'success': True})

    @app.route('/api/chains/<int:chain_id>/activate', methods=['POST'])
    @password_required
    def activate_chain_route(chain_id):
        """Activate a pending chain (start monitoring for funds)."""
        chain = get_relay_chain(chain_id)
        if not chain:
            return jsonify({'error': 'Chain not found'}), 404
        
        if chain['status'] != 'pending':
            return jsonify({'error': 'Can only activate pending chains'}), 400
        
        update_chain_status(chain_id, 'active')
        log_transaction(chain_id, 'chain_activated')
        
        # Ensure relay engine is running
        with app.engine_lock:
            if app.relay_engine is None or not app.relay_engine.is_running:
                app.relay_engine = RelayEngine(chain['network'], session['password'])
                app.relay_engine.start()
        
        return jsonify({'success': True})

    # ========================================================================
    # Wallet API
    # ========================================================================

    @app.route('/api/address/validate', methods=['POST'])
    @password_required
    def validate_address_route():
        """Validate a Bitcoin address."""
        data = request.json
        address = data.get('address')
        
        if not address:
            return jsonify({'error': 'Address required'}), 400
        
        network = get_active_network()
        wallet = WalletManager(network)
        
        return jsonify({
            'address': address,
            'valid': wallet.validate_address(address),
            'network': network
        })

    @app.route('/api/address/balance', methods=['POST'])
    @password_required
    def get_balance_route():
        """Get balance for an address."""
        data = request.json
        address = data.get('address')
        
        if not address:
            return jsonify({'error': 'Address required'}), 400
        
        network = get_active_network()
        api = BitcoinAPI(network)
        
        try:
            confirmed, unconfirmed = api.get_address_balance(address)
            return jsonify({
                'address': address,
                'confirmed_sats': confirmed,
                'unconfirmed_sats': unconfirmed,
                'total_sats': confirmed + unconfirmed,
                'network': network
            })
        except Exception as e:
            return jsonify({'error': f'Failed to get balance: {str(e)}'}), 500

    # ========================================================================
    # Status API
    # ========================================================================

    @app.route('/api/status', methods=['GET'])
    @password_required
    def get_status():
        """Get current relay engine status."""
        network = get_active_network()
        api = BitcoinAPI(network)
        
        try:
            block_height = api.get_block_height()
        except:
            block_height = None
        
        engine_running = app.relay_engine is not None and app.relay_engine.is_running
        
        # Count chains
        chains = get_all_relay_chains(network)
        active_chains = sum(1 for c in chains if c['status'] == 'active')
        pending_chains = sum(1 for c in chains if c['status'] == 'pending')
        
        return jsonify({
            'network': network,
            'block_height': block_height,
            'engine_running': engine_running,
            'active_chains': active_chains,
            'pending_chains': pending_chains
        })

    @app.route('/api/engine/start', methods=['POST'])
    @password_required
    def start_engine():
        """Start the relay engine."""
        with app.engine_lock:
            if app.relay_engine is not None and app.relay_engine.is_running:
                return jsonify({'error': 'Engine already running'}), 400
            
            network = get_active_network()
            app.relay_engine = RelayEngine(network, session['password'])
            app.relay_engine.start()
        
        return jsonify({'success': True})

    @app.route('/api/engine/stop', methods=['POST'])
    @password_required
    def stop_engine():
        """Stop the relay engine."""
        with app.engine_lock:
            if app.relay_engine is None or not app.relay_engine.is_running:
                return jsonify({'error': 'Engine not running'}), 400
            
            app.relay_engine.stop()
        
        return jsonify({'success': True})

    # ========================================================================
    # Export API
    # ========================================================================

    @app.route('/api/chains/<int:chain_id>/export', methods=['GET'])
    @password_required
    def export_chain_keys(chain_id):
        """Export private keys for a chain (for backup)."""
        chain = get_relay_chain(chain_id)
        if not chain:
            return jsonify({'error': 'Chain not found'}), 404
        
        password = session['password']
        
        try:
            keys = {
                'chain_id': chain_id,
                'name': chain['name'],
                'network': chain['network'],
                'intake_address': chain['intake_address'],
                'intake_privkey': KeyEncryption.decrypt(chain['intake_privkey_encrypted'], password),
                'final_address': chain['final_address'],
            }
            
            if chain['final_is_generated'] and chain['final_privkey_encrypted']:
                keys['final_privkey'] = KeyEncryption.decrypt(chain['final_privkey_encrypted'], password)
            
            hops = get_relay_hops(chain_id)
            keys['hops'] = []
            for hop in hops:
                keys['hops'].append({
                    'hop_number': hop['hop_number'],
                    'address': hop['address'],
                    'privkey': KeyEncryption.decrypt(hop['privkey_encrypted'], password)
                })
            
            return jsonify(keys)
            
        except Exception as e:
            return jsonify({'error': f'Failed to export keys: {str(e)}'}), 500

    return app


# Create the application instance
app = create_app()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
