# migrations

运行时 schema 由 SQLAlchemy `Base.metadata.create_all` 在 backend 启动时创建（演示项目，
无 Alembic 迁移链）。`0001_initial.sql` 是同一份结构的 MySQL 8.0 DDL，供 DBA 审阅或手工初始化：

```bash
mysql -h 127.0.0.1 -P 17742 -u tracknorm -p tracknorm < backend/migrations/0001_initial.sql
```

修改模型后请同步本文件；生产化时应引入 Alembic 并把 create_all 换成显式迁移。
