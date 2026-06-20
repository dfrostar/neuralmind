require_relative "../auth/handlers"
require_relative "../billing/stripe_client"
require_relative "../db/connection"

# The HTTP methods the fixture router understands.
module Method
  GET = "GET"
  POST = "POST"
  DELETE = "DELETE"
end

# A single registered route.
class Route
  attr_accessor :path, :verb
end

# HTTP route table wiring auth and billing handlers to paths.
class Routes
  # POST /api/auth/login — issue a token for valid credentials.
  def self.login_endpoint(conn, email)
    Handlers.authenticate_user(conn, email)
  end

  # GET /api/users/me — requires a valid session token.
  def self.get_me_endpoint(token)
    Handlers.verify_session(token)
  end

  # POST /api/billing/charge — charge the authenticated user.
  def self.charge_endpoint(client, cents)
    client.charge_customer(cents)
  end
end
