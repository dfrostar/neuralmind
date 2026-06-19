#include "db.h"
#include <stdlib.h>
#include <string.h>

struct Connection *db_connect(const char *dsn) {
    struct Connection *conn = malloc(sizeof(struct Connection));
    conn->dsn = strdup(dsn);
    conn->socket_fd = -1;
    conn->in_transaction = 0;
    return conn;
}

int db_execute(struct Connection *conn, const char *sql) {
    (void)sql;
    return conn ? 0 : -1;
}

void db_close(struct Connection *conn) {
    if (conn) {
        free(conn->dsn);
        free(conn);
    }
}
