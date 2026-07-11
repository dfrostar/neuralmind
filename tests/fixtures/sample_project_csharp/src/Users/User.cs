namespace Acme.Users;

/// <summary>A persisted user record.</summary>
public class User
{
    /// <summary>Primary key.</summary>
    public long Id;
    /// <summary>Unique login email.</summary>
    public string Email;
    /// <summary>Whether the account is active (auto-property).</summary>
    public bool IsActive { get; set; }
}
