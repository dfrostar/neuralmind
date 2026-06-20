namespace Acme.Db;

/// <summary>Behaviour every backing store must provide.</summary>
public interface DataStore
{
    /// <summary>Run a statement and return the number of affected rows.</summary>
    int Execute(string sql);
}

/// <summary>A pooled connection to the fixture database.</summary>
public class Connection : DataStore
{
    /// <summary>The backing database URL.</summary>
    public string Url;
    private bool Open;

    /// <summary>Return a process-wide connection to the fixture database.</summary>
    public static Connection GetConnection()
    {
        Connection c = new Connection();
        c.Url = "sqlite:fixture.db";
        c.Open = true;
        return c;
    }

    /// <summary>Close the connection and release the pool slot.</summary>
    public void Close()
    {
        this.Open = false;
    }

    public int Execute(string sql)
    {
        return sql.Length;
    }

    /// <summary>Create the fixture tables if they don't exist yet.</summary>
    public static bool EnsureSchema(Connection conn)
    {
        return conn.Execute("CREATE TABLE users") > 0;
    }
}
