from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_

import models
import schemas
import auth
import validators
from database import engine, get_db, Base

Base.metadata.create_all(bind=engine)

app = FastAPI(title="茶焙坊管理系统 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def init_db():
    db = next(get_db())
    admin = db.query(models.User).filter(models.User.username == "admin").first()
    if not admin:
        admin_user = models.User(
            username="admin",
            full_name="系统管理员",
            hashed_password=auth.get_password_hash("admin123"),
            role="admin"
        )
        db.add(admin_user)

    qc = db.query(models.User).filter(models.User.username == "qc001").first()
    if not qc:
        qc_user = models.User(
            username="qc001",
            full_name="品控员001",
            hashed_password=auth.get_password_hash("qc123456"),
            role="qc"
        )
        db.add(qc_user)
    db.commit()


init_db()


@app.get("/")
def root():
    return {"message": "茶焙坊管理系统 API 服务已启动", "port": 8111, "docs": "/docs"}


@app.post("/auth/login", response_model=schemas.Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/auth/me", response_model=schemas.UserResponse)
async def get_current_user_info(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


@app.post("/admin/users", response_model=schemas.UserResponse)
def create_user(
    user_data: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    if user_data.role not in ["admin", "qc"]:
        raise HTTPException(status_code=400, detail="角色只能是 admin 或 qc")
    existing = db.query(models.User).filter(models.User.username == user_data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = models.User(
        username=user_data.username,
        full_name=user_data.full_name,
        role=user_data.role,
        hashed_password=auth.get_password_hash(user_data.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/admin/users", response_model=List[schemas.UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    return db.query(models.User).all()


@app.post("/admin/tea-stocks", response_model=schemas.TeaStockResponse)
def create_tea_stock(
    data: schemas.TeaStockCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    existing = db.query(models.TeaStock).filter(models.TeaStock.batch_no == data.batch_no).first()
    if existing:
        raise HTTPException(status_code=400, detail="茶坯批号已存在")
    stock = models.TeaStock(**data.model_dump())
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


@app.get("/admin/tea-stocks", response_model=List[schemas.TeaStockResponse])
def list_tea_stocks(
    batch_no: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    query = db.query(models.TeaStock)
    if batch_no:
        query = query.filter(models.TeaStock.batch_no.contains(batch_no))
    return query.order_by(models.TeaStock.created_at.desc()).all()


@app.put("/admin/tea-stocks/{stock_id}", response_model=schemas.TeaStockResponse)
def update_tea_stock(
    stock_id: int,
    data: schemas.TeaStockCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    stock = db.query(models.TeaStock).filter(models.TeaStock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="茶坯不存在")
    duplicate = db.query(models.TeaStock).filter(
        models.TeaStock.batch_no == data.batch_no,
        models.TeaStock.id != stock_id
    ).first()
    if duplicate:
        raise HTTPException(status_code=400, detail=f"茶坯批号 '{data.batch_no}' 已存在，无法修改")
    for key, value in data.model_dump().items():
        setattr(stock, key, value)
    db.commit()
    db.refresh(stock)
    return stock


@app.delete("/admin/tea-stocks/{stock_id}")
def delete_tea_stock(
    stock_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    stock = db.query(models.TeaStock).filter(models.TeaStock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="茶坯不存在")
    db.delete(stock)
    db.commit()
    return {"message": "删除成功"}


@app.post("/admin/furnaces", response_model=schemas.FurnaceResponse)
def create_furnace(
    data: schemas.FurnaceCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    existing = db.query(models.Furnace).filter(models.Furnace.furnace_no == data.furnace_no).first()
    if existing:
        raise HTTPException(status_code=400, detail="焙火炉号已存在")
    furnace = models.Furnace(**data.model_dump())
    db.add(furnace)
    db.commit()
    db.refresh(furnace)
    return furnace


@app.get("/admin/furnaces", response_model=List[schemas.FurnaceResponse])
def list_furnaces(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    return db.query(models.Furnace).order_by(models.Furnace.furnace_no).all()


@app.put("/admin/furnaces/{furnace_id}", response_model=schemas.FurnaceResponse)
def update_furnace(
    furnace_id: int,
    data: schemas.FurnaceCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    furnace = db.query(models.Furnace).filter(models.Furnace.id == furnace_id).first()
    if not furnace:
        raise HTTPException(status_code=404, detail="焙火炉不存在")
    duplicate = db.query(models.Furnace).filter(
        models.Furnace.furnace_no == data.furnace_no,
        models.Furnace.id != furnace_id
    ).first()
    if duplicate:
        raise HTTPException(status_code=400, detail=f"焙火炉号 '{data.furnace_no}' 已存在，无法修改")
    for key, value in data.model_dump().items():
        setattr(furnace, key, value)
    db.commit()
    db.refresh(furnace)
    return furnace


@app.delete("/admin/furnaces/{furnace_id}")
def delete_furnace(
    furnace_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    furnace = db.query(models.Furnace).filter(models.Furnace.id == furnace_id).first()
    if not furnace:
        raise HTTPException(status_code=404, detail="焙火炉不存在")
    db.delete(furnace)
    db.commit()
    return {"message": "删除成功"}


@app.post("/admin/fire-levels", response_model=schemas.FireLevelResponse)
def create_fire_level(
    data: schemas.FireLevelCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    existing = db.query(models.FireLevel).filter(models.FireLevel.level_code == data.level_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="火候等级编码已存在")
    fire_level = models.FireLevel(**data.model_dump())
    db.add(fire_level)
    db.commit()
    db.refresh(fire_level)
    return fire_level


@app.get("/admin/fire-levels", response_model=List[schemas.FireLevelResponse])
def list_fire_levels(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    return db.query(models.FireLevel).order_by(models.FireLevel.level_code).all()


@app.put("/admin/fire-levels/{level_id}", response_model=schemas.FireLevelResponse)
def update_fire_level(
    level_id: int,
    data: schemas.FireLevelCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    level = db.query(models.FireLevel).filter(models.FireLevel.id == level_id).first()
    if not level:
        raise HTTPException(status_code=404, detail="火候等级不存在")
    duplicate = db.query(models.FireLevel).filter(
        models.FireLevel.level_code == data.level_code,
        models.FireLevel.id != level_id
    ).first()
    if duplicate:
        raise HTTPException(status_code=400, detail=f"火候等级编码 '{data.level_code}' 已存在，无法修改")
    for key, value in data.model_dump().items():
        setattr(level, key, value)
    db.commit()
    db.refresh(level)
    return level


@app.delete("/admin/fire-levels/{level_id}")
def delete_fire_level(
    level_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    level = db.query(models.FireLevel).filter(models.FireLevel.id == level_id).first()
    if not level:
        raise HTTPException(status_code=404, detail="火候等级不存在")
    db.delete(level)
    db.commit()
    return {"message": "删除成功"}


@app.post("/admin/cabinets", response_model=schemas.CabinetResponse)
def create_cabinet(
    data: schemas.CabinetCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    existing = db.query(models.Cabinet).filter(models.Cabinet.cabinet_no == data.cabinet_no).first()
    if existing:
        raise HTTPException(status_code=400, detail="静置柜位号已存在")
    cabinet = models.Cabinet(**data.model_dump())
    db.add(cabinet)
    db.commit()
    db.refresh(cabinet)
    return cabinet


@app.get("/admin/cabinets", response_model=List[schemas.CabinetResponse])
def list_cabinets(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    return db.query(models.Cabinet).order_by(models.Cabinet.cabinet_no).all()


@app.put("/admin/cabinets/{cabinet_id}", response_model=schemas.CabinetResponse)
def update_cabinet(
    cabinet_id: int,
    data: schemas.CabinetCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    cabinet = db.query(models.Cabinet).filter(models.Cabinet.id == cabinet_id).first()
    if not cabinet:
        raise HTTPException(status_code=404, detail="静置柜位不存在")
    duplicate = db.query(models.Cabinet).filter(
        models.Cabinet.cabinet_no == data.cabinet_no,
        models.Cabinet.id != cabinet_id
    ).first()
    if duplicate:
        raise HTTPException(status_code=400, detail=f"静置柜位号 '{data.cabinet_no}' 已存在，无法修改")
    for key, value in data.model_dump().items():
        setattr(cabinet, key, value)
    db.commit()
    db.refresh(cabinet)
    return cabinet


@app.delete("/admin/cabinets/{cabinet_id}")
def delete_cabinet(
    cabinet_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    cabinet = db.query(models.Cabinet).filter(models.Cabinet.id == cabinet_id).first()
    if not cabinet:
        raise HTTPException(status_code=404, detail="静置柜位不存在")
    db.delete(cabinet)
    db.commit()
    return {"message": "删除成功"}


@app.post("/admin/persons", response_model=schemas.PersonResponse)
def create_person(
    data: schemas.PersonCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    existing = db.query(models.Person).filter(models.Person.person_no == data.person_no).first()
    if existing:
        raise HTTPException(status_code=400, detail="责任人编号已存在")
    person = models.Person(**data.model_dump())
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


@app.get("/admin/persons", response_model=List[schemas.PersonResponse])
def list_persons(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    return db.query(models.Person).order_by(models.Person.person_no).all()


@app.put("/admin/persons/{person_id}", response_model=schemas.PersonResponse)
def update_person(
    person_id: int,
    data: schemas.PersonCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    person = db.query(models.Person).filter(models.Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="责任人不存在")
    duplicate = db.query(models.Person).filter(
        models.Person.person_no == data.person_no,
        models.Person.id != person_id
    ).first()
    if duplicate:
        raise HTTPException(status_code=400, detail=f"责任人编号 '{data.person_no}' 已存在，无法修改")
    for key, value in data.model_dump().items():
        setattr(person, key, value)
    db.commit()
    db.refresh(person)
    return person


@app.delete("/admin/persons/{person_id}")
def delete_person(
    person_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    person = db.query(models.Person).filter(models.Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="责任人不存在")
    db.delete(person)
    db.commit()
    return {"message": "删除成功"}


@app.post("/qc/batches", response_model=schemas.BatchResponse)
def create_batch(
    data: schemas.BatchCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_qc)
):
    if not data.plan_roast_start or not data.plan_roast_end:
        raise HTTPException(status_code=400, detail="必须指定计划入炉和出炉时间")
    if data.plan_roast_end <= data.plan_roast_start:
        raise HTTPException(status_code=400, detail="计划出炉时间必须晚于入炉时间")

    missing_refs = []
    if not db.query(models.TeaStock).filter(models.TeaStock.id == data.tea_stock_id).first():
        missing_refs.append(f"茶坯ID={data.tea_stock_id}")
    if not db.query(models.Furnace).filter(models.Furnace.id == data.furnace_id).first():
        missing_refs.append(f"焙火炉ID={data.furnace_id}")
    if not db.query(models.FireLevel).filter(models.FireLevel.id == data.fire_level_id).first():
        missing_refs.append(f"火候等级ID={data.fire_level_id}")
    if not db.query(models.Person).filter(models.Person.id == data.person_id).first():
        missing_refs.append(f"责任人ID={data.person_id}")
    if data.cabinet_id and not db.query(models.Cabinet).filter(models.Cabinet.id == data.cabinet_id).first():
        missing_refs.append(f"静置柜位ID={data.cabinet_id}")
    if missing_refs:
        raise HTTPException(status_code=400, detail=f"引用的基础数据不存在: {', '.join(missing_refs)}")

    conflicts = validators.check_furnace_conflict(
        db, data.furnace_id, data.plan_roast_start, data.plan_roast_end
    )
    if conflicts:
        raise HTTPException(
            status_code=400,
            detail={"message": "同一炉号同一时段存在冲突批次", "conflicts": conflicts}
        )

    batch_code = validators.generate_batch_code(db)
    batch = models.Batch(
        batch_code=batch_code,
        **data.model_dump()
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


@app.get("/qc/batches", response_model=List[schemas.BatchDetailResponse])
def list_batches(
    batch_code: Optional[str] = Query(None, description="批次编码"),
    tea_batch_no: Optional[str] = Query(None, description="茶坯批号"),
    furnace_no: Optional[str] = Query(None, description="炉号"),
    fire_level_id: Optional[int] = Query(None, description="火候等级ID"),
    person_id: Optional[int] = Query(None, description="责任人ID"),
    status: Optional[str] = Query(None, description="状态"),
    burnt_edge_level: Optional[int] = Query(None, description="焦边等级"),
    date_from: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    query = db.query(models.Batch)

    if batch_code:
        query = query.filter(models.Batch.batch_code.contains(batch_code))
    if status:
        query = query.filter(models.Batch.status == status)
    if fire_level_id:
        query = query.filter(models.Batch.fire_level_id == fire_level_id)
    if person_id:
        query = query.filter(models.Batch.person_id == person_id)
    if furnace_no:
        query = query.join(models.Furnace).filter(models.Furnace.furnace_no.contains(furnace_no))
    if tea_batch_no:
        query = query.join(models.TeaStock).filter(models.TeaStock.batch_no.contains(tea_batch_no))
    if date_from:
        d_from = datetime.strptime(date_from, "%Y-%m-%d")
        query = query.filter(models.Batch.created_at >= d_from)
    if date_to:
        d_to = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
        query = query.filter(models.Batch.created_at < d_to)
    if burnt_edge_level is not None:
        subquery = db.query(models.ProcessRecord.batch_id).filter(
            models.ProcessRecord.record_type == "retest",
            models.ProcessRecord.burnt_edge_level == burnt_edge_level
        ).subquery()
        query = query.filter(models.Batch.id.in_(subquery))

    return query.order_by(models.Batch.created_at.desc()).offset(skip).limit(limit).all()


@app.get("/qc/batches/{batch_id}", response_model=schemas.BatchDetailResponse)
def get_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    batch = db.query(models.Batch).filter(models.Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")
    return batch


@app.post("/qc/batches/{batch_id}/records", response_model=schemas.ProcessRecordResponse)
def create_process_record(
    batch_id: int,
    data: schemas.ProcessRecordCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_qc)
):
    batch = db.query(models.Batch).filter(models.Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")

    now = datetime.utcnow()
    valid_record_types = ["in_furnace", "out_furnace", "to_cabinet", "retest", "delivery"]
    if data.record_type not in valid_record_types:
        raise HTTPException(status_code=400, detail=f"记录类型必须是: {', '.join(valid_record_types)}")

    if data.record_type == "in_furnace":
        batch.status = "roasting"
        batch.actual_roast_start = now
        batch.roast_count = (batch.roast_count or 0) + 1

        furnace = db.query(models.Furnace).filter(models.Furnace.id == batch.furnace_id).first()
        if furnace:
            furnace.status = "in_use"

    elif data.record_type == "out_furnace":
        batch.status = "standing"
        batch.actual_roast_end = now

        furnace = db.query(models.Furnace).filter(models.Furnace.id == batch.furnace_id).first()
        if furnace:
            furnace.status = "idle"

    elif data.record_type == "to_cabinet":
        batch.status = "pending_retest"
        batch.cabinet_start = now

        if data.burnt_edge_level is not None and (data.burnt_edge_level < 0 or data.burnt_edge_level > 5):
            raise HTTPException(status_code=400, detail="焦边等级范围 0-5")

        cabinet = db.query(models.Cabinet).filter(models.Cabinet.id == batch.cabinet_id).first()
        if cabinet:
            cabinet.status = "in_use"

    elif data.record_type == "retest":
        if data.retest_conclusion not in ["pass", "fail", "re-roast"]:
            raise HTTPException(status_code=400, detail="复测结论必须是 pass/fail/re-roast")
        if data.burnt_edge_level is not None and (data.burnt_edge_level < 0 or data.burnt_edge_level > 5):
            raise HTTPException(status_code=400, detail="焦边等级范围 0-5")

        if data.retest_conclusion == "pass":
            batch.status = "deliverable"
        elif data.retest_conclusion == "fail":
            batch.status = "paused"
        elif data.retest_conclusion == "re-roast":
            batch.status = "need_reroast"

    elif data.record_type == "delivery":
        batch.status = "delivered"

        cabinet = db.query(models.Cabinet).filter(models.Cabinet.id == batch.cabinet_id).first()
        if cabinet:
            cabinet.status = "empty"

    record_data = data.model_dump()
    record_data.pop("batch_id", None)
    record = models.ProcessRecord(
        batch_id=batch_id,
        recorder_id=current_user.id,
        **record_data
    )

    if data.record_type in ["out_furnace", "to_cabinet"]:
        batch.retest_deadline = now + timedelta(hours=batch.retest_cycle_hours or 24)

    batch.updated_at = now
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@app.get("/qc/batches/{batch_id}/records", response_model=List[schemas.ProcessRecordResponse])
def list_batch_records(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    batch = db.query(models.Batch).filter(models.Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")
    return db.query(models.ProcessRecord).filter(
        models.ProcessRecord.batch_id == batch_id
    ).order_by(models.ProcessRecord.recorded_at.asc()).all()


@app.put("/qc/batches/{batch_id}/status")
def update_batch_status(
    batch_id: int,
    new_status: str = Query(..., description="新状态: pending_in/roasting/standing/pending_retest/need_reroast/deliverable/delivered/paused"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_qc)
):
    valid_statuses = ["pending_in", "roasting", "standing", "pending_retest", "need_reroast", "deliverable", "delivered", "paused"]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"无效状态。有效值: {', '.join(valid_statuses)}")

    batch = db.query(models.Batch).filter(models.Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")

    old_status = batch.status
    batch.status = new_status
    batch.updated_at = datetime.utcnow()
    db.commit()

    return {"message": "状态更新成功", "batch_code": batch.batch_code, "old_status": old_status, "new_status": new_status}


@app.get("/alerts", response_model=List[schemas.AlertItem])
def get_alerts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    return validators.get_all_alerts(db)


@app.get("/stats/high-risk-fire-levels", response_model=List[schemas.HighRiskFireItem])
def get_high_risk_fire_levels(
    min_batches: int = Query(5, description="最少批次数"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    results = []
    fire_levels = db.query(models.FireLevel).all()

    for fl in fire_levels:
        total = db.query(models.Batch).filter(models.Batch.fire_level_id == fl.id).count()
        if total < min_batches:
            continue

        burnt_count = db.query(models.Batch).join(models.ProcessRecord).filter(
            models.Batch.fire_level_id == fl.id,
            models.ProcessRecord.record_type == "retest",
            models.ProcessRecord.burnt_edge_level >= 3
        ).distinct(models.Batch.id).count()

        rate = burnt_count / total if total > 0 else 0
        results.append(schemas.HighRiskFireItem(
            fire_level_id=fl.id,
            fire_level_code=fl.level_code,
            fire_level_name=fl.level_name,
            total_batches=total,
            burnt_edge_count=burnt_count,
            risk_rate=round(rate, 4)
        ))

    results.sort(key=lambda x: x.risk_rate, reverse=True)
    return results


@app.get("/stats/pending-retest")
def get_pending_retest_list(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    now = datetime.utcnow()
    batches = db.query(models.Batch).filter(
        models.Batch.status == "pending_retest"
    ).all()

    result = []
    for batch in batches:
        overdue_hours = 0
        is_overdue = False
        if batch.retest_deadline:
            if now > batch.retest_deadline:
                overdue_hours = (now - batch.retest_deadline).total_seconds() / 3600
                is_overdue = True

        person = db.query(models.Person).filter(models.Person.id == batch.person_id).first()
        result.append({
            "batch_id": batch.id,
            "batch_code": batch.batch_code,
            "tea_stock_id": batch.tea_stock_id,
            "fire_level_id": batch.fire_level_id,
            "person_id": batch.person_id,
            "person_name": person.person_name if person else None,
            "retest_deadline": batch.retest_deadline.isoformat() if batch.retest_deadline else None,
            "retest_cycle_hours": batch.retest_cycle_hours,
            "is_overdue": is_overdue,
            "overdue_hours": round(overdue_hours, 1),
            "roast_count": batch.roast_count,
            "cabinet_start": batch.cabinet_start.isoformat() if batch.cabinet_start else None
        })

    result.sort(key=lambda x: (x["is_overdue"], x["overdue_hours"]), reverse=True)
    return result


@app.get("/stats/delivery-trend", response_model=List[schemas.DeliveryTrendItem])
def get_delivery_trend(
    days: int = Query(14, description="统计天数"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days - 1)

    results = []
    for i in range(days):
        current_date = start_date + timedelta(days=i)
        next_date = current_date + timedelta(days=1)

        total = db.query(models.Batch).filter(
            models.Batch.created_at >= datetime.combine(current_date, datetime.min.time()),
            models.Batch.created_at < datetime.combine(next_date, datetime.min.time())
        ).count()

        delivered = db.query(models.Batch).filter(
            models.Batch.status == "delivered",
            models.Batch.updated_at >= datetime.combine(current_date, datetime.min.time()),
            models.Batch.updated_at < datetime.combine(next_date, datetime.min.time())
        ).count()

        rate = delivered / total if total > 0 else 0
        results.append(schemas.DeliveryTrendItem(
            date=current_date.isoformat(),
            total_batches=total,
            delivered_count=delivered,
            delivery_rate=round(rate, 4)
        ))

    return results


@app.get("/stats/person-backlog", response_model=List[schemas.TodoItem])
def get_person_backlog(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    todo_statuses = ["pending_in", "roasting", "standing", "pending_retest", "need_reroast", "deliverable"]
    persons = db.query(models.Person).all()
    results = []

    for person in persons:
        pending_batches = db.query(models.Batch).filter(
            models.Batch.person_id == person.id,
            models.Batch.status.in_(todo_statuses)
        ).all()

        batches_info = [
            {
                "batch_id": b.id,
                "batch_code": b.batch_code,
                "status": b.status,
                "updated_at": b.updated_at.isoformat() if b.updated_at else None
            }
            for b in pending_batches
        ]

        results.append(schemas.TodoItem(
            person_id=person.id,
            person_name=person.person_name,
            pending_count=len(pending_batches),
            batches=batches_info
        ))

    results.sort(key=lambda x: x.pending_count, reverse=True)
    return results


@app.post("/qc/anomaly-disposals", response_model=schemas.AnomalyDisposalResponse)
def create_anomaly_disposal(
    data: schemas.AnomalyDisposalCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_qc)
):
    valid_anomaly_types = ["retest_fail", "burnt_edge_high", "retest_overdue", "reroast_abnormal"]
    if data.anomaly_type not in valid_anomaly_types:
        raise HTTPException(status_code=400, detail=f"异常类型必须是: {', '.join(valid_anomaly_types)}")

    valid_severities = ["low", "medium", "high", "critical"]
    if data.severity not in valid_severities:
        raise HTTPException(status_code=400, detail=f"严重程度必须是: {', '.join(valid_severities)}")

    batch = db.query(models.Batch).filter(models.Batch.id == data.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")

    if data.process_record_id:
        record = db.query(models.ProcessRecord).filter(
            models.ProcessRecord.id == data.process_record_id,
            models.ProcessRecord.batch_id == data.batch_id
        ).first()
        if not record:
            raise HTTPException(status_code=404, detail="关联的复测记录不存在")
        if record.record_type != "retest":
            raise HTTPException(status_code=400, detail=f"只能关联复测记录，当前记录类型为: {record.record_type}")

    person = db.query(models.Person).filter(models.Person.id == data.responsible_person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="责任人不存在")

    if data.expected_completion_time <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="预计完成时间必须晚于当前时间")

    disposal_no = validators.generate_disposal_no(db)
    disposal = models.AnomalyDisposal(
        disposal_no=disposal_no,
        created_by=current_user.id,
        **data.model_dump()
    )
    db.add(disposal)
    db.commit()
    db.refresh(disposal)
    return disposal


@app.get("/qc/anomaly-disposals", response_model=List[schemas.AnomalyDisposalDetailResponse])
def list_anomaly_disposals(
    disposal_no: Optional[str] = Query(None, description="异常处置单编号"),
    batch_code: Optional[str] = Query(None, description="批次编码"),
    anomaly_type: Optional[str] = Query(None, description="异常类型"),
    severity: Optional[str] = Query(None, description="严重程度"),
    status: Optional[str] = Query(None, description="状态: pending/processing/completed/closed"),
    responsible_person_id: Optional[int] = Query(None, description="责任人ID"),
    date_from: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    only_my: bool = Query(False, description="仅查看我相关的"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    query = db.query(models.AnomalyDisposal)

    if current_user.role != "admin" or only_my:
        user_filter = validators.get_user_related_filter(db, current_user)
        if user_filter is not None:
            query = query.filter(user_filter)

    if disposal_no:
        query = query.filter(models.AnomalyDisposal.disposal_no.contains(disposal_no))
    if anomaly_type:
        query = query.filter(models.AnomalyDisposal.anomaly_type == anomaly_type)
    if severity:
        query = query.filter(models.AnomalyDisposal.severity == severity)
    if status:
        query = query.filter(models.AnomalyDisposal.status == status)
    if responsible_person_id:
        query = query.filter(models.AnomalyDisposal.responsible_person_id == responsible_person_id)
    if batch_code:
        query = query.join(models.Batch).filter(models.Batch.batch_code.contains(batch_code))
    if date_from:
        d_from = datetime.strptime(date_from, "%Y-%m-%d")
        query = query.filter(models.AnomalyDisposal.created_at >= d_from)
    if date_to:
        d_to = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
        query = query.filter(models.AnomalyDisposal.created_at < d_to)

    return query.order_by(models.AnomalyDisposal.created_at.desc()).offset(skip).limit(limit).all()


@app.get("/qc/anomaly-disposals/{disposal_id}", response_model=schemas.AnomalyDisposalDetailResponse)
def get_anomaly_disposal(
    disposal_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    disposal = db.query(models.AnomalyDisposal).filter(models.AnomalyDisposal.id == disposal_id).first()
    if not disposal:
        raise HTTPException(status_code=404, detail="异常处置单不存在")

    if not validators.is_user_related_to_disposal(db, current_user, disposal):
        raise HTTPException(status_code=403, detail="无权查看此异常处置单")

    return disposal


@app.put("/qc/anomaly-disposals/{disposal_id}", response_model=schemas.AnomalyDisposalResponse)
def update_anomaly_disposal(
    disposal_id: int,
    data: schemas.AnomalyDisposalUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_qc)
):
    disposal = db.query(models.AnomalyDisposal).filter(models.AnomalyDisposal.id == disposal_id).first()
    if not disposal:
        raise HTTPException(status_code=404, detail="异常处置单不存在")

    if not validators.is_user_related_to_disposal(db, current_user, disposal):
        raise HTTPException(status_code=403, detail="无权修改此异常处置单")

    if data.status:
        valid_statuses = ["pending", "processing", "completed", "closed"]
        if data.status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"状态必须是: {', '.join(valid_statuses)}")

        is_valid, msg = validators.validate_status_transition(disposal.status, data.status)
        if not is_valid:
            raise HTTPException(status_code=400, detail=msg)

        if data.status in ["completed", "closed"] and not data.final_result and not disposal.final_result:
            raise HTTPException(status_code=400, detail="完成或关闭处置单时必须填写最终处理结果")

        old_status = disposal.status
        if data.status == "completed" and old_status != "completed":
            disposal.completed_at = datetime.utcnow()
        elif old_status in ["completed", "closed"] and data.status not in ["completed", "closed"]:
            disposal.completed_at = None

    if data.severity:
        valid_severities = ["low", "medium", "high", "critical"]
        if data.severity not in valid_severities:
            raise HTTPException(status_code=400, detail=f"严重程度必须是: {', '.join(valid_severities)}")

    if data.responsible_person_id:
        person = db.query(models.Person).filter(models.Person.id == data.responsible_person_id).first()
        if not person:
            raise HTTPException(status_code=404, detail="责任人不存在")

    if data.expected_completion_time and data.expected_completion_time <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="预计完成时间必须晚于当前时间")

    update_data = data.model_dump(exclude_unset=True)
    if data.status in ["processing", "completed", "closed"]:
        update_data["handled_by"] = current_user.id

    for key, value in update_data.items():
        setattr(disposal, key, value)

    disposal.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(disposal)
    return disposal


@app.put("/qc/anomaly-disposals/{disposal_id}/status")
def update_disposal_status(
    disposal_id: int,
    new_status: str = Query(..., description="新状态: pending/processing/completed/closed"),
    final_result: Optional[str] = Query(None, description="最终处理结果（完成或关闭时必填）"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_qc)
):
    disposal = db.query(models.AnomalyDisposal).filter(models.AnomalyDisposal.id == disposal_id).first()
    if not disposal:
        raise HTTPException(status_code=404, detail="异常处置单不存在")

    if not validators.is_user_related_to_disposal(db, current_user, disposal):
        raise HTTPException(status_code=403, detail="无权修改此异常处置单状态")

    valid_statuses = ["pending", "processing", "completed", "closed"]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"状态必须是: {', '.join(valid_statuses)}")

    is_valid, msg = validators.validate_status_transition(disposal.status, new_status)
    if not is_valid:
        raise HTTPException(status_code=400, detail=msg)

    if new_status in ["completed", "closed"] and not final_result and not disposal.final_result:
        raise HTTPException(status_code=400, detail="完成或关闭处置单时必须填写最终处理结果")

    old_status = disposal.status
    disposal.status = new_status
    disposal.handled_by = current_user.id

    if new_status == "completed" and old_status != "completed":
        disposal.completed_at = datetime.utcnow()
    elif old_status in ["completed", "closed"] and new_status not in ["completed", "closed"]:
        disposal.completed_at = None

    if final_result:
        disposal.final_result = final_result

    disposal.updated_at = datetime.utcnow()
    db.commit()

    return {
        "message": "状态更新成功",
        "disposal_no": disposal.disposal_no,
        "old_status": old_status,
        "new_status": new_status
    }


@app.delete("/admin/anomaly-disposals/{disposal_id}")
def delete_anomaly_disposal(
    disposal_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    disposal = db.query(models.AnomalyDisposal).filter(models.AnomalyDisposal.id == disposal_id).first()
    if not disposal:
        raise HTTPException(status_code=404, detail="异常处置单不存在")

    db.delete(disposal)
    db.commit()
    return {"message": "删除成功"}


@app.get("/stats/anomaly-uncompleted")
def get_uncompleted_anomaly_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    return validators.get_uncompleted_anomaly_stats(db, current_user)


@app.get("/stats/anomaly-overdue", response_model=List[schemas.OverdueAnomalyItem])
def get_overdue_anomalies(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    return validators.get_overdue_anomalies(db, current_user)


@app.get("/stats/high-risk-fire-anomalies", response_model=List[schemas.HighRiskFireAnomalyItem])
def get_high_risk_fire_anomalies(
    min_batches: int = Query(5, description="最少批次数"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    return validators.get_high_risk_fire_anomalies(db, min_batches, current_user)


@app.get("/stats/anomaly-summary")
def get_anomaly_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    return validators.get_anomaly_summary(db, current_user)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8111)
