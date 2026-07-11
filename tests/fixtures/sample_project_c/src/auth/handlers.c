#include "handlers.h"

enum AuthResult authenticate(const char *token, const char *secret) {
    struct Claims claims;
    if (jwt_verify(token, secret, &claims) != 0) {
        return AUTH_INVALID;
    }
    return AUTH_OK;
}
