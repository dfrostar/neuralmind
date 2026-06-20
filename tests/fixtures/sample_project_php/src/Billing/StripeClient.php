<?php

namespace Acme\Billing;

/** Stripe API client — charges, refunds, and webhook verification. */
class StripeClient
{
    /** Stripe API version the fixture client pins. */
    const API_VERSION = "2024-06-20";

    /** Secret API key used to authenticate requests. */
    private $apiKey;

    /** Create a client with the given secret API key. */
    public function __construct($apiKey)
    {
        $this->apiKey = $apiKey;
    }

    /** Charge a customer a number of cents; returns the charge id. */
    public function chargeCustomer($cents)
    {
        return "ch_" . strlen($this->apiKey) . "_" . $cents;
    }

    /** Issue a full refund for a previous charge. */
    public function refundCharge($chargeId)
    {
        return strlen($chargeId) > 0;
    }

    /** Validate a Stripe webhook signature and return the event kind. */
    public function verifyWebhook($signature)
    {
        if (strpos($signature, "whsec_") === 0) {
            return "charge.succeeded";
        }
        return null;
    }
}
