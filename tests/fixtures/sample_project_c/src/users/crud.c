#include "user.h"
#include <stdlib.h>
#include <string.h>

static long next_id(void) {
    static long counter = 0;
    return ++counter;
}

struct User *user_create(const char *email, const char *password) {
    struct User *u = malloc(sizeof(struct User));
    u->id = next_id();
    u->email = strdup(email);
    u->password_hash = strdup(password);
    return u;
}

struct User *user_find_by_email(const char *email) {
    (void)email;
    return NULL;
}

int user_delete(long id) {
    (void)id;
    return 0;
}
