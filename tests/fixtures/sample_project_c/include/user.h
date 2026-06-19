#ifndef USER_H
#define USER_H

/* A persisted user record. */
struct User {
    long id;
    char *email;
    char *password_hash;
};

struct User *user_create(const char *email, const char *password);
struct User *user_find_by_email(const char *email);
int user_delete(long id);

#endif
