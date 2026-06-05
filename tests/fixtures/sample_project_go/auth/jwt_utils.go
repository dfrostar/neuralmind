// Package auth provides JWT encode/decode helpers and auth handlers.
package auth

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"strings"
	"time"
)

const (
	jwtSecret = "change-me-in-prod"
	algorithm = "HS256"
)

// ErrTokenExpired is returned when the exp claim is in the past.
var ErrTokenExpired = errors.New("token expired")

// ErrInvalidSignature is returned when the HMAC signature does not match.
var ErrInvalidSignature = errors.New("signature mismatch")

// ErrMalformedToken is returned when the token cannot be parsed.
var ErrMalformedToken = errors.New("token must have 3 segments")

// EncodeToken produces a signed JWT string from a claims map.
func EncodeToken(claims map[string]interface{}) string {
	header := map[string]string{"alg": algorithm, "typ": "JWT"}
	headerJSON, _ := json.Marshal(header)
	payloadJSON, _ := json.Marshal(claims)
	headerB64 := b64url(headerJSON)
	payloadB64 := b64url(payloadJSON)

	signingInput := headerB64 + "." + payloadB64
	signature := sign([]byte(signingInput))
	return signingInput + "." + b64url(signature)
}

// DecodeToken verifies signature + expiry and returns the claims map.
func DecodeToken(token string) (map[string]interface{}, error) {
	segments := strings.Split(token, ".")
	if len(segments) != 3 {
		return nil, ErrMalformedToken
	}
	signingInput := segments[0] + "." + segments[1]
	expected := sign([]byte(signingInput))
	sig, err := b64urlDecode(segments[2])
	if err != nil || !hmac.Equal(expected, sig) {
		return nil, ErrInvalidSignature
	}

	payloadBytes, err := b64urlDecode(segments[1])
	if err != nil {
		return nil, ErrMalformedToken
	}
	var payload map[string]interface{}
	if err := json.Unmarshal(payloadBytes, &payload); err != nil {
		return nil, ErrMalformedToken
	}
	if exp, ok := payload["exp"].(float64); ok {
		if time.Now().Unix() > int64(exp) {
			return nil, ErrTokenExpired
		}
	}
	return payload, nil
}

func sign(data []byte) []byte {
	mac := hmac.New(sha256.New, []byte(jwtSecret))
	mac.Write(data)
	return mac.Sum(nil)
}

func b64url(data []byte) string {
	return base64.RawURLEncoding.EncodeToString(data)
}

func b64urlDecode(s string) ([]byte, error) {
	return base64.RawURLEncoding.DecodeString(s)
}
