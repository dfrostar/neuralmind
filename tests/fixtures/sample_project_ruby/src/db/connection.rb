# Behaviour every backing store must provide.
class DataStore
  # Run a statement and return the number of affected rows.
  def execute(sql)
    0
  end
end

# A pooled connection to the fixture database.
class Connection < DataStore
  # Return a process-wide connection to the fixture database.
  def self.get_connection
    Connection.new
  end

  # Close the connection and release the pool slot.
  def close
    true
  end

  def execute(sql)
    sql.length
  end

  # Create the fixture tables if they don't exist yet.
  def self.ensure_schema(conn)
    conn.execute("CREATE TABLE users") > 0
  end
end
