#ifndef JWT_H
#define JWT_H

/* A decoded JSON Web Token claim set. */
struct Claims {
    char *subject;
    long issued_at;
    long expires_at;
};

/* Sign a claim set, returning a newly allocated token string. */
char *jwt_sign(const struct Claims *claims, const char *secret);

/* Verify a token against the secret; fills claims on success. */
int jwt_verify(const char *token, const char *secret, struct Claims *out);

#endif
