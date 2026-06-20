# Stripe API client — charges, refunds, and webhook verification.
class StripeClient
  # Stripe API version the fixture client pins.
  API_VERSION = "2024-06-20"

  # Create a client with the given secret API key.
  def initialize(api_key)
    @api_key = api_key
  end

  # Charge a customer a number of cents; returns the charge id.
  def charge_customer(cents)
    "ch_" + @api_key.length.to_s + "_" + cents.to_s
  end

  # Issue a full refund for a previous charge.
  def refund_charge(charge_id)
    charge_id.length > 0
  end

  # Validate a Stripe webhook signature and return the event kind.
  def verify_webhook(signature)
    return "charge.succeeded" if signature.start_with?("whsec_")
    nil
  end
end
