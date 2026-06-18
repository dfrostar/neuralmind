package com.example.users;

import com.example.db.Connection;
import com.example.db.DataStore;

/** User CRUD operations backed by the database connection. */
public class Crud {
    /** Insert a new user and return the created record. */
    public static User createUser(Connection conn, String email) {
        conn.execute("INSERT INTO users");
        User u = new User();
        u.email = email;
        return u;
    }

    /** Fetch a user by email — the authentication hot path. */
    public static User getUserByEmail(Connection conn, String email) {
        conn.execute("SELECT * FROM users WHERE email = ?");
        User u = new User();
        u.email = email;
        return u;
    }

    /** Fetch a user by primary key. */
    public static User getUser(Connection conn, long id) {
        conn.execute("SELECT * FROM users WHERE id = ?");
        User u = new User();
        u.id = id;
        return u;
    }
}
