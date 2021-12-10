import pymysql
import json
import logging

import middleware.context as context

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()
logger.setLevel(logging.INFO)


class RDBServiceException(Exception):
    def __init__(self, msg):
        self.msg = msg


def _get_db_connection():

    db_connect_info = context.get_db_info()
    logger.info("rdb_service._get_db_connection:")
    logger.info("\t host = " + db_connect_info["host"])

    db_info = context.get_db_info()
    db_connection = pymysql.connect(**db_info)
    return db_connection


def fetch_all_records(db_schema, table_name, offset, limit, fields):
    conn = _get_db_connection()
    cur = conn.cursor()

    if fields is None:
        sql = "SELECT * FROM " + db_schema + "." + table_name
    else:
        sql = f"SELECT {', '.join(fields)} FROM " + db_schema + "." + table_name

    if offset is not None and limit is not None:
        sql += f" LIMIT {offset},{limit}"
    elif offset is not None and limit is None:
        sql += f" LIMIT {offset},18446744073709551615"
    elif offset is None and limit is not None:
        sql += f" LIMIT {limit}"

    print("sql statement = " + cur.mogrify(sql, None))

    try:
        res = cur.execute(sql)
    except pymysql.err.OperationalError as e:
        return False, (e.args[0], e.args[1])  # False == failure
    res = cur.fetchall()
    conn.close()
    return True, res


def get_by_prefix(db_schema, table_name, column_name, value_prefix):
    conn = _get_db_connection()
    cur = conn.cursor()

    sql = (
        "SELECT * FROM "
        + db_schema
        + "."
        + table_name
        + " WHERE "
        + column_name
        + " LIKE "
        + "'"
        + value_prefix
        + "%'"
    )
    print("SQL Statement = " + cur.mogrify(sql, None))

    res = cur.execute(sql)
    res = cur.fetchall()
    conn.close()
    return res


def _get_where_clause_args(template):

    terms = []
    args = []
    clause = None

    if template is None or template == {}:
        clause = ""
        args = None
    else:
        for k, v in template.items():
            terms.append(k + "=%s")
            args.append(v)

        clause = " WHERE " + " AND ".join(terms)

    return clause, args


def find_by_template(db_schema, table_name, template, offset=None, limit=None, fields=None):
    """
    Find an individual record by SQL template.
    :param db_schema: Schema name
    :param table_name: Table name
    :param template: A dictionary containing key, value pairs representing WHERE statements
    :return: Records found under template
    """
    conn = _get_db_connection()
    cur = conn.cursor()

    where_clause, args = _get_where_clause_args(template)

    if fields is None:
        sql = "SELECT * FROM " + db_schema + "." + table_name + " " + where_clause
    else:
        sql = f"SELECT {', '.join(fields)} FROM " + db_schema + "." + table_name + " " + where_clause

    if offset is not None and limit is not None:
        sql += f" LIMIT {offset},{limit}"
    elif offset is not None and limit is None:
        sql += f" LIMIT {offset},18446744073709551615"
    elif offset is None and limit is not None:
        sql += f" LIMIT {limit}"

    try:
        res = cur.execute(sql, args)
    except pymysql.err.OperationalError as e:
        return False, (e.args[0], e.args[1])  # False == failure
    res = cur.fetchall()
    conn.close()
    return True, res


def update_record(db_schema, table_name, conditions, **kwargs):
    """
    Update a database record with the mapping provided
    :param db_schema: Schema name
    :param table_name: Table name
    :param conditions: Row matching condition
    :param kwargs: Mapping of column to value to update
    :return: Database record updated, Throws RDBServiceException() if error occurs
    """
    if conditions is None or len(conditions) == 0:
        raise ValueError("Must have at least one condition for a record update.")

    update_elements = [f"{key} = {value}" for key, value in kwargs.items()]
    update_sql = ", ".join(update_elements)

    condition_elements = [f"{key} = {value}" for key, value in conditions.items()]
    condition_sql = ", ".join(condition_elements)

    sql = (
        "UPDATE "
        + db_schema + "." + table_name
        + " SET "
        + update_sql
        + " WHERE " + condition_sql
    )
    return _execute_db_commit_query(sql)


def create_new_record(db_schema, table_name, contents):
    """
    Inserts a record into the database generically as a list of key, value arguments.
    :param db_schema: Schema name
    :param table_name: Table name
    :param contents: Dictionary of key, value arguments
    :return: Database record created, Throws RDBServiceException() if error occurs
    """
    conn = _get_db_connection()
    cur = conn.cursor()

    columns = [key for key in contents.keys()]
    value_placeholders = ["%s" for _ in contents.keys()]
    column_specifier = "(" + ", ".join(columns) + ")"
    value_specifier = "(" + ", ".join(value_placeholders) + ")"
    sql = (
        "INSERT INTO "
        + db_schema + "." + table_name
        + column_specifier
        + " VALUES " + value_specifier
    )

    try:
        cur.execute(sql, args=[v for v in contents.values()])
        new_row = cur.lastrowid
        conn.commit()
        return new_row
    except Exception as e:
        raise RDBServiceException(e)
    finally:
        conn.close()


def delete_record_by_multikey(db_schema, table_name, **kwargs):
    """
    Deletes a single record from the database table by key; note that key column must be
    specified
    :param db_schema: Database schema name
    :param table_name: Table name
    :param kwargs: Dictionary containing keys and values to match entries by
    :return:
    """
    sql = (
        "DELETE FROM " + db_schema + "." + table_name
    )

    if len(kwargs) == 0:
        raise ValueError("Missing conditions for deletion.")

    sql += " WHERE "
    first_done = False
    for k, v in kwargs.items():
        if first_done: sql += " AND "
        first_done = True

        sql += f"{k} = {v}"

    return _execute_db_commit_query(sql)


def _execute_db_commit_query(sql):
    """
    Function to execute database query, based on provided sql statement
    :param sql: String version of SQL statement to run
    :return: Database response
    """
    conn = _get_db_connection()
    cur = conn.cursor()
    try:
        res = cur.execute(sql)
        conn.commit()
        return res
    except Exception as e:
        raise RDBServiceException(e)
    finally:
        conn.close()
