# API Documentation

Bitcoin Relay provides a RESTful API for managing relay chains programmatically.

## Authentication

All endpoints (except `/api/auth/*`) require authentication. After logging in, the session is maintained via cookies.

### Check Auth Status

```http
GET /api/auth/status
```

**Response:**
```json
{
  "password_set": true,
  "authenticated": false
}
```

### Setup Password (First Time)

```http
POST /api/auth/setup
Content-Type: application/json

{
  "password": "your-secure-password",
  "confirm": "your-secure-password"
}
```

**Response:**
```json
{
  "success": true
}
```

### Login

```http
POST /api/auth/login
Content-Type: application/json

{
  "password": "your-secure-password"
}
```

**Response:**
```json
{
  "success": true
}
```

### Logout

```http
POST /api/auth/logout
```

**Response:**
```json
{
  "success": true
}
```

---

## Network

### Get Current Network

```http
GET /api/network
```

**Response:**
```json
{
  "network": "testnet",
  "config": {
    "name": "Bitcoin Testnet",
    "api_base": "https://blockstream.info/testnet/api",
    "explorer_base": "https://blockstream.info/testnet",
    "min_confirmations": 1,
    "dust_threshold": 546
  }
}
```

### Switch Network

```http
POST /api/network
Content-Type: application/json

{
  "network": "mainnet"
}
```

**Response:**
```json
{
  "success": true,
  "network": "mainnet",
  "config": { ... }
}
```

---

## Fee Estimation

### Get Current Fee Estimates

```http
GET /api/fees
```

**Response:**
```json
{
  "network": "testnet",
  "estimates": {
    "high": {
      "fee_rate_sat_vb": 20,
      "estimated_fee_sats": 2200,
      "priority": "high"
    },
    "medium": {
      "fee_rate_sat_vb": 10,
      "estimated_fee_sats": 1100,
      "priority": "medium"
    },
    "low": {
      "fee_rate_sat_vb": 5,
      "estimated_fee_sats": 550,
      "priority": "low"
    },
    "economy": {
      "fee_rate_sat_vb": 2,
      "estimated_fee_sats": 220,
      "priority": "economy"
    }
  }
}
```

### Estimate Total Fees for Chain

```http
POST /api/fees/estimate
Content-Type: application/json

{
  "num_hops": 5,
  "fee_priority": "medium"
}
```

**Response:**
```json
{
  "network": "testnet",
  "num_hops": 5,
  "fee_priority": "medium",
  "fees": {
    "fee_rate_sat_vb": 10,
    "fee_per_transaction_sats": 1100,
    "num_transactions": 6,
    "total_fees_sats": 6600,
    "priority": "medium"
  },
  "timing": {
    "delays_per_hop": [1, 1, 2, 3, 5],
    "total_delay_blocks": 12,
    "estimated_minutes": 120,
    "estimated_hours": 2.0,
    "estimated_days": 0.08
  }
}
```

---

## Chain Management

### List All Chains

```http
GET /api/chains
GET /api/chains?network=testnet
```

**Response:**
```json
{
  "network": "testnet",
  "chains": [
    {
      "id": 1,
      "name": "My Relay",
      "network": "testnet",
      "status": "pending",
      "intake_address": "tb1q...",
      "final_address": "tb1q...",
      "total_hops": 5,
      "current_hop": 0,
      "amount_received_sats": null,
      "amount_sent_sats": null,
      "total_fees_sats": 0,
      "created_at": "2025-01-15T10:30:00",
      "hops": [...]
    }
  ]
}
```

### Create New Chain

```http
POST /api/chains
Content-Type: application/json

{
  "name": "My Relay Chain",
  "num_hops": 5,
  "final_address": "tb1q...",  // optional
  "fee_priority": "medium",
  "dry_run": false
}
```

**Response:**
```json
{
  "success": true,
  "chain_id": 1,
  "network": "testnet",
  "name": "My Relay Chain",
  "intake_address": "tb1qxyz...",
  "final_address": "tb1qabc...",
  "final_is_generated": true,
  "hops": [
    {
      "hop_number": 0,
      "address": "tb1q...",
      "delay_blocks": 1
    },
    ...
  ],
  "fees": { ... },
  "timing": { ... }
}
```

### Get Chain Details

```http
GET /api/chains/1
```

**Response:**
```json
{
  "id": 1,
  "name": "My Relay Chain",
  "network": "testnet",
  "status": "active",
  "intake_address": "tb1q...",
  "final_address": "tb1q...",
  "total_hops": 5,
  "current_hop": 2,
  "amount_received_sats": 100000,
  "amount_sent_sats": null,
  "total_fees_sats": 2200,
  "hops": [...],
  "log": [
    {
      "id": 1,
      "chain_id": 1,
      "event_type": "chain_created",
      "created_at": "2025-01-15T10:30:00"
    },
    ...
  ]
}
```

### Activate Chain

```http
POST /api/chains/1/activate
```

**Response:**
```json
{
  "success": true
}
```

### Cancel Chain

```http
POST /api/chains/1/cancel
```

**Response:**
```json
{
  "success": true
}
```

### Export Chain Keys

```http
GET /api/chains/1/export
```

**Response:**
```json
{
  "chain_id": 1,
  "name": "My Relay Chain",
  "network": "testnet",
  "intake_address": "tb1q...",
  "intake_privkey": "cN...",
  "final_address": "tb1q...",
  "final_privkey": "cN...",
  "hops": [
    {
      "hop_number": 0,
      "address": "tb1q...",
      "privkey": "cN..."
    },
    ...
  ]
}
```

---

## Address Utilities

### Validate Address

```http
POST /api/address/validate
Content-Type: application/json

{
  "address": "tb1qxyz..."
}
```

**Response:**
```json
{
  "address": "tb1qxyz...",
  "valid": true,
  "network": "testnet"
}
```

### Get Address Balance

```http
POST /api/address/balance
Content-Type: application/json

{
  "address": "tb1qxyz..."
}
```

**Response:**
```json
{
  "address": "tb1qxyz...",
  "confirmed_sats": 100000,
  "unconfirmed_sats": 0,
  "total_sats": 100000,
  "network": "testnet"
}
```

---

## Engine Control

### Get Status

```http
GET /api/status
```

**Response:**
```json
{
  "network": "testnet",
  "block_height": 2500000,
  "engine_running": true,
  "active_chains": 2,
  "pending_chains": 1
}
```

### Start Engine

```http
POST /api/engine/start
```

**Response:**
```json
{
  "success": true
}
```

### Stop Engine

```http
POST /api/engine/stop
```

**Response:**
```json
{
  "success": true
}
```

---

## Error Responses

All endpoints return errors in this format:

```json
{
  "error": "Error message describing what went wrong"
}
```

Common HTTP status codes:
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (not authenticated)
- `404` - Not Found (chain doesn't exist)
- `500` - Internal Server Error
