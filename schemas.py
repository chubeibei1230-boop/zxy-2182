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


class AnomalyDisposalBase(BaseModel):
    batch_id: int = Field(..., description="批次ID")
    process_record_id: Optional[int] = Field(None, description="关联的复测记录ID")
    anomaly_type: str = Field(..., description="异常类型: retest_fail/burnt_edge_high/retest_overdue/reroast_abnormal")
    severity: str = Field(..., description="严重程度: low/medium/high/critical")
    reason_description: str = Field(..., description="原因说明")
    disposal_suggestion: str = Field(..., description="处置建议")
    responsible_person_id: int = Field(..., description="责任人ID")
    expected_completion_time: datetime = Field(..., description="预计完成时间")


class AnomalyDisposalCreate(AnomalyDisposalBase):
    pass


class AnomalyDisposalUpdate(BaseModel):
    status: Optional[str] = Field(None, description="状态: pending/processing/completed/closed")
    final_result: Optional[str] = Field(None, description="最终处理结果")
    severity: Optional[str] = Field(None, description="严重程度: low/medium/high/critical")
    reason_description: Optional[str] = Field(None, description="原因说明")
    disposal_suggestion: Optional[str] = Field(None, description="处置建议")
    responsible_person_id: Optional[int] = Field(None, description="责任人ID")
    expected_completion_time: Optional[datetime] = Field(None, description="预计完成时间")


class AnomalyDisposalResponse(BaseModel):
    id: int
    disposal_no: str
    batch_id: int
    process_record_id: Optional[int]
    anomaly_type: str
    severity: str
    reason_description: str
    disposal_suggestion: str
    responsible_person_id: int
    expected_completion_time: datetime
    final_result: Optional[str]
    status: str
    created_by: int
    handled_by: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class AnomalyDisposalDetailResponse(AnomalyDisposalResponse):
    batch: Optional[BatchDetailResponse] = None
    process_record: Optional[ProcessRecordResponse] = None
    responsible_person: Optional[PersonResponse] = None
    creator: Optional[UserResponse] = None
    handler: Optional[UserResponse] = None


class AnomalyStatsItem(BaseModel):
    anomaly_type: str
    anomaly_type_name: str
    count: int


class OverdueAnomalyItem(BaseModel):
    disposal_id: int
    disposal_no: str
    batch_code: str
    anomaly_type: str
    severity: str
    responsible_person_name: str
    expected_completion_time: datetime
    overdue_hours: float
    status: str


class HighRiskFireAnomalyItem(BaseModel):
    fire_level_id: int
    fire_level_code: str
    fire_level_name: str
    anomaly_count: int
    total_batches: int
    anomaly_rate: float


class DeliveryConfirmationBase(BaseModel):
    batch_id: int = Field(..., description="批次ID")
    delivery_quantity: float = Field(..., description="交付数量(kg)")
    delivery_target: str = Field(..., description="交付对象")
    delivery_time: datetime = Field(..., description="交付时间")
    delivery_remarks: Optional[str] = Field(None, description="交付备注")
    quality_conclusion: str = Field(..., description="质量确认结论: qualified/conditional_qualified/unqualified")


class DeliveryConfirmationCreate(DeliveryConfirmationBase):
    pass


class DeliveryConfirmationUpdate(BaseModel):
    delivery_quantity: Optional[float] = Field(None, description="交付数量(kg)")
    delivery_target: Optional[str] = Field(None, description="交付对象")
    delivery_time: Optional[datetime] = Field(None, description="交付时间")
    delivery_remarks: Optional[str] = Field(None, description="交付备注")
    quality_conclusion: Optional[str] = Field(None, description="质量确认结论: qualified/conditional_qualified/unqualified")
    status: Optional[str] = Field(None, description="状态: confirmed/cancelled")


class DeliveryConfirmationResponse(BaseModel):
    id: int
    delivery_no: str
    batch_id: int
    delivery_quantity: float
    delivery_target: str
    delivery_time: datetime
    delivery_remarks: Optional[str]
    quality_conclusion: str
    status: str
    confirmed_by: int
    confirmed_at: datetime
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class DeliveryConfirmationDetailResponse(DeliveryConfirmationResponse):
    batch: Optional[BatchDetailResponse] = None
    confirmer: Optional[UserResponse] = None


class DeliverySummaryResponse(BaseModel):
    pending_delivery_count: int = Field(..., description="待交付数量")
    delivered_count: int = Field(..., description="已交付数量")
    recent_7day_trend: List[DeliveryTrendItem] = Field(..., description="近7日交付趋势")
