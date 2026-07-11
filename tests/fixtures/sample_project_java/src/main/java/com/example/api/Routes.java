package com.example.api;

import com.example.auth.Handlers;
import com.example.billing.StripeClient;
import com.example.db.Connection;

/** The HTTP methods the fixture router understands. */
enum Method {
    GET,
    POST,
    DELETE
}

/** A single registered route. */
class Route {
    /** URL path, e.g. {@code /api/auth/login}. */
    public String path;
    /** HTTP method for the route. */
    public Method method;
}

/** HTTP route table wiring auth and billing handlers to paths. */
public class Routes {
    /** POST /api/auth/login — issue a token for valid credentials. */
    public static String loginEndpoint(Connection conn, String email) {
        return Handlers.authenticateUser(conn, email);
    }

    /** GET /api/users/me — requires a valid session token. */
    public static boolean getMeEndpoint(String token) {
        return Handlers.verifySession(token);
    }

    /** POST /api/billing/charge — charge the authenticated user. */
    public static String chargeEndpoint(StripeClient client, long cents) {
        return client.chargeCustomer(cents);
    }
}
