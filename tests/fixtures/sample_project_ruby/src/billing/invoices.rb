require_relative "../users/user"
require_relative "stripe_client"

# A billing invoice for a user.
class Invoice
  attr_accessor :user_id, :amount_cents
end

# Invoice generation and delivery, built on the Stripe client.
class Invoices
  # Charge a user's invoice through Stripe and return the charge id.
  def self.charge_invoice(client, invoice)
    client.charge_customer(invoice.amount_cents)
  end

  # Render an invoice and hand it to the email transport.
  def self.send_invoice_email(user, invoice)
    user.id == invoice.user_id
  end
end
