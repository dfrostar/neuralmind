#include "app/handlers.hpp"

namespace app {
namespace auth {

BearerAuthenticator::BearerAuthenticator(JwtCodec codec) : codec_(std::move(codec)) {}

bool BearerAuthenticator::authenticate(const std::string &token) {
    Claims claims;
    return codec_.verify(token, claims);
}

}  // namespace auth
}  // namespace app
