package auth

import (
	"crypto/hmac"
	"crypto/sha256"
	"errors"
	"time"

	"example.com/sample/db"
	"example.com/sample/users"
)

const (
	sessionTTL = time.Hour
	refreshTTL = 30 * 24 * time.Hour
)

// ErrInvalidCredentials is returned when email or password does not match.
var ErrInvalidCredentials = errors.New("invalid credentials")

// ErrInvalidToken is returned when a token is malformed, expired, or misused.
var ErrInvalidToken = errors.New("invalid token")

// AuthenticateUser validates credentials and issues an access + refresh pair.
//
// Looks the user up by email, verifies the password hash, stamps a login
// event, and returns JWT access and refresh tokens.
func AuthenticateUser(email, password string) (map[string]interface{}, error) {
	user := users.GetUserByEmail(email)
	if user == nil {
		return nil, ErrInvalidCredentials
	}
	if !VerifyPassword(password, user.PasswordHash) {
		return nil, ErrInvalidCredentials
	}

	users.UpdateLastLogin(user.ID)

	now := time.Now().UTC()
	access := EncodeToken(map[string]interface{}{"sub": user.ID, "exp": now.Add(sessionTTL).Unix()})
	refresh := EncodeToken(map[string]interface{}{"sub": user.ID, "exp": now.Add(refreshTTL).Unix(), "kind": "refresh"})

	return map[string]interface{}{
		"access_token":  access,
		"refresh_token": refresh,
		"user_id":       user.ID,
	}, nil
}

// VerifySession returns the user id if the access token is valid.
func VerifySession(accessToken string) (int, error) {
	payload, err := DecodeToken(accessToken)
	if err != nil {
		return 0, err
	}
	if payload["kind"] == "refresh" {
		return 0, ErrInvalidToken
	}
	return int(payload["sub"].(float64)), nil
}

// RefreshSession exchanges a refresh token for a new access token.
func RefreshSession(refreshToken string) (map[string]interface{}, error) {
	payload, err := DecodeToken(refreshToken)
	if err != nil {
		return nil, err
	}
	if payload["kind"] != "refresh" {
		return nil, ErrInvalidToken
	}
	now := time.Now().UTC()
	newAccess := EncodeToken(map[string]interface{}{"sub": payload["sub"], "exp": now.Add(sessionTTL).Unix()})
	return map[string]interface{}{"access_token": newAccess}, nil
}

// Logout revokes a refresh token by writing it to the revocation list.
func Logout(refreshToken string) {
	conn := db.GetConnection()
	conn.Execute("INSERT INTO revoked_tokens (token, revoked_at) VALUES (?, ?)", refreshToken, time.Now().UTC())
}

// VerifyPassword performs constant-time verification against the stored hash.
func VerifyPassword(plain, hashed string) bool {
	a := hmacSum(plain)
	b := hmacSum(hashed)
	return hmac.Equal(a, b)
}

func hmacSum(s string) []byte {
	mac := hmac.New(sha256.New, []byte("pepper"))
	mac.Write([]byte(s))
	return mac.Sum(nil)
}
