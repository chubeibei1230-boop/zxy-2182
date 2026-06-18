from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class UserBase(BaseModel):
    username: str
    full_name: str
    role: str


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class TeaStockBase(BaseModel):
    batch_no: str = Field(..., description="茶坯批号")
    tea_name: str = Field(..., description="茶叶名称")
    origin: Optional[str] = Field(None, description="产地")
    weight: Optional[float] = Field(None, description="重量(kg)")


class TeaStockCreate(TeaStockBase):
    pass


class TeaStockResponse(TeaStockBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class FurnaceBase(BaseModel):
    furnace_no: str = Field(..., description="焙火炉号")
    furnace_name: Optional[str] = Field(None, description="炉名")
    capacity: Optional[float] = Field(None, description="容量(kg)")


class FurnaceCreate(FurnaceBase):
    pass


class FurnaceResponse(FurnaceBase):
    id: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class FireLevelBase(BaseModel):
    level_code: str = Field(..., description="火候等级编码")
    level_name: str = Field(..., description="火候等级名称")
    description: Optional[str] = Field(None, description="火候描述")
    temp_min: Optional[int] = Field(None, description="最低温度")
    temp_max: Optional[int] = Field(None, description="最高温度")


class FireLevelCreate(FireLevelBase):
    pass


class FireLevelResponse(FireLevelBase):
    id: int

    class Config:
        from_attributes = True


class CabinetBase(BaseModel):
    cabinet_no: str = Field(..., description="静置柜位号")
    location: Optional[str] = Field(None, description="位置")


class CabinetCreate(CabinetBase):
    pass


class CabinetResponse(CabinetBase):
    id: int
    status: str

    class Config:
        from_attributes = True


class PersonBase(BaseModel):
    person_no: str = Field(..., description="责任人编号")
    person_name: str = Field(..., description="责任人姓名")
    department: Optional[str] = Field(None, description="部门")
    phone: Optional[str] = Field(None, description="联系电话")


class PersonCreate(PersonBase):
    pass


class PersonResponse(PersonBase):
    id: int

    class Config:
        from_attributes = True


class BatchBase(BaseModel):
    tea_stock_id: int = Field(..., description="茶坯ID")
    furnace_id: int = Field(..., description="焙火炉ID")
    fire_level_id: int = Field(..., description="火候等级ID")
    cabinet_id: Optional[int] = Field(None, description="静置柜位ID")
    person_id: int = Field(..., description="责任人ID")
    retest_cycle_hours: int = Field(24, description="复测周期(小时)")
    plan_roast_start: Optional[datetime] = Field(None, description="计划入炉时间")
    plan_roast_end: Optional[datetime] = Field(None, description="计划出炉时间")


class BatchCreate(BatchBase):
    pass


class BatchResponse(BaseModel):
    id: int
    batch_code: str
    tea_stock_id: int
    furnace_id: int
    fire_level_id: int
    cabinet_id: Optional[int]
    person_id: int
    status: str
    retest_cycle_hours: int
    roast_count: int
    plan_roast_start: Optional[datetime]
    plan_roast_end: Optional[datetime]
    actual_roast_start: Optional[datetime]
    actual_roast_end: Optional[datetime]
    cabinet_start: Optional[datetime]
    retest_deadline: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class BatchDetailResponse(BatchResponse):
    tea_stock: Optional[TeaStockResponse] = None
    furnace: Optional[FurnaceResponse] = None
    fire_level: Optional[FireLevelResponse] = None
    cabinet: Optional[CabinetResponse] = None
    person: Optional[PersonResponse] = None


class ProcessRecordBase(BaseModel):
    batch_id: int = Field(..., description="批次ID")
    record_type: str = Field(..., description="记录类型: in_furnace/out_furnace/to_cabinet/retest/delivery")
    temperature: Optional[float] = Field(None, description="温度")
    aroma_description: Optional[str] = Field(None, description="香气描述")
    moisture_level: Optional[str] = Field(None, description="含水占位")
    burnt_edge_level: Optional[int] = Field(None, description="焦边等级 0-5")
    retest_conclusion: Optional[str] = Field(None, description="复测结论: pass/fail/re-roast")
    delivery_suggestion: Optional[str] = Field(None, description="交付建议")
    remarks: Optional[str] = Field(None, description="备注")


class ProcessRecordCreate(ProcessRecordBase):
    pass


class ProcessRecordResponse(ProcessRecordBase):
    id: int
    recorder_id: int
    recorded_at: datetime

    class Config:
        from_attributes = True


class BatchQueryParams(BaseModel):
    batch_no: Optional[str] = None
    batch_code: Optional[str] = None
    furnace_no: Optional[str] = None
    fire_level_id: Optional[int] = None
    person_id: Optional[int] = None
    status: Optional[str] = None
    burnt_edge_level: Optional[int] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None


class AlertItem(BaseModel):
    alert_type: str
    alert_level: str
    batch_code: Optional[str] = None
    message: str
    related_data: Optional[dict] = None


class HighRiskFireItem(BaseModel):
    fire_level_id: int
    fire_level_code: str
    fire_level_name: str
    total_batches: int
    burnt_edge_count: int
    risk_rate: float


class DeliveryTrendItem(BaseModel):
    date: str
    total_batches: int
    delivered_count: int
    delivery_rate: float


class TodoItem(BaseModel):
    person_id: int
    person_name: str
    pending_count: int
    batches: List[dict]
