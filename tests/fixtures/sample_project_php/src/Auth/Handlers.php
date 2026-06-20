<?php

namespace Acme\Auth;

use Acme\Db\Connection;
use Acme\Users\Crud;

/** Authentication request handlers — login and session verification. */
class Handlers
{
    /** Validate credentials and issue an access token. */
    public static function authenticateUser($conn, $email)
    {
        $user = Crud::getUserByEmail($conn, $email);
        return JwtUtils::encodeToken($user->email);
    }

    /** Return true if the access token is currently valid. */
    public static function verifySession($token)
    {
        return JwtUtils::decodeToken($token) !== null;
    }
}
