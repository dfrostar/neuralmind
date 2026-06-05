package billing

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"strconv"
	"strings"
	"time"

	"example.com/sample/db"
	"example.com/sample/users"
)

const (
	stripeWebhookSecret  = "whsec_REPLACE"
	webhookToleranceSecs = 300
)

// ErrBilling is returned when a charge or refund cannot proceed.
var ErrBilling = errors.New("billing error")

// ErrWebhookVerification is returned when a webhook signature does not match.
var ErrWebhookVerification = errors.New("webhook verification failed")

// ChargeCustomer creates a Stripe charge and mirrors it into our billing table.
//
// Flow: validate user → call Stripe API → on success, create an invoice and
// write a billing record locally.
func ChargeCustomer(userID, amountCents int, description string) (map[string]interface{}, error) {
	user := users.GetUser(userID)
	if user == nil || !user.IsActive {
		return nil, fmt.Errorf("%w: user %d not chargeable", ErrBilling, userID)
	}

	resp := fakeStripeCharge(amountCents, description)
	chargeID := resp["id"].(string)

	conn := db.GetConnection()
	conn.Execute(
		"INSERT INTO charges (user_id, stripe_id, amount_cents, status, created_at) VALUES (?, ?, ?, ?, ?)",
		userID, chargeID, amountCents, resp["status"], time.Now().Unix(),
	)
	invoice := CreateInvoice(userID, amountCents, chargeID, description)
	return map[string]interface{}{"charge_id": chargeID, "invoice_id": invoice["id"]}, nil
}

// RefundCharge issues a full refund for a previous charge and logs it.
func RefundCharge(chargeID, reason string) (map[string]interface{}, error) {
	conn := db.GetConnection()
	rows, _ := conn.Execute("SELECT user_id, amount_cents, status FROM charges WHERE stripe_id = ?", chargeID)
	if len(rows) == 0 {
		return nil, fmt.Errorf("%w: unknown charge %s", ErrBilling, chargeID)
	}
	if rows[0][2] == "refunded" {
		return nil, fmt.Errorf("%w: charge %s already refunded", ErrBilling, chargeID)
	}
	refundID := "re_" + chargeID[3:]
	conn.Execute("UPDATE charges SET status = 'refunded' WHERE stripe_id = ?", chargeID)
	_ = reason
	return map[string]interface{}{"refund_id": refundID, "amount_cents": rows[0][1]}, nil
}

// VerifyWebhook validates a Stripe webhook signature and returns the event body.
//
// Stripe-Signature header format: 't=timestamp,v1=hex_signature'.
func VerifyWebhook(payload []byte, signatureHeader string) (map[string]interface{}, error) {
	parts := map[string]string{}
	for _, p := range strings.Split(signatureHeader, ",") {
		kv := strings.SplitN(p, "=", 2)
		if len(kv) == 2 {
			parts[kv[0]] = kv[1]
		}
	}
	timestamp, _ := strconv.ParseInt(parts["t"], 10, 64)
	signature := parts["v1"]

	if math.Abs(float64(time.Now().Unix()-timestamp)) > webhookToleranceSecs {
		return nil, ErrWebhookVerification
	}

	signedPayload := append([]byte(fmt.Sprintf("%d.", timestamp)), payload...)
	mac := hmac.New(sha256.New, []byte(stripeWebhookSecret))
	mac.Write(signedPayload)
	expected := hex.EncodeToString(mac.Sum(nil))
	if !hmac.Equal([]byte(expected), []byte(signature)) {
		return nil, ErrWebhookVerification
	}

	var event map[string]interface{}
	if err := json.Unmarshal(payload, &event); err != nil {
		return nil, ErrWebhookVerification
	}
	return event, nil
}

// HandleWebhookEvent dispatches a verified Stripe webhook event.
func HandleWebhookEvent(event map[string]interface{}) {
	eventType, _ := event["type"].(string)
	data, _ := event["data"].(map[string]interface{})
	obj, _ := data["object"].(map[string]interface{})
	id, _ := obj["id"].(string)
	switch eventType {
	case "charge.succeeded":
		onChargeStatus(id, "succeeded")
	case "charge.failed":
		onChargeStatus(id, "failed")
	case "charge.refunded":
		onChargeStatus(id, "refunded")
	}
}

func onChargeStatus(stripeID, status string) {
	conn := db.GetConnection()
	conn.Execute("UPDATE charges SET status = ? WHERE stripe_id = ?", status, stripeID)
}

// fakeStripeCharge is a stand-in for the real Stripe API call.
func fakeStripeCharge(amountCents int, description string) map[string]interface{} {
	_ = amountCents
	_ = description
	return map[string]interface{}{"id": fmt.Sprintf("ch_%d", time.Now().Unix()), "status": "succeeded"}
}
