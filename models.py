from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, Date
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # admin / qc
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    records = relationship("ProcessRecord", back_populates="recorder")


class TeaStock(Base):
    __tablename__ = "tea_stocks"

    id = Column(Integer, primary_key=True, index=True)
    batch_no = Column(String(50), unique=True, index=True, nullable=False)
    tea_name = Column(String(100), nullable=False)
    origin = Column(String(200))
    weight = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    batches = relationship("Batch", back_populates="tea_stock")


class Furnace(Base):
    __tablename__ = "furnaces"

    id = Column(Integer, primary_key=True, index=True)
    furnace_no = Column(String(50), unique=True, index=True, nullable=False)
    furnace_name = Column(String(100))
    capacity = Column(Float)
    status = Column(String(20), default="idle")  # idle / in_use / maintenance
    created_at = Column(DateTime, default=datetime.utcnow)

    batches = relationship("Batch", back_populates="furnace")


class FireLevel(Base):
    __tablename__ = "fire_levels"

    id = Column(Integer, primary_key=True, index=True)
    level_code = Column(String(50), unique=True, index=True, nullable=False)
    level_name = Column(String(100), nullable=False)
    description = Column(Text)
    temp_min = Column(Integer)
    temp_max = Column(Integer)

    batches = relationship("Batch", back_populates="fire_level")


class Cabinet(Base):
    __tablename__ = "cabinets"

    id = Column(Integer, primary_key=True, index=True)
    cabinet_no = Column(String(50), unique=True, index=True, nullable=False)
    location = Column(String(200))
    status = Column(String(20), default="empty")  # empty / in_use

    batches = relationship("Batch", back_populates="cabinet")


class Person(Base):
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, index=True)
    person_no = Column(String(50), unique=True, index=True, nullable=False)
    person_name = Column(String(100), nullable=False)
    department = Column(String(100))
    phone = Column(String(50))

    batches = relationship("Batch", back_populates="person")


class Batch(Base):
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True, index=True)
    batch_code = Column(String(50), unique=True, index=True, nullable=False)
    tea_stock_id = Column(Integer, ForeignKey("tea_stocks.id"), nullable=False)
    furnace_id = Column(Integer, ForeignKey("furnaces.id"), nullable=False)
    fire_level_id = Column(Integer, ForeignKey("fire_levels.id"), nullable=False)
    cabinet_id = Column(Integer, ForeignKey("cabinets.id"))
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    status = Column(String(20), default="pending_in")  # pending_in/roasting/standing/pending_retest/need_reroast/deliverable/paused
    retest_cycle_hours = Column(Integer, default=24)
    roast_count = Column(Integer, default=0)
    plan_roast_start = Column(DateTime)
    plan_roast_end = Column(DateTime)
    actual_roast_start = Column(DateTime)
    actual_roast_end = Column(DateTime)
    cabinet_start = Column(DateTime)
    retest_deadline = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    tea_stock = relationship("TeaStock", back_populates="batches")
    furnace = relationship("Furnace", back_populates="batches")
    fire_level = relationship("FireLevel", back_populates="batches")
    cabinet = relationship("Cabinet", back_populates="batches")
    person = relationship("Person", back_populates="batches")
    process_records = relationship("ProcessRecord", back_populates="batch", cascade="all, delete-orphan")


class ProcessRecord(Base):
    __tablename__ = "process_records"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False)
    record_type = Column(String(30), nullable=False)  # in_furnace/out_furnace/to_cabinet/retest/delivery
    temperature = Column(Float)
    aroma_description = Column(Text)
    moisture_level = Column(String(50))
    burnt_edge_level = Column(Integer)  # 0-5
    retest_conclusion = Column(String(20))  # pass/fail/re-roast
    delivery_suggestion = Column(Text)
    remarks = Column(Text)
    recorder_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    batch = relationship("Batch", back_populates="process_records")
    recorder = relationship("User", back_populates="records")
