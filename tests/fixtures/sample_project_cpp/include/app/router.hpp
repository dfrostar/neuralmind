#ifndef APP_ROUTER_HPP
#define APP_ROUTER_HPP

#include <string>
#include "app/handlers.hpp"
#include "app/user.hpp"
#include "app/billing.hpp"

namespace app {
namespace api {

/// Dispatches HTTP requests to the right subsystem.
class Router {
public:
    Router(auth::BearerAuthenticator auth, users::UserRepository users);
    int dispatch(const std::string &method, const std::string &path, const std::string &body);

private:
    auth::BearerAuthenticator auth_;
    users::UserRepository users_;
};

}  // namespace api
}  // namespace app

#endif
