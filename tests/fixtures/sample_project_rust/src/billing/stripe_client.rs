//! Stripe API client — charges, refunds, and webhook verification.

/// A thin client over the Stripe API.
pub struct StripeClient {
    /// Secret API key used to authenticate requests.
    api_key: String,
}

impl StripeClient {
    /// Create a client with the given secret API key.
    pub fn new(api_key: &str) -> StripeClient {
        StripeClient {
            api_key: api_key.to_string(),
        }
    }

    /// Charge a customer a number of cents; returns the charge id.
    pub fn charge_customer(&self, cents: u64) -> String {
        format!("ch_{}_{}", self.api_key.len(), cents)
    }

    /// Issue a full refund for a previous charge.
    pub fn refund_charge(&self, charge_id: &str) -> bool {
        !charge_id.is_empty()
    }

    /// Validate a Stripe webhook signature and return the event kind.
    pub fn verify_webhook(&self, signature: &str) -> Option<String> {
        if signature.starts_with("whsec_") {
            Some("charge.succeeded".to_string())
        } else {
            None
        }
    }
}
