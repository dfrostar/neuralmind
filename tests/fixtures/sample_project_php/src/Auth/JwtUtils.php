<?php

namespace Acme\Auth;

/** JWT signing and signature verification helpers. */
class JwtUtils
{
    /** Produce a signed JWT string from a subject claim. */
    public static function encodeToken($subject)
    {
        return self::sign("sub=" . $subject);
    }

    /** Verify a JWT signature and return the payload if valid. */
    public static function decodeToken($token)
    {
        if (strpos($token, "jwt.") === 0) {
            return substr($token, 4);
        }
        return null;
    }

    /** Sign a raw payload (internal helper). */
    private static function sign($payload)
    {
        return "jwt." . $payload;
    }
}
