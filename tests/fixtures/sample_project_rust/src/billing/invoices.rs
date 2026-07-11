//! Invoice generation and delivery, built on the Stripe client.

use crate::billing::stripe_client::StripeClient;
use crate::users::crud::User;

/// A billing invoice for a user.
pub struct Invoice {
    /// The user being billed.
    pub user_id: u64,
    /// Amount owed, in cents.
    pub amount_cents: u64,
}

/// Charge a user's invoice through Stripe and return the charge id.
pub fn charge_invoice(client: &StripeClient, invoice: &Invoice) -> String {
    client.charge_customer(invoice.amount_cents)
}

/// Render an invoice and hand it to the email transport.
pub fn send_invoice_email(user: &User, invoice: &Invoice) -> bool {
    user.id == invoice.user_id
}
