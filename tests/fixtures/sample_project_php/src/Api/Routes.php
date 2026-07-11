<?php

namespace Acme\Api;

use Acme\Auth\Handlers;
use Acme\Billing\StripeClient;
use Acme\Db\Connection;

/** The HTTP methods the fixture router understands. */
interface Method
{
    const GET = "GET";
    const POST = "POST";
    const DELETE = "DELETE";
}

/** A single registered route. */
class Route
{
    /** URL path, e.g. /api/auth/login. */
    public $path;
    /** HTTP method for the route. */
    public $verb;
}

/** HTTP route table wiring auth and billing handlers to paths. */
class Routes
{
    /** POST /api/auth/login — issue a token for valid credentials. */
    public static function loginEndpoint($conn, $email)
    {
        return Handlers::authenticateUser($conn, $email);
    }

    /** GET /api/users/me — requires a valid session token. */
    public static function getMeEndpoint($token)
    {
        return Handlers::verifySession($token);
    }

    /** POST /api/billing/charge — charge the authenticated user. */
    public static function chargeEndpoint($client, $cents)
    {
        return $client->chargeCustomer($cents);
    }
}
