#ifndef APP_USER_HPP
#define APP_USER_HPP

#include <string>

namespace app {
namespace users {

/// A persisted user record.
class User {
public:
    User(long id, std::string email);
    long id() const;
    const std::string &email() const;

private:
    long id_;
    std::string email_;
};

/// Stores and retrieves User records.
class UserRepository {
public:
    User create(const std::string &email, const std::string &password);
    bool remove(long id);

private:
    long next_id_ = 0;
};

}  // namespace users
}  // namespace app

#endif
