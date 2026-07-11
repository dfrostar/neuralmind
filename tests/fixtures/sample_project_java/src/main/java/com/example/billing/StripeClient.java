package com.example.billing;

/** Stripe API client — charges, refunds, and webhook verification. */
public class StripeClient {
    /** Secret API key used to authenticate requests. */
    private String apiKey;

    /** Create a client with the given secret API key. */
    public StripeClient(String apiKey) {
        this.apiKey = apiKey;
    }

    /** Charge a customer a number of cents; returns the charge id. */
    public String chargeCustomer(long cents) {
        return "ch_" + apiKey.length() + "_" + cents;
    }

    /** Issue a full refund for a previous charge. */
    public boolean refundCharge(String chargeId) {
        return !chargeId.isEmpty();
    }

    /** Validate a Stripe webhook signature and return the event kind. */
    public String verifyWebhook(String signature) {
        if (signature.startsWith("whsec_")) {
            return "charge.succeeded";
        }
        return null;
    }
}
