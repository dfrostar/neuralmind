// Package api wires HTTP routes for the sample web app.
package api

import (
	"strings"

	"example.com/sample/auth"
	"example.com/sample/billing"
	"example.com/sample/users"
)

// Request is a minimal HTTP request used by the fixture.
type Request struct {
	JSON    map[string]interface{}
	Body    []byte
	Headers map[string]string
}

// Handler handles a single request.
type Handler func(r Request) (interface{}, error)

// Route is a (method, path, handler) tuple.
type Route struct {
	Method  string
	Path    string
	Handler Handler
}

// Routes is the registered route table.
var Routes []Route

func register(method, path string, fn Handler) {
	Routes = append(Routes, Route{Method: strings.ToUpper(method), Path: path, Handler: fn})
}

// LoginEndpoint handles POST /api/auth/login — returns access + refresh tokens.
func LoginEndpoint(r Request) (interface{}, error) {
	return auth.AuthenticateUser(r.JSON["email"].(string), r.JSON["password"].(string))
}

// RefreshEndpoint handles POST /api/auth/refresh — returns a new access token.
func RefreshEndpoint(r Request) (interface{}, error) {
	return auth.RefreshSession(r.JSON["refresh_token"].(string))
}

// LogoutEndpoint handles POST /api/auth/logout — revokes a refresh token.
func LogoutEndpoint(r Request) (interface{}, error) {
	auth.Logout(r.JSON["refresh_token"].(string))
	return map[string]bool{"ok": true}, nil
}

// CreateUserEndpoint handles POST /api/users — sign-up flow.
func CreateUserEndpoint(r Request) (interface{}, error) {
	user := users.CreateUser(r.JSON["email"].(string), r.JSON["password_hash"].(string))
	return map[string]interface{}{"id": user.ID, "email": user.Email}, nil
}

// GetMeEndpoint handles GET /api/users/me — requires Authorization: Bearer.
func GetMeEndpoint(r Request) (interface{}, error) {
	userID, err := auth.VerifySession(bearer(r))
	if err != nil {
		return nil, err
	}
	user := users.GetUser(userID)
	return map[string]interface{}{"id": user.ID, "email": user.Email}, nil
}

// DeleteMeEndpoint handles DELETE /api/users/me — soft-delete the user.
func DeleteMeEndpoint(r Request) (interface{}, error) {
	userID, err := auth.VerifySession(bearer(r))
	if err != nil {
		return nil, err
	}
	users.DeactivateUser(userID)
	return map[string]bool{"ok": true}, nil
}

// ChargeEndpoint handles POST /api/billing/charge — charge the user.
func ChargeEndpoint(r Request) (interface{}, error) {
	userID, err := auth.VerifySession(bearer(r))
	if err != nil {
		return nil, err
	}
	return billing.ChargeCustomer(userID, int(r.JSON["amount_cents"].(float64)), r.JSON["description"].(string))
}

// RefundEndpoint handles POST /api/billing/refund — admin-only refund.
func RefundEndpoint(r Request) (interface{}, error) {
	return billing.RefundCharge(r.JSON["charge_id"].(string), r.JSON["reason"].(string))
}

// ListInvoicesEndpoint handles GET /api/billing/invoices — list user invoices.
func ListInvoicesEndpoint(r Request) (interface{}, error) {
	userID, err := auth.VerifySession(bearer(r))
	if err != nil {
		return nil, err
	}
	return billing.ListUserInvoices(userID), nil
}

// StripeWebhookEndpoint handles POST /webhooks/stripe — entry point for events.
func StripeWebhookEndpoint(r Request) (interface{}, error) {
	event, err := billing.VerifyWebhook(r.Body, r.Headers["Stripe-Signature"])
	if err != nil {
		return nil, err
	}
	billing.HandleWebhookEvent(event)
	return map[string]bool{"received": true}, nil
}

func bearer(r Request) string {
	return strings.TrimSpace(strings.TrimPrefix(r.Headers["Authorization"], "Bearer "))
}

func init() {
	register("POST", "/api/auth/login", LoginEndpoint)
	register("POST", "/api/auth/refresh", RefreshEndpoint)
	register("POST", "/api/auth/logout", LogoutEndpoint)
	register("POST", "/api/users", CreateUserEndpoint)
	register("GET", "/api/users/me", GetMeEndpoint)
	register("DELETE", "/api/users/me", DeleteMeEndpoint)
	register("POST", "/api/billing/charge", ChargeEndpoint)
	register("POST", "/api/billing/refund", RefundEndpoint)
	register("GET", "/api/billing/invoices", ListInvoicesEndpoint)
	register("POST", "/webhooks/stripe", StripeWebhookEndpoint)
}
