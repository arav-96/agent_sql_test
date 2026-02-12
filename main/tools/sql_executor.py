import duckdb


class DuckDBExecutor:
    """
    Thin wrapper around DuckDB for executing read-only analytical queries
    against an existing DuckDB database file.
    """

    def __init__(self, db_path: str):
        """
        Initialize a connection to an existing DuckDB database.

        Args:
            db_path (str): Path to DuckDB file (e.g. data/taxi.duckdb)
        """
        self.db_path = db_path
        # DuckDB does not support read-only mode for in-memory databases.
        read_only = db_path != ":memory:"
        self.conn = duckdb.connect(
            database=db_path,
            read_only=read_only
        )

    def execute(self, sql: str):
        """
        Execute a SQL query and return results as a pandas DataFrame.

        Args:
            sql (str): SQL query to execute

        Returns:
            pandas.DataFrame
        """
        return self.conn.execute(sql).df()

    def register_table(self, name: str, df):
        """
        Register a pandas DataFrame as a DuckDB table/view.

        Args:
            name (str): Table name to register.
            df (pandas.DataFrame): DataFrame to register.
        """
        self.conn.register(name, df)

    def close(self):
        """
        Close the DuckDB connection.
        """
        if self.conn:
            self.conn.close()
            self.conn = None
