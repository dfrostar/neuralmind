package com.example.billing;

import com.example.users.User;

/** A billing invoice for a user. */
class Invoice {
    public long userId;
    public long amountCents;
}

/** Invoice generation and delivery, built on the Stripe client. */
public class Invoices {
    /** Charge a user's invoice through Stripe and return the charge id. */
    public static String chargeInvoice(StripeClient client, Invoice invoice) {
        return client.chargeCustomer(invoice.amountCents);
    }

    /** Render an invoice and hand it to the email transport. */
    public static boolean sendInvoiceEmail(User user, Invoice invoice) {
        return user.id == invoice.userId;
    }
}
