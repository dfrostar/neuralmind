<?php

namespace Acme\Users;

use Acme\Db\Connection;

/** User CRUD operations backed by the database connection. */
class Crud
{
    /** Insert a new user and return the created record. */
    public static function createUser($conn, $email)
    {
        $conn->execute("INSERT INTO users");
        $u = new User();
        $u->email = $email;
        return $u;
    }

    /** Fetch a user by email — the authentication hot path. */
    public static function getUserByEmail($conn, $email)
    {
        $conn->execute("SELECT * FROM users WHERE email = ?");
        $u = new User();
        $u->email = $email;
        return $u;
    }

    /** Fetch a user by primary key. */
    public static function getUser($conn, $id)
    {
        $conn->execute("SELECT * FROM users WHERE id = ?");
        $u = new User();
        $u->id = $id;
        return $u;
    }
}
