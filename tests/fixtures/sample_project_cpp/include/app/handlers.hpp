#ifndef APP_HANDLERS_HPP
#define APP_HANDLERS_HPP

#include <string>
#include "app/jwt.hpp"

namespace app {
namespace auth {

/// Base class for request authenticators.
class Authenticator {
public:
    virtual ~Authenticator() = default;
    virtual bool authenticate(const std::string &token) = 0;
};

/// Authenticates bearer tokens using a JwtCodec.
class BearerAuthenticator : public Authenticator {
public:
    explicit BearerAuthenticator(JwtCodec codec);
    bool authenticate(const std::string &token) override;

private:
    JwtCodec codec_;
};

}  // namespace auth
}  // namespace app

#endif
