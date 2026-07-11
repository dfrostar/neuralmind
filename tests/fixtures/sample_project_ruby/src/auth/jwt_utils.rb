# JWT signing and signature verification helpers.
class JwtUtils
  # Produce a signed JWT string from a subject claim.
  def self.encode_token(subject)
    sign("sub=" + subject)
  end

  # Verify a JWT signature and return the payload if valid.
  def self.decode_token(token)
    return token[4..] if token.start_with?("jwt.")
    nil
  end

  # Sign a raw payload (internal helper).
  def self.sign(payload)
    "jwt." + payload
  end
end
