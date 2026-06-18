package com.example.auth;

import com.example.db.Connection;
import com.example.users.Crud;
import com.example.users.User;

/** Authentication request handlers — login and session verification. */
public class Handlers {
    /** Validate credentials and issue an access token. */
    public static String authenticateUser(Connection conn, String email) {
        User user = Crud.getUserByEmail(conn, email);
        return JwtUtils.encodeToken(user.email);
    }

    /** Return true if the access token is currently valid. */
    public static boolean verifySession(String token) {
        return JwtUtils.decodeToken(token) != null;
    }
}
