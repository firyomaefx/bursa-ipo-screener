#!/usr/bin/env python3
"""
Payment gateway for IPO reports — Stripe Checkout integration.
Handles payment session creation and verification.
"""

import os, json, hmac, hashlib
from datetime import datetime

try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False

REPORTS_DIR = os.path.join(os.path.dirname(__file__), 'reports')
PAYMENT_LOG = os.path.join(os.path.dirname(__file__), 'payment_log.json')

DEFAULT_PRICE_RM = 30  # RM per report
DEFAULT_PRICE_CENTS = DEFAULT_PRICE_RM * 100  # Stripe uses cents/sen

def get_stripe_key():
    """Get Stripe secret key from environment or Streamlit secrets."""
    key = os.environ.get('STRIPE_SECRET_KEY')
    if not key:
        try:
            import streamlit as st
            if hasattr(st, 'secrets') and 'STRIPE_SECRET_KEY' in st.secrets:
                key = st.secrets['STRIPE_SECRET_KEY']
        except Exception:
            pass
    return key

def get_publishable_key():
    """Get Stripe publishable key."""
    key = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    if not key:
        try:
            import streamlit as st
            if hasattr(st, 'secrets') and 'STRIPE_PUBLISHABLE_KEY' in st.secrets:
                key = st.secrets['STRIPE_PUBLISHABLE_KEY']
        except Exception:
            pass
    return key

def create_checkout_session(ipo_data, success_url, cancel_url, price_cents=DEFAULT_PRICE_CENTS):
    """
    Create a Stripe Checkout Session for an IPO report.
    
    Args:
        ipo_data: dict with company_name, ticker, alpha_score
        success_url: URL to redirect on successful payment (include {CHECKOUT_SESSION_ID})
        cancel_url: URL to redirect on cancellation
        price_cents: price in cents/sen (RM 30 = 3000)
    
    Returns:
        Stripe Checkout Session object, or None if Stripe not configured
    """
    key = get_stripe_key()
    if not key or not STRIPE_AVAILABLE:
        return None
    
    stripe.api_key = key
    company = ipo_data.get('company_name', 'IPO')
    ticker = ipo_data.get('ticker', '')
    
    session = stripe.checkout.Session.create(
        line_items=[{
            'price_data': {
                'currency': 'myr',
                'product_data': {
                    'name': f'{company} ({ticker}) — IPO Equity Research Report',
                    'description': f'30-page institutional-grade PDF report. Alpha Score: {ipo_data.get("alpha_score", 0):.0f}/100 · {ipo_data.get("verdict", "N/A")}',
                    'images': [],  # Could add chart image URL
                },
                'unit_amount': price_cents,
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            'company': company,
            'ticker': ticker,
            'alpha_score': str(ipo_data.get('alpha_score', 0)),
            'type': 'ipo_report'
        },
    )
    
    # Log the payment attempt
    _log_payment(session.id, company, ticker, 'created')
    
    return session

def verify_payment(session_id):
    """
    Verify that a Stripe Checkout Session was paid successfully.
    
    Args:
        session_id: Stripe Checkout Session ID
    
    Returns:
        dict with verified=True/False and metadata if paid
    """
    key = get_stripe_key()
    if not key or not STRIPE_AVAILABLE:
        return {'verified': False, 'error': 'Stripe not configured'}
    
    stripe.api_key = key
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == 'paid':
            _log_payment(session.id, session.metadata.get('company', 'Unknown'),
                         session.metadata.get('ticker', ''), 'paid')
            return {
                'verified': True,
                'company': session.metadata.get('company'),
                'ticker': session.metadata.get('ticker'),
                'amount': session.amount_total / 100,
                'currency': session.currency,
                'payment_intent': session.payment_intent,
            }
        else:
            return {'verified': False, 'status': session.payment_status}
    except Exception as e:
        return {'verified': False, 'error': str(e)}

def _log_payment(session_id, company, ticker, status):
    """Log payment event to JSON file."""
    try:
        log = []
        if os.path.exists(PAYMENT_LOG):
            with open(PAYMENT_LOG, 'r') as f:
                log = json.load(f)
        log.append({
            'session_id': session_id,
            'company': company,
            'ticker': ticker,
            'status': status,
            'timestamp': datetime.now().isoformat(),
        })
        with open(PAYMENT_LOG, 'w') as f:
            json.dump(log, f, indent=2)
    except Exception:
        pass  # Don't fail if log can't be written

def check_stripe_config():
    """Check if Stripe is properly configured."""
    key = get_stripe_key()
    pub_key = get_publishable_key()
    if not key:
        return False, "Stripe secret key not configured"
    if not pub_key:
        return False, "Stripe publishable key not configured"
    if not STRIPE_AVAILABLE:
        return False, "stripe package not installed"
    return True, "Stripe ready"

def set_price_rm(price_rm):
    """Set the price per report in Ringgit Malaysia."""
    return int(price_rm * 100)
