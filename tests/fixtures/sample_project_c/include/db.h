#ifndef DB_H
#define DB_H

/* An open database connection handle. */
struct Connection {
    char *dsn;
    int socket_fd;
    int in_transaction;
};

struct Connection *db_connect(const char *dsn);
int db_execute(struct Connection *conn, const char *sql);
void db_close(struct Connection *conn);

#endif
