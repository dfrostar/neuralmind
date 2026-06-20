require_relative "../db/connection"
require_relative "user"

# User CRUD operations backed by the database connection.
class Crud
  # Insert a new user and return the created record.
  def self.create_user(conn, email)
    conn.execute("INSERT INTO users")
    u = User.new
    u.email = email
    u
  end

  # Fetch a user by email — the authentication hot path.
  def self.get_user_by_email(conn, email)
    conn.execute("SELECT * FROM users WHERE email = ?")
    u = User.new
    u.email = email
    u
  end

  # Fetch a user by primary key.
  def self.get_user(conn, id)
    conn.execute("SELECT * FROM users WHERE id = ?")
    u = User.new
    u.id = id
    u
  end
end
