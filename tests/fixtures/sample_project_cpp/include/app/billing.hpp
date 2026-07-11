#ifndef APP_BILLING_HPP
#define APP_BILLING_HPP

#include "app/user.hpp"

namespace app {
namespace billing {

/// A single billing line item.
class Invoice {
public:
    Invoice(long user_id, long amount_cents);
    bool charge();
    long amount_cents() const;

private:
    long user_id_;
    long amount_cents_;
    bool paid_ = false;
};

/// Talks to the payment processor.
class StripeClient {
public:
    bool charge(const Invoice &invoice);
    bool refund(long charge_id, long amount_cents);
};

}  // namespace billing
}  // namespace app

#endif
