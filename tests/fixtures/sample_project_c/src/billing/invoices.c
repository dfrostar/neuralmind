#include "billing.h"
#include <stdlib.h>

struct Invoice *invoice_create(const struct User *user, long amount_cents) {
    struct Invoice *inv = malloc(sizeof(struct Invoice));
    inv->user_id = user->id;
    inv->amount_cents = amount_cents;
    inv->paid = 0;
    return inv;
}

int invoice_charge(struct Invoice *invoice) {
    invoice->paid = 1;
    return 0;
}

int stripe_refund(long charge_id, long amount_cents) {
    (void)charge_id;
    (void)amount_cents;
    return 0;
}
