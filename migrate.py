import psycopg2
from psycopg2 import sql

old_uri = "postgresql://postgres:Ss6dcHAz%3F%2BAVtbX@db.zomjegcicgciyaprzbkp.supabase.co:5432/postgres"
new_uri = "postgresql://postgres:%2FyXv%24gmT%259%2BEThc@db.wiwrsunutqjfmnfckgoy.supabase.co:5432/postgres"

def get_schema(conn, table_name):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name, data_type, character_maximum_length, column_default, is_nullable
            FROM information_schema.columns 
            WHERE table_name = %s AND table_schema = 'public'
            ORDER BY ordinal_position;
        """, (table_name,))
        return cur.fetchall()

def create_table_sql(table_name, schema):
    cols = []
    for col in schema:
        cname, dtype, max_len, default, is_null = col
        
        if default and "nextval" in default:
            if dtype == 'bigint':
                dtype = 'BIGSERIAL'
            elif dtype == 'integer':
                dtype = 'SERIAL'
            default = None
            
        col_def = f'"{cname}" {dtype}'
        if max_len:
            col_def += f"({max_len})"
        if is_null == 'NO':
            col_def += " NOT NULL"
        if default is not None:
            col_def += f" DEFAULT {default}"
        cols.append(col_def)
    
    return f'CREATE TABLE IF NOT EXISTS public."{table_name}" (\n    ' + ',\n    '.join(cols) + '\n);'

try:
    print("Connecting to old db...")
    conn_old = psycopg2.connect(old_uri)
    print("Connecting to new db...")
    conn_new = psycopg2.connect(new_uri)

    tables = ['users', 'chats']

    for table in tables:
        print(f"Migrating schema for {table}...")
        schema = get_schema(conn_old, table)
        if not schema:
            print(f"Table {table} not found in old DB.")
            continue
        
        create_sql = create_table_sql(table, schema)
        print(create_sql)
        with conn_new.cursor() as cur:
            cur.execute(create_sql)
        conn_new.commit()

        print(f"Migrating data for {table}...")
        with conn_old.cursor() as cur_old:
            cur_old.execute(f'SELECT * FROM public."{table}"')
            rows = cur_old.fetchall()
            if rows:
                cols = [f'"{c[0]}"' for c in schema]
                placeholders = ', '.join(['%s'] * len(cols))
                insert_sql = f'INSERT INTO public."{table}" ({", ".join(cols)}) VALUES ({placeholders})'
                with conn_new.cursor() as cur_new:
                    for row in rows:
                        cur_new.execute(insert_sql, row)
                conn_new.commit()
                print(f"Migrated {len(rows)} rows to {table}.")
            else:
                print(f"No data in {table}.")

    print("Done!")

except Exception as e:
    print("Error:", e)
finally:
    if 'conn_old' in locals(): conn_old.close()
    if 'conn_new' in locals(): conn_new.close()
