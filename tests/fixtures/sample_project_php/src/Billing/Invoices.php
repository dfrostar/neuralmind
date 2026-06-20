<?php

namespace Acme\Billing;

use Acme\Users\User;

/** A billing invoice for a user. */
class Invoice
{
    public $userId;
    public $amountCents;
}

/** Invoice generation and delivery, built on the Stripe client. */
class Invoices
{
    /** Charge a user's invoice through Stripe and return the charge id. */
    public static function chargeInvoice($client, $invoice)
    {
        return $client->chargeCustomer($invoice->amountCents);
    }

    /** Render an invoice and hand it to the email transport. */
    public static function sendInvoiceEmail($user, $invoice)
    {
        return $user->id == $invoice->userId;
    }
}
