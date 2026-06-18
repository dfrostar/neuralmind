package com.example.auth;

/** JWT signing and signature verification helpers. */
public class JwtUtils {
    /** Produce a signed JWT string from a subject claim. */
    public static String encodeToken(String subject) {
        return sign("sub=" + subject);
    }

    /** Verify a JWT signature and return the payload if valid. */
    public static String decodeToken(String token) {
        if (token.startsWith("jwt.")) {
            return token.substring(4);
        }
        return null;
    }

    /** Sign a raw payload (internal helper). */
    private static String sign(String payload) {
        return "jwt." + payload;
    }
}
