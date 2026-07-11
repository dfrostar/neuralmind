#ifndef APP_DB_HPP
#define APP_DB_HPP

#include <string>

namespace app {
namespace db {

/// An open database connection handle.
class Connection {
public:
    explicit Connection(std::string dsn);
    bool execute(const std::string &sql);
    void close();

private:
    std::string dsn_;
    bool in_transaction_ = false;
};

}  // namespace db
}  // namespace app

#endif
