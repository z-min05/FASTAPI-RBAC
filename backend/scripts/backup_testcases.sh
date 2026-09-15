#!/usr/bin/env bash
#
# ============================================================================
# testcases 表定时备份脚本
# ============================================================================
#
# 为什么备份 4 张表而不是 1 张（依赖链，自上而下）：
#   users                                        （根表，无上层依赖）
#     ^-- projects.id
#           ^-- testcase_modules.project_id
#           ^-- testcases.project_id            (NOT NULL 必填外键)
#     ^-- testcases.module_id -> testcase_modules.id  (可空外键，存的是数字 ID)
#     ^-- projects.code_init_by -> users.id      (自动化代码初始化人，来自 0007)
#
# 只 dump testcases 单表的话，将来恢复到新库会因外键约束失败，且 module_id
# （模块归属）会指向不存在的记录，所以必须带上 projects 与 testcase_modules。
# 不带 users 的话，projects.code_init_by -> users.id 这条外键在空库上会创建失败
# （报 relation "public.users" does not exist）：数据仍能恢复，但约束会丢失。
#
# 注意：备份文件因此包含 users 表（用户名 + 密码哈希），请确保文件权限受控
# （脚本已设 umask 077、目录 700）。若不希望备份用户数据，可把 users 从下面的
# TABLES 中移除，此时恢复空库会出现一条上述外键报错，测试用例数据本身不受影响。
#
# 为什么还要显式备份序列：
#   id 列是 SERIAL，序列是独立对象，pg_dump -t <表名> 不会自动包含它。
#   不一起备份的话，恢复时建表语句里的 nextval() 会因序列不存在而失败。
#   脚本会自动查出这几张表的序列并一并导出。
#
# 安装（示例：每天 03:00 执行，日志追加到 /var/log/testcases_backup.log）：
#   chmod +x backend/scripts/backup_testcases.sh
#   crontab -e
#   0 3 * * * /var/www/test_platform/backend/scripts/backup_testcases.sh >> /var/log/testcases_backup.log 2>&1
#
# 恢复（新服务器 / 空库）：
#   createdb -h <host> -U postgres fastapi_rbac
#   gunzip -c /var/backups/test_platform/testcases/testcases_20260915_030000.sql.gz \
#     | psql -h <host> -U postgres -d fastapi_rbac
#
# 恢复（覆盖现有库中的这四张表，谨慎操作，会先删掉现有数据）：
#   先执行 DROP TABLE IF EXISTS testcases, testcase_modules, projects, users CASCADE;
#   再导入上面的 psql 命令
#
# 说明：文件必须是 LF 换行。若报 "bad interpreter: /bin/bash^M"，
#   执行 sed -i 's/\r$//' backup_testcases.sh 修正后再运行。
# ============================================================================

set -euo pipefail
umask 077   # 备份文件默认仅属主可读

# ---------------------------- 可调配置 ----------------------------

# 备份文件存放目录。注意：仅本机磁盘时，整机/磁盘损坏会一起丢失，
# 建议后续将其纳入异地同步（rsync）或加入日常运维检查。
BACKUP_DIR="${BACKUP_DIR:-/var/backups/test_platform/testcases}"

# 保留天数，超期自动删除
KEEP_DAYS="${KEEP_DAYS:-30}"

# 要备份的表，顺序即依赖顺序（父表在前）
TABLES=(users projects testcase_modules testcases)

# 项目 .env 路径（用于自动解析数据库连接，脚本内不硬编码密码）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$(cd "${SCRIPT_DIR}/.." && pwd)/.env}"

PG_DUMP_BIN="${PG_DUMP_BIN:-pg_dump}"
PSQL_BIN="${PSQL_BIN:-psql}"

# ---------------------------- 工具函数 ----------------------------

log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*"; }
fail() { log "错误：$*"; exit 1; }

TMP_FILE=""
cleanup() {
  if [[ -n "${TMP_FILE}" && -f "${TMP_FILE}" ]]; then
    rm -f "${TMP_FILE}"
  fi
  return 0
}
trap cleanup EXIT

# ---------------------------- 前置检查 ----------------------------

command -v "${PG_DUMP_BIN}" >/dev/null 2>&1 \
  || fail "找不到 ${PG_DUMP_BIN}，请确认 PostgreSQL 客户端已安装并在 PATH 中"
command -v "${PSQL_BIN}" >/dev/null 2>&1 \
  || fail "找不到 ${PSQL_BIN}，请确认 PostgreSQL 客户端已安装并在 PATH 中"
[[ -f "${ENV_FILE}" ]] \
  || fail "找不到 .env：${ENV_FILE}（可用 ENV_FILE=/path/to/.env 指定）"

# ---------------------------- 解析数据库连接 ----------------------------

DATABASE_URL="$(grep -E '^[[:space:]]*DATABASE_URL=' "${ENV_FILE}" | head -n1 | cut -d= -f2-)"
[[ -n "${DATABASE_URL:-}" ]] || fail "${ENV_FILE} 中未找到 DATABASE_URL"

# 去掉可能包裹的引号
DATABASE_URL="${DATABASE_URL%\"}"; DATABASE_URL="${DATABASE_URL#\"}"
DATABASE_URL="${DATABASE_URL%\'}"; DATABASE_URL="${DATABASE_URL#\'}"

# postgresql+asyncpg://user:pass@host:port/db  ->  拆出各段
_url="${DATABASE_URL#*://}"
_url="${_url%%\?*}"        # 去掉 ? 之后的参数
_creds="${_url%@*}"        # user:pass
_hostpart="${_url##*@}"    # host:port/db

export PGUSER="${_creds%%:*}"
export PGPASSWORD="${_creds#*:}"
export PGHOST="${_hostpart%%:*}"
_pg_port="${_hostpart#*:}"
export PGPORT="${_pg_port%%/*}"
export PGDATABASE="${_hostpart##*/}"
export PGCONNECT_TIMEOUT=15

[[ -n "${PGUSER}" && -n "${PGHOST}" && -n "${PGDATABASE}" ]] \
  || fail "DATABASE_URL 解析失败：${DATABASE_URL}"

"${PSQL_BIN}" -Atq -c 'SELECT 1' >/dev/null 2>&1 \
  || fail "无法连接数据库 ${PGUSER}@${PGHOST}:${PGPORT}/${PGDATABASE}"

mkdir -p "${BACKUP_DIR}"
chmod 700 "${BACKUP_DIR}"

# ---------------------------- 收集序列名 ----------------------------

_table_list=""
for _t in "${TABLES[@]}"; do
  _table_list+="'${_t}',"
done
_table_list="${_table_list%,}"

_seq_names="$(
  "${PSQL_BIN}" -Atq -c \
    "SELECT pg_get_serial_sequence(quote_ident(t), 'id')
       FROM unnest(ARRAY[${_table_list}]) AS t
      WHERE pg_get_serial_sequence(quote_ident(t), 'id') IS NOT NULL"
)"

dump_args=(--no-owner --no-acl --encoding=UTF8)
for _t in "${TABLES[@]}"; do
  dump_args+=(-t "${_t}")
done
while IFS= read -r _s; do
  [[ -n "${_s}" ]] && dump_args+=(-t "${_s}")
done <<< "${_seq_names}"

# ---------------------------- 执行备份 ----------------------------

TS="$(date '+%Y%m%d_%H%M%S')"
OUT_FILE="${BACKUP_DIR}/testcases_${TS}.sql.gz"
TMP_FILE="${OUT_FILE}.tmp"

log "开始备份 ${PGUSER}@${PGHOST}:${PGPORT}/${PGDATABASE} 表=${TABLES[*]}"

"${PG_DUMP_BIN}" "${dump_args[@]}" | gzip -9 > "${TMP_FILE}"

# 校验：gzip 完整性 + 文件非空 + 关键表确实导出成功
gzip -t "${TMP_FILE}" >/dev/null 2>&1 || fail "备份文件损坏（gzip 校验失败）"
[[ -s "${TMP_FILE}" ]] || fail "备份文件为空"
for _t in "${TABLES[@]}"; do
  if ! gunzip -c "${TMP_FILE}" | grep -qE "^(CREATE TABLE|COPY) (public\.)?${_t}[ (]"; then
    fail "备份内容缺少表 ${_t}，已中止"
  fi
done

mv "${TMP_FILE}" "${OUT_FILE}"
TMP_FILE=""

log "备份完成 ${OUT_FILE}（$(du -h "${OUT_FILE}" | cut -f1)）"

# 记录行数，便于日后核对数据是否有缺失
for _t in "${TABLES[@]}"; do
  _cnt="$("${PSQL_BIN}" -Atq -c "SELECT count(*) FROM ${_t}")"
  log "  ${_t}: ${_cnt} 行"
done

# ---------------------------- 清理历史 ----------------------------

_deleted="$(
  find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'testcases_*.sql.gz' \
       -mtime +"${KEEP_DAYS}" -print -delete | wc -l
)"
if [[ "${_deleted}" -gt 0 ]]; then
  log "已清理 ${_deleted} 个超过 ${KEEP_DAYS} 天的旧备份"
fi
log "当前保留备份文件数：$(find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'testcases_*.sql.gz' | wc -l)"
