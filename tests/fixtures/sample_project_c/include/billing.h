#ifndef BILLING_H
#define BILLING_H

#include "user.h"

/* A line item plus total for a billing run. */
struct Invoice {
    long id;
    long user_id;
    long amount_cents;
    int paid;
};

struct Invoice *invoice_create(const struct User *user, long amount_cents);
int invoice_charge(struct Invoice *invoice);
int stripe_refund(long charge_id, long amount_cents);

#endif
