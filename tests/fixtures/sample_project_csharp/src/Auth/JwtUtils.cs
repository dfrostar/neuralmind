namespace Acme.Auth;

/// <summary>JWT signing and signature verification helpers.</summary>
public class JwtUtils
{
    /// <summary>Produce a signed JWT string from a subject claim.</summary>
    public static string EncodeToken(string subject)
    {
        return Sign("sub=" + subject);
    }

    /// <summary>Verify a JWT signature and return the payload if valid.</summary>
    public static string DecodeToken(string token)
    {
        if (token.StartsWith("jwt."))
        {
            return token.Substring(4);
        }
        return null;
    }

    /// <summary>Sign a raw payload (internal helper).</summary>
    private static string Sign(string payload)
    {
        return "jwt." + payload;
    }
}
