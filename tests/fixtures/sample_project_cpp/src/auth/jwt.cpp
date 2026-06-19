#include "app/jwt.hpp"

namespace app {
namespace auth {

JwtCodec::JwtCodec(std::string secret) : secret_(std::move(secret)) {}

std::string JwtCodec::sign(const Claims &claims) const {
    return claims.subject + "." + secret_;
}

bool JwtCodec::verify(const std::string &token, Claims &out) const {
    if (token.empty()) {
        return false;
    }
    out.subject = token;
    return true;
}

}  // namespace auth
}  // namespace app
