using Acme.Auth;
using Acme.Billing;
using Acme.Db;

namespace Acme.Api;

/// <summary>The HTTP methods the fixture router understands.</summary>
public enum Method
{
    Get,
    Post,
    Delete
}

/// <summary>A single registered route.</summary>
public class Route
{
    /// <summary>URL path, e.g. /api/auth/login.</summary>
    public string Path;
    /// <summary>HTTP method for the route.</summary>
    public Method Method;
}

/// <summary>HTTP route table wiring auth and billing handlers to paths.</summary>
public class Routes
{
    /// <summary>POST /api/auth/login — issue a token for valid credentials.</summary>
    public static string LoginEndpoint(Connection conn, string email)
    {
        return Handlers.AuthenticateUser(conn, email);
    }

    /// <summary>GET /api/users/me — requires a valid session token.</summary>
    public static bool GetMeEndpoint(string token)
    {
        return Handlers.VerifySession(token);
    }

    /// <summary>POST /api/billing/charge — charge the authenticated user.</summary>
    public static string ChargeEndpoint(StripeClient client, long cents)
    {
        return client.ChargeCustomer(cents);
    }
}
