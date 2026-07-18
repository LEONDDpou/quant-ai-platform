"""模拟盘交易系统（Paper Trading）— 企业级模块化子包。

分层架构（自上而下，依赖单向）：
    routers/       接口层（FastAPI 路由，仅做参数校验与协议转换）
    services/      业务层（交易/账户/撮合/风控等业务规则）
    repositories/  数据访问层（Repository Pattern，封装 ORM 持久化）
    domain_models  领域模型（SQLAlchemy ORM，仅依赖 app.db.database.Base）

设计目标：
- 高内聚低耦合，各层仅依赖下一层；
- 本包自包含，仅依赖 app.db.database 的 Base 与 SessionLocal，
  未来可整体抽离为独立微服务（如 paper-service）。
"""
