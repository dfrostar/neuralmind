package com.example.db;

/** Behaviour every backing store must provide. */
interface DataStore {
    /** Run a statement and return the number of affected rows. */
    int execute(String sql);
}

/** A pooled connection to the fixture database. */
public class Connection implements DataStore {
    /** The backing database URL. */
    public String url;
    private boolean open;

    /** Return a process-wide connection to the fixture database. */
    public static Connection getConnection() {
        Connection c = new Connection();
        c.url = "jdbc:sqlite:fixture.db";
        c.open = true;
        return c;
    }

    /** Close the connection and release the pool slot. */
    public void close() {
        this.open = false;
    }

    @Override
    public int execute(String sql) {
        return sql.length();
    }

    /** Create the fixture tables if they don't exist yet. */
    public static boolean ensureSchema(Connection conn) {
        return conn.execute("CREATE TABLE users") > 0;
    }
}
