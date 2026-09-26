"""
Stand-in for the sandbox/test-mode Nigerian payment gateway integration
described in Section 3.15 and 4.2 (Paystack / Flutterwave test API keys).

Section 1.5 scopes the project to a sandboxed integration rather than
live money movement, so this module simulates gateway charge/webhook
behaviour deterministically enough for testing while remaining a drop-in
seam: swapping this module for a real Paystack/Flutterwave SDK client
does not require touching payments/routes.py.
"""
import random
import time
import uuid
from dataclasses import dataclass

from flask import current_app


@dataclass
class GatewayResponse:
    ok: bool
    reference: str
    message: str


def charge(amount: float, method: str, reference: str) -> GatewayResponse:
    """Simulate submitting a capture request to the sandbox gateway."""
    latency = current_app.config.get("GATEWAY_LATENCY_SECONDS", 0.0)
    if latency:
        time.sleep(latency)

    failure_rate = current_app.config.get("GATEWAY_SIMULATED_FAILURE_RATE", 0.0)
    succeeded = random.random() >= failure_rate

    gateway_ref = f"sbx_{uuid.uuid4().hex[:16]}"
    if succeeded:
        return GatewayResponse(ok=True, reference=gateway_ref, message="Charge successful (sandbox)")
    return GatewayResponse(ok=False, reference=gateway_ref, message="Charge declined (sandbox)")
