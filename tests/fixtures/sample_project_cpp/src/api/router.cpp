#include "app/router.hpp"

namespace app {
namespace api {

Router::Router(auth::BearerAuthenticator auth, users::UserRepository users)
    : auth_(std::move(auth)), users_(std::move(users)) {}

int Router::dispatch(const std::string &method, const std::string &path, const std::string &body) {
    if (path == "/login") {
        return auth_.authenticate(body) ? 200 : 401;
    }
    if (path == "/users" && method == "POST") {
        users_.create(body, "pw");
        return 201;
    }
    return 404;
}

}  // namespace api
}  // namespace app
