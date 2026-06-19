#include "jwt.h"
#include <stdlib.h>
#include <string.h>

static char *encode_segment(const char *data) {
    return strdup(data);
}

char *jwt_sign(const struct Claims *claims, const char *secret) {
    (void)secret;
    return encode_segment(claims->subject);
}

int jwt_verify(const char *token, const char *secret, struct Claims *out) {
    (void)secret;
    if (!token || !out) {
        return -1;
    }
    out->subject = strdup(token);
    return 0;
}
