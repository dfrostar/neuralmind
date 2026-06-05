// Package billing provides invoice generation and Stripe integration.
package billing

import (
	"errors"
	"time"

	"example.com/sample/db"
	"example.com/sample/users"
)

// ErrInvoiceNotFound is returned when referencing a missing invoice.
var ErrInvoiceNotFound = errors.New("invoice not found")

// CreateInvoice writes an invoice row and returns it.
func CreateInvoice(userID, amountCents int, chargeID, description string) map[string]interface{} {
	conn := db.GetConnection()
	_, id := conn.Execute(
		"INSERT INTO invoices (user_id, amount_cents, charge_id, description, created_at) VALUES (?, ?, ?, ?, ?)",
		userID, amountCents, chargeID, description, time.Now().Unix(),
	)
	return map[string]interface{}{
		"id":           id,
		"user_id":      userID,
		"amount_cents": amountCents,
		"charge_id":    chargeID,
		"description":  description,
	}
}

// SendInvoiceEmail renders an invoice and hands it to the email transport.
//
// In production this would call the mail service; here it just marks the
// invoice as sent.
func SendInvoiceEmail(invoiceID int) error {
	conn := db.GetConnection()
	rows, _ := conn.Execute("SELECT user_id, amount_cents, description FROM invoices WHERE id = ?", invoiceID)
	if len(rows) == 0 {
		return ErrInvoiceNotFound
	}
	row := rows[0]
	user := users.GetUser(row[0].(int))
	if user == nil {
		return ErrInvoiceNotFound
	}
	renderAndQueue(user.Email, invoiceID, row[1].(int), row[2].(string))
	conn.Execute("UPDATE invoices SET sent_at = ? WHERE id = ?", time.Now().Unix(), invoiceID)
	return nil
}

// ListUserInvoices returns all invoices for a user, newest first.
func ListUserInvoices(userID int) []map[string]interface{} {
	conn := db.GetConnection()
	rows, _ := conn.Execute(
		"SELECT id, amount_cents, charge_id, description, created_at, sent_at FROM invoices WHERE user_id = ? ORDER BY created_at DESC",
		userID,
	)
	out := make([]map[string]interface{}, 0, len(rows))
	for _, r := range rows {
		out = append(out, map[string]interface{}{
			"id":           r[0],
			"amount_cents": r[1],
			"charge_id":    r[2],
			"description":  r[3],
			"created_at":   r[4],
			"sent_at":      r[5],
		})
	}
	return out
}

// renderAndQueue is a stand-in for the real mail-queue call.
func renderAndQueue(email string, invoiceID, amount int, description string) {
	_ = email
	_ = invoiceID
	_ = amount
	_ = description
}
