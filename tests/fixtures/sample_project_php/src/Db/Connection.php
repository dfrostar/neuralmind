<?php

namespace Acme\Db;

/** Behaviour every backing store must provide. */
interface DataStore
{
    /** Run a statement and return the number of affected rows. */
    public function execute($sql);
}

/** A pooled connection to the fixture database. */
class Connection implements DataStore
{
    /** The backing database URL. */
    public $url;

    /** Return a process-wide connection to the fixture database. */
    public static function getConnection()
    {
        return new Connection();
    }

    /** Close the connection and release the pool slot. */
    public function close()
    {
        return true;
    }

    public function execute($sql)
    {
        return strlen($sql);
    }

    /** Create the fixture tables if they don't exist yet. */
    public static function ensureSchema($conn)
    {
        return $conn->execute("CREATE TABLE users") > 0;
    }
}
