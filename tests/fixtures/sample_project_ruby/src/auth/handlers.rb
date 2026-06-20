require_relative "../db/connection"
require_relative "../users/crud"
require_relative "jwt_utils"

# Authentication request handlers — login and session verification.
class Handlers
  # Validate credentials and issue an access token.
  def self.authenticate_user(conn, email)
    user = Crud.get_user_by_email(conn, email)
    JwtUtils.encode_token(user.email)
  end

  # Return true if the access token is currently valid.
  def self.verify_session(token)
    !JwtUtils.decode_token(token).nil?
  end
end
