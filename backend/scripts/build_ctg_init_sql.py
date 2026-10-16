"""
Sinh 1 file SQL duy nhất để khởi tạo database CTG mới:
tạo bảng (schema lấy từ DB hiện tại) + insert toàn bộ data.

Chỉ ĐỌC database nguồn (transaction read-only), không sửa gì.

Cách dùng:
    python scripts/build_ctg_init_sql.py                 # nguồn = DATABASE_URL trong .env
    python scripts/build_ctg_init_sql.py --source-url URL --output database/ctg_init.sql
"""

import argparse
import asyncio
import re
from pathlib import Path

import asyncpg
from dotenv import dotenv_values


# Bảng GraphRAG: không tạo, không copy data.
EXCLUDED_TABLES = {
    "entities",
    "entity_contexts",
    "entity_relationships",
    "graph_documents",
    "users",
    "user_roles",
}

BATCH_SIZE = 200

NEXTVAL_RE = re.compile(r"nextval\('([^']+)'::regclass\)")


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def quote_literal(value: str | None) -> str:
    if value is None:
        return "NULL"

    # Escape xuống dòng để file không bị đổi CRLF/LF khi mở bằng editor
    # hoặc chạy trên Windows (dữ liệu có cả \r\n và \n).
    if "\r" in value or "\n" in value:
        escaped = (
            value
            .replace("\\", "\\\\")
            .replace("'", "''")
            .replace("\r", "\\r")
            .replace("\n", "\\n")
        )
        return "E'" + escaped + "'"

    return "'" + value.replace("'", "''") + "'"


def to_asyncpg_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def load_tables(conn) -> list[str]:
    rows = await conn.fetch(
        """
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
        ORDER BY c.relname
        """
    )
    return [r["relname"] for r in rows if r["relname"] not in EXCLUDED_TABLES]


async def load_columns(conn, table: str):
    return await conn.fetch(
        """
        SELECT a.attname AS name,
               format_type(a.atttypid, a.atttypmod) AS type,
               a.attnotnull AS not_null,
               NULLIF(a.attgenerated::text, '') AS generated,
               pg_get_expr(d.adbin, d.adrelid) AS default_expr
        FROM pg_attribute a
        LEFT JOIN pg_attrdef d
               ON d.adrelid = a.attrelid AND d.adnum = a.attnum
        WHERE a.attrelid = ('public.' || quote_ident($1))::regclass
          AND a.attnum > 0
          AND NOT a.attisdropped
        ORDER BY a.attnum
        """,
        table,
    )


async def load_constraints(conn, table: str):
    return await conn.fetch(
        """
        SELECT con.conname AS name,
               con.contype::text AS type,
               pg_get_constraintdef(con.oid) AS definition,
               ref.relname AS ref_table
        FROM pg_constraint con
        LEFT JOIN pg_class ref ON ref.oid = con.confrelid
        WHERE con.conrelid = ('public.' || quote_ident($1))::regclass
        ORDER BY CASE con.contype
                     WHEN 'p' THEN 0 WHEN 'u' THEN 1
                     WHEN 'c' THEN 2 WHEN 'f' THEN 3 ELSE 4
                 END,
                 con.conname
        """,
        table,
    )


async def load_extra_indexes(conn, table: str) -> list[str]:
    rows = await conn.fetch(
        """
        SELECT pg_get_indexdef(x.indexrelid) AS definition
        FROM pg_index x
        WHERE x.indrelid = ('public.' || quote_ident($1))::regclass
          AND NOT EXISTS (
              SELECT 1 FROM pg_constraint k WHERE k.conindid = x.indexrelid
          )
        ORDER BY 1
        """,
        table,
    )
    return [r["definition"] for r in rows]


async def load_rls(conn, table: str):
    return await conn.fetchrow(
        """
        SELECT relrowsecurity AS enabled, relforcerowsecurity AS forced
        FROM pg_class
        WHERE oid = ('public.' || quote_ident($1))::regclass
        """,
        table,
    )


def sort_by_dependencies(tables: list[str], deps: dict[str, set[str]]) -> list[str]:
    ordered: list[str] = []
    visiting: set[str] = set()

    def visit(table: str):
        if table in ordered:
            return
        if table in visiting:
            raise RuntimeError(f"Circular foreign key at table {table}")
        visiting.add(table)
        for dep in sorted(deps[table]):
            if dep != table:
                visit(dep)
        visiting.discard(table)
        ordered.append(table)

    for table in tables:
        visit(table)

    return ordered


async def build(source_url: str) -> tuple[str, dict[str, int]]:
    conn = await asyncpg.connect(
        to_asyncpg_url(source_url),
        statement_cache_size=0,
    )

    try:
        async with conn.transaction(readonly=True, isolation="repeatable_read"):
            await conn.execute("SET LOCAL TIME ZONE 'UTC'")

            tables = await load_tables(conn)
            meta = {}
            deps = {}

            for table in tables:
                columns = await load_columns(conn, table)
                excluded_columns = {"triggered_by"} if table == "ingestion_jobs" else set()
                columns = [c for c in columns if c["name"] not in excluded_columns]
                constraints = await load_constraints(conn, table)
                constraints = [c for c in constraints if not (
                    (c["type"] == "f" and c["ref_table"] in {"users", "user_roles"})
                    or any(re.search(r"\b" + re.escape(column) + r"\b", c["definition"])
                           for column in excluded_columns)
                )]

                for con in constraints:
                    if con["type"] == "f" and con["ref_table"] in EXCLUDED_TABLES:
                        raise RuntimeError(
                            f"{table}.{con['name']} references excluded table "
                            f"{con['ref_table']}"
                        )

                meta[table] = {
                    "columns": columns,
                    "constraints": constraints,
                    "indexes": [index for index in await load_extra_indexes(conn, table)
                                if not any(re.search(r"\b" + re.escape(column) + r"\b", index)
                                           for column in excluded_columns)],
                    "rls": await load_rls(conn, table),
                }
                deps[table] = {
                    con["ref_table"]
                    for con in constraints
                    if con["type"] == "f"
                }

            policies = await conn.fetchval(
                "SELECT count(*) FROM pg_policies WHERE schemaname = 'public' "
                "AND tablename <> ALL($1::text[])",
                list(EXCLUDED_TABLES),
            )
            if policies:
                raise RuntimeError(
                    "Source has RLS policies; this generator does not copy them yet."
                )

            ordered = sort_by_dependencies(tables, deps)

            out: list[str] = []
            counts: dict[str, int] = {}

            out += [
                "-- ============================================================",
                "-- CTG database init: schema + data",
                "-- Sinh bởi scripts/build_ctg_init_sql.py từ DB hiện tại.",
                "-- Đã loại bỏ bảng GraphRAG: " + ", ".join(sorted(EXCLUDED_TABLES)),
                "-- Chạy trên database MỚI, RỖNG. Lỗi ở bất kỳ bước nào sẽ rollback toàn bộ.",
                "-- CẢNH BÁO: file chứa dữ liệu thật (chat, CV, token Microsoft).",
                "-- Không commit, xóa sau khi import xong.",
                "-- ============================================================",
                "",
                "BEGIN;",
                "",
                "SET LOCAL standard_conforming_strings = on;",
                "SET LOCAL client_encoding = 'UTF8';",
                "SET LOCAL search_path = public, extensions;",
                "",
                "-- pgvector: recruitment_campaigns.cv_embedding",
                "CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;",
                "",
            ]

            # Sequences (cột serial)
            sequences: list[tuple[str, str, str]] = []
            for table in ordered:
                for col in meta[table]["columns"]:
                    match = NEXTVAL_RE.search(col["default_expr"] or "")
                    if match:
                        seq = match.group(1)
                        if "." not in seq:
                            seq = f"public.{seq}"
                        sequences.append((seq, table, col["name"]))

            if sequences:
                out.append("-- Sequences")
                for seq, _, _ in sequences:
                    out.append(f"CREATE SEQUENCE {seq};")
                out.append("")

            # Tables
            for table in ordered:
                lines = []
                for col in meta[table]["columns"]:
                    line = f"    {quote_ident(col['name'])} {col['type']}"
                    if col["generated"] == "s":
                        line += f" GENERATED ALWAYS AS ({col['default_expr']}) STORED"
                    elif col["default_expr"] is not None:
                        line += f" DEFAULT {col['default_expr']}"
                    if col["not_null"]:
                        line += " NOT NULL"
                    lines.append(line)

                for con in meta[table]["constraints"]:
                    lines.append(
                        f"    CONSTRAINT {quote_ident(con['name'])} {con['definition']}"
                    )

                out.append(f"CREATE TABLE public.{quote_ident(table)} (")
                out.append(",\n".join(lines))
                out.append(");")
                out.append("")

            for seq, table, column in sequences:
                out.append(
                    f"ALTER SEQUENCE {seq} OWNED BY "
                    f"public.{quote_ident(table)}.{quote_ident(column)};"
                )
            if sequences:
                out.append("")

            # Data
            out.append("-- ============================ DATA ============================")
            out.append("")

            for table in ordered:
                insert_cols = [
                    c["name"] for c in meta[table]["columns"] if not c["generated"]
                ]
                pk_cols = []
                for con in meta[table]["constraints"]:
                    if con["type"] == "p":
                        pk_cols = re.findall(r'"?([A-Za-z_][A-Za-z0-9_]*)"?',
                                             con["definition"].split("(", 1)[1])
                order_by = (
                    " ORDER BY " + ", ".join(quote_ident(c) for c in pk_cols)
                    if pk_cols else ""
                )
                select_list = ", ".join(
                    f"{quote_ident(c)}::text" for c in insert_cols
                )
                rows = await conn.fetch(
                    f"SELECT {select_list} FROM public.{quote_ident(table)}{order_by}"
                )
                counts[table] = len(rows)

                out.append(f"-- {table}: {len(rows)} rows")
                if not rows:
                    out.append("")
                    continue

                column_list = ", ".join(quote_ident(c) for c in insert_cols)
                for start in range(0, len(rows), BATCH_SIZE):
                    batch = rows[start:start + BATCH_SIZE]
                    values = ",\n".join(
                        "    (" + ", ".join(quote_literal(v) for v in row) + ")"
                        for row in batch
                    )
                    out.append(
                        f"INSERT INTO public.{quote_ident(table)} ({column_list}) VALUES\n"
                        f"{values};"
                    )
                out.append("")

            for seq, table, column in sequences:
                out.append(
                    f"SELECT setval('{seq}', "
                    f"COALESCE((SELECT max({quote_ident(column)}) FROM public.{quote_ident(table)}), 1), "
                    f"(SELECT max({quote_ident(column)}) FROM public.{quote_ident(table)}) IS NOT NULL);"
                )
            if sequences:
                out.append("")

            # Indexes + RLS
            out.append("-- ========================= INDEXES / RLS =========================")
            for table in ordered:
                for index in meta[table]["indexes"]:
                    out.append(f"{index};")
            out.append("")
            for table in ordered:
                rls = meta[table]["rls"]
                if rls["enabled"]:
                    out.append(
                        f"ALTER TABLE public.{quote_ident(table)} ENABLE ROW LEVEL SECURITY;"
                    )
                if rls["forced"]:
                    out.append(
                        f"ALTER TABLE public.{quote_ident(table)} FORCE ROW LEVEL SECURITY;"
                    )
            out.append("")
            out.append("COMMIT;")
            out.append("")

            return "\n".join(out), counts

    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-url", default=None)
    parser.add_argument("--output", default="database/ctg_init.sql")
    args = parser.parse_args()

    source_url = args.source_url or dotenv_values(".env").get("DATABASE_URL")
    if not source_url:
        raise SystemExit("Missing --source-url and DATABASE_URL in .env")

    sql, counts = asyncio.run(build(source_url))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(sql, encoding="utf-8", newline="\n")

    print(f"Wrote {output} ({output.stat().st_size // 1024} KB)")
    print(f"Tables: {len(counts)}, rows: {sum(counts.values())}")
    for table, count in counts.items():
        print(f"  {table:40} {count}")


if __name__ == "__main__":
    main()
