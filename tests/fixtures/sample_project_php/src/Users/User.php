<?php

namespace Acme\Users;

/** A persisted user record. */
class User
{
    /** Maximum length the fixture allows for an email. */
    const MAX_EMAIL_LEN = 254;

    /** Primary key. */
    public $id;
    /** Unique login email. */
    public $email;
}
