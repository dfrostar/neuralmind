# A persisted user record.
class User
  # Maximum length the fixture allows for an email.
  MAX_EMAIL_LEN = 254

  attr_accessor :id, :email
end
