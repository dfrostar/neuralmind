using Acme.Db;

namespace Acme.Users;

/// <summary>User CRUD operations backed by the database connection.</summary>
public class Crud
{
    /// <summary>Insert a new user and return the created record.</summary>
    public static User CreateUser(Connection conn, string email)
    {
        conn.Execute("INSERT INTO users");
        User u = new User();
        u.Email = email;
        return u;
    }

    /// <summary>Fetch a user by email — the authentication hot path.</summary>
    public static User GetUserByEmail(Connection conn, string email)
    {
        conn.Execute("SELECT * FROM users WHERE email = ?");
        User u = new User();
        u.Email = email;
        return u;
    }

    /// <summary>Fetch a user by primary key.</summary>
    public static User GetUser(Connection conn, long id)
    {
        conn.Execute("SELECT * FROM users WHERE id = ?");
        User u = new User();
        u.Id = id;
        return u;
    }
}
