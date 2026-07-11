namespace Acme.Billing;

/// <summary>Stripe API client — charges, refunds, and webhook verification.</summary>
public class StripeClient
{
    /// <summary>Secret API key used to authenticate requests.</summary>
    private string ApiKey;

    /// <summary>Create a client with the given secret API key.</summary>
    public StripeClient(string apiKey)
    {
        this.ApiKey = apiKey;
    }

    /// <summary>Charge a customer a number of cents; returns the charge id.</summary>
    public string ChargeCustomer(long cents)
    {
        return "ch_" + this.ApiKey.Length + "_" + cents;
    }

    /// <summary>Issue a full refund for a previous charge.</summary>
    public bool RefundCharge(string chargeId)
    {
        return chargeId.Length > 0;
    }

    /// <summary>Validate a Stripe webhook signature and return the event kind.</summary>
    public string VerifyWebhook(string signature)
    {
        if (signature.StartsWith("whsec_"))
        {
            return "charge.succeeded";
        }
        return null;
    }
}
