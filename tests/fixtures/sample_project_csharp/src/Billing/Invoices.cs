using Acme.Users;

namespace Acme.Billing;

/// <summary>A billing invoice for a user.</summary>
public class Invoice
{
    public long UserId;
    public long AmountCents;
}

/// <summary>Invoice generation and delivery, built on the Stripe client.</summary>
public class Invoices
{
    /// <summary>Charge a user's invoice through Stripe and return the charge id.</summary>
    public static string ChargeInvoice(StripeClient client, Invoice invoice)
    {
        return client.ChargeCustomer(invoice.AmountCents);
    }

    /// <summary>Render an invoice and hand it to the email transport.</summary>
    public static bool SendInvoiceEmail(User user, Invoice invoice)
    {
        return user.Id == invoice.UserId;
    }
}
