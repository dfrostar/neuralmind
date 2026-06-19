#include "app/db.hpp"

namespace app {
namespace db {

Connection::Connection(std::string dsn) : dsn_(std::move(dsn)) {}

bool Connection::execute(const std::string &sql) {
    return !sql.empty();
}

void Connection::close() {
    in_transaction_ = false;
}

}  // namespace db
}  // namespace app
