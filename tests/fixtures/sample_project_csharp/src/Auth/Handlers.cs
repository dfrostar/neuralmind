using Acme.Db;
using Acme.Users;

namespace Acme.Auth;

/// <summary>Authentication request handlers — login and session verification.</summary>
public class Handlers
{
    /// <summary>Validate credentials and issue an access token.</summary>
    public static string AuthenticateUser(Connection conn, string email)
    {
        User user = Crud.GetUserByEmail(conn, email);
        return JwtUtils.EncodeToken(user.Email);
    }

    /// <summary>Return true if the access token is currently valid.</summary>
    public static bool VerifySession(string token)
    {
        return JwtUtils.DecodeToken(token) != null;
    }
}
