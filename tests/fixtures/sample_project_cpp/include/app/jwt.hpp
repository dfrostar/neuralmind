#ifndef APP_JWT_HPP
#define APP_JWT_HPP

#include <string>

namespace app {
namespace auth {

/// A decoded JSON Web Token claim set.
struct Claims {
    std::string subject;
    long issued_at;
    long expires_at;
};

/// Signs and verifies JSON Web Tokens.
class JwtCodec {
public:
    explicit JwtCodec(std::string secret);
    std::string sign(const Claims &claims) const;
    bool verify(const std::string &token, Claims &out) const;

private:
    std::string secret_;
};

}  // namespace auth
}  // namespace app

#endif
