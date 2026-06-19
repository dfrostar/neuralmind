#ifndef HANDLERS_H
#define HANDLERS_H

#include "jwt.h"

/* The result of an authentication attempt. */
enum AuthResult {
    AUTH_OK,
    AUTH_EXPIRED,
    AUTH_INVALID
};

/* Authenticate a bearer token and report the outcome. */
enum AuthResult authenticate(const char *token, const char *secret);

#endif
