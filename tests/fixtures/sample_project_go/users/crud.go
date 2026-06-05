// Package users provides the user model and CRUD operations.
package users

import (
	"time"

	"example.com/sample/db"
)

// User is the canonical user record.
type User struct {
	ID           int
	Email        string
	PasswordHash string
	CreatedAt    time.Time
	LastLogin    *time.Time
	IsActive     bool
}

// CreateUser inserts a new user and returns the created record.
func CreateUser(email, passwordHash string) *User {
	conn := db.GetConnection()
	_, id := conn.Execute(
		"INSERT INTO users (email, password_hash, created_at, is_active) VALUES (?, ?, ?, ?)",
		email, passwordHash, time.Now().UTC(), true,
	)
	return &User{
		ID:           id,
		Email:        email,
		PasswordHash: passwordHash,
		CreatedAt:    time.Now().UTC(),
		IsActive:     true,
	}
}

// GetUserByEmail fetches a user by email (auth hot path).
func GetUserByEmail(email string) *User {
	conn := db.GetConnection()
	rows, _ := conn.Execute(
		"SELECT id, email, password_hash, created_at, last_login, is_active FROM users WHERE email = ? AND is_active = 1",
		email,
	)
	if len(rows) == 0 {
		return nil
	}
	return rowToUser(rows[0])
}

// GetUser fetches a user by primary key.
func GetUser(userID int) *User {
	conn := db.GetConnection()
	rows, _ := conn.Execute(
		"SELECT id, email, password_hash, created_at, last_login, is_active FROM users WHERE id = ?",
		userID,
	)
	if len(rows) == 0 {
		return nil
	}
	return rowToUser(rows[0])
}

// UpdateLastLogin stamps the user's last_login timestamp.
func UpdateLastLogin(userID int) {
	conn := db.GetConnection()
	conn.Execute("UPDATE users SET last_login = ? WHERE id = ?", time.Now().UTC(), userID)
}

// DeactivateUser soft-deletes a user by flipping is_active off.
func DeactivateUser(userID int) {
	conn := db.GetConnection()
	conn.Execute("UPDATE users SET is_active = 0 WHERE id = ?", userID)
}

func rowToUser(row db.Row) *User {
	return &User{
		ID:           row[0].(int),
		Email:        row[1].(string),
		PasswordHash: row[2].(string),
		CreatedAt:    row[3].(time.Time),
		IsActive:     row[5].(bool),
	}
}
