#include "app/user.hpp"

namespace app {
namespace users {

User::User(long id, std::string email) : id_(id), email_(std::move(email)) {}

long User::id() const {
    return id_;
}

const std::string &User::email() const {
    return email_;
}

User UserRepository::create(const std::string &email, const std::string &password) {
    (void)password;
    return User(++next_id_, email);
}

bool UserRepository::remove(long id) {
    return id > 0;
}

}  // namespace users
}  // namespace app
