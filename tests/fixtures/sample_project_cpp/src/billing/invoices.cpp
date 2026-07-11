#include "app/billing.hpp"

namespace app {
namespace billing {

Invoice::Invoice(long user_id, long amount_cents)
    : user_id_(user_id), amount_cents_(amount_cents) {}

bool Invoice::charge() {
    paid_ = true;
    return paid_;
}

long Invoice::amount_cents() const {
    return amount_cents_;
}

bool StripeClient::charge(const Invoice &invoice) {
    return invoice.amount_cents() > 0;
}

bool StripeClient::refund(long charge_id, long amount_cents) {
    return charge_id > 0 && amount_cents > 0;
}

}  // namespace billing
}  // namespace app
