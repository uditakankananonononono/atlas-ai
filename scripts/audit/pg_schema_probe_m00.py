"""Read-only M00 PostgreSQL catalog probe after migrations, not feature acceptance."""
import json
import os
import psycopg


def probe(connection):
    tables = [r[0] for r in connection.execute("select table_name from information_schema.tables where table_schema='public' and table_name like 'm00_%' order by table_name")]
    columns = {}
    for table in tables:
        columns[table] = {name: kind for name, kind in connection.execute("select column_name, data_type from information_schema.columns where table_schema='public' and table_name=%s order by ordinal_position", (table,))}
    partitions = list(connection.execute("select parent.relname, child.relname from pg_inherits i join pg_class parent on parent.oid=i.inhparent join pg_class child on child.oid=i.inhrelid where parent.relname like 'm00_%' order by 1,2"))
    triggers = list(connection.execute("select event_object_table, trigger_name from information_schema.triggers where event_object_schema='public' and event_object_table like 'm00_%' order by 1,2"))
    foreign_keys = list(connection.execute("select table_name, constraint_name from information_schema.table_constraints where table_schema='public' and table_name like 'm00_%' and constraint_type='FOREIGN KEY' order by 1,2"))
    return {"server_version": connection.execute("show server_version").fetchone()[0], "columns": columns, "partitions": partitions, "triggers": triggers, "foreign_keys": foreign_keys}


if __name__ == "__main__":
    url = os.environ["ATLAS_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as connection:
        print(json.dumps(probe(connection), indent=2))
