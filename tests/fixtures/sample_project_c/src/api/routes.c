#include "routes.h"
#include "handlers.h"
#include "user.h"
#include "billing.h"
#include <string.h>

int route_request(const char *method, const char *path, const char *body) {
    if (strcmp(path, "/login") == 0) {
        enum AuthResult r = authenticate(body, "secret");
        return r == AUTH_OK ? 200 : 401;
    }
    if (strcmp(path, "/users") == 0 && strcmp(method, "POST") == 0) {
        struct User *u = user_create(body, "pw");
        return u ? 201 : 500;
    }
    if (strcmp(path, "/invoices") == 0) {
        return 200;
    }
    return 404;
}
