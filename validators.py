from datetime import datetime, timedelta
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session
import models
import schemas


def check_furnace_conflict(
    db: Session,
    furnace_id: int,
    plan_start: datetime,
    plan_end: datetime,
    exclude_batch_id: int = None
) -> list:
    conflicts = []
    active_statuses = ["pending_in", "roasting"]

    query = db.query(models.Batch).filter(
        models.Batch.furnace_id == furnace_id,
        models.Batch.status.in_(active_statuses)
    )
    if exclude_batch_id:
        query = query.filter(models.Batch.id != exclude_batch_id)

    batches = query.all()

    for batch in batches:
        b_start = batch.plan_roast_start or batch.actual_roast_start
        b_end = batch.plan_roast_end or batch.actual_roast_end

        if not b_start or not b_end:
            conflicts.append({
                "batch_code": batch.batch_code,
                "reason": "该批次已占用炉号但时间信息不完整"
            })
            continue

        has_overlap = (plan_start <= b_end) and (plan_end >= b_start)
        if has_overlap:
            conflicts.append({
                "batch_code": batch.batch_code,
                "reason": f"时间重叠: 该批次 {b_start.strftime('%Y-%m-%d %H:%M')} ~ {b_end.strftime('%Y-%m-%d %H:%M')}"
            })

    return conflicts


def check_retest_overdue(db: Session) -> list:
    alerts = []
    now = datetime.utcnow()
    pending_retest = db.query(models.Batch).filter(
        models.Batch.status == "pending_retest",
        models.Batch.retest_deadline.isnot(None)
    ).all()

    for batch in pending_retest:
        if batch.retest_deadline < now:
            hours_overdue = (now - batch.retest_deadline).total_seconds() / 3600
            level = "critical" if hours_overdue > 48 else "warning"
            alerts.append(schemas.AlertItem(
                alert_type="retest_overdue",
                alert_level=level,
                batch_code=batch.batch_code,
                message=f"复测超期 {hours_overdue:.1f} 小时",
                related_data={
                    "retest_deadline": batch.retest_deadline.isoformat(),
                    "person_id": batch.person_id
                }
            ))
    return alerts


def check_burnt_edge_concentration(db: Session, threshold: float = 0.3, min_batches: int = 5) -> list:
    alerts = []
    fire_levels = db.query(models.FireLevel).all()

    for fl in fire_levels:
        batches = db.query(models.Batch).filter(
            models.Batch.fire_level_id == fl.id
        ).all()

        if len(batches) < min_batches:
            continue

        burnt_count = 0
        for batch in batches:
            latest_retest = db.query(models.ProcessRecord).filter(
                models.ProcessRecord.batch_id == batch.id,
                models.ProcessRecord.record_type == "retest",
                models.ProcessRecord.burnt_edge_level >= 3
            ).first()
            if latest_retest:
                burnt_count += 1

        rate = burnt_count / len(batches)
        if rate >= threshold:
            alerts.append(schemas.AlertItem(
                alert_type="burnt_edge_concentration",
                alert_level="warning",
                batch_code=None,
                message=f"火候等级 [{fl.level_code} {fl.level_name}] 焦边集中率 {rate:.1%}（超过阈值 {threshold:.0%}）",
                related_data={
                    "fire_level_id": fl.id,
                    "fire_level_code": fl.level_code,
                    "total_batches": len(batches),
                    "burnt_count": burnt_count,
                    "rate": rate
                }
            ))
    return alerts


def check_reroast_missing_retest(db: Session) -> list:
    alerts = []
    need_reroast = db.query(models.Batch).filter(
        models.Batch.status == "need_reroast"
    ).all()

    for batch in need_reroast:
        reroast_records = db.query(models.ProcessRecord).filter(
            models.ProcessRecord.batch_id == batch.id,
            models.ProcessRecord.record_type == "in_furnace"
        ).all()

        if len(reroast_records) > 1:
            latest_retest = db.query(models.ProcessRecord).filter(
                models.ProcessRecord.batch_id == batch.id,
                models.ProcessRecord.record_type == "retest"
            ).order_by(models.ProcessRecord.recorded_at.desc()).first()

            last_in_furnace = reroast_records[-1]

            if not latest_retest or latest_retest.recorded_at < last_in_furnace.recorded_at:
                alerts.append(schemas.AlertItem(
                    alert_type="reroast_missing_retest",
                    alert_level="warning",
                    batch_code=batch.batch_code,
                    message="返焙后缺少复测结论",
                    related_data={
                        "last_reroast_at": last_in_furnace.recorded_at.isoformat(),
                        "roast_count": batch.roast_count
                    }
                ))
    return alerts


def check_person_todo_backlog(db: Session, threshold: int = 5) -> list:
    alerts = []
    todo_statuses = ["pending_in", "roasting", "standing", "pending_retest", "need_reroast", "deliverable"]

    persons = db.query(models.Person).all()
    for person in persons:
        pending_count = db.query(models.Batch).filter(
            models.Batch.person_id == person.id,
            models.Batch.status.in_(todo_statuses)
        ).count()

        if pending_count >= threshold:
            pending_batches = db.query(models.Batch).filter(
                models.Batch.person_id == person.id,
                models.Batch.status.in_(todo_statuses)
            ).all()
            batches_info = [
                {"batch_code": b.batch_code, "status": b.status}
                for b in pending_batches
            ]
            level = "critical" if pending_count >= threshold * 2 else "warning"
            alerts.append(schemas.AlertItem(
                alert_type="person_backlog",
                alert_level=level,
                batch_code=None,
                message=f"责任人 [{person.person_no} {person.person_name}] 待办堆积 {pending_count} 项",
                related_data={
                    "person_id": person.id,
                    "pending_count": pending_count,
                    "batches": batches_info
                }
            ))
    return alerts


def get_all_alerts(db: Session) -> list:
    all_alerts = []
    all_alerts.extend(check_retest_overdue(db))
    all_alerts.extend(check_burnt_edge_concentration(db))
    all_alerts.extend(check_reroast_missing_retest(db))
    all_alerts.extend(check_person_todo_backlog(db))
    all_alerts.extend(check_anomaly_overdue(db))
    return all_alerts


def generate_batch_code(db: Session) -> str:
    now = datetime.now()
    prefix = now.strftime("%Y%m%d")
    last_batch = db.query(models.Batch).filter(
        models.Batch.batch_code.like(f"{prefix}%")
    ).order_by(models.Batch.batch_code.desc()).first()

    if last_batch:
        try:
            seq = int(last_batch.batch_code[-4:]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


ANOMALY_TYPE_NAMES = {
    "retest_fail": "复测不通过",
    "burnt_edge_high": "焦边等级偏高",
    "retest_overdue": "复测超期",
    "reroast_abnormal": "返焙后仍异常"
}

SEVERITY_NAMES = {
    "low": "低",
    "medium": "中",
    "high": "高",
    "critical": "严重"
}

STATUS_NAMES = {
    "pending": "待处理",
    "processing": "处理中",
    "completed": "已完成",
    "closed": "已关闭"
}


def generate_disposal_no(db: Session) -> str:
    now = datetime.now()
    prefix = f"AD{now.strftime('%Y%m%d')}"
    last_disposal = db.query(models.AnomalyDisposal).filter(
        models.AnomalyDisposal.disposal_no.like(f"{prefix}%")
    ).order_by(models.AnomalyDisposal.disposal_no.desc()).first()

    if last_disposal:
        try:
            seq = int(last_disposal.disposal_no[-4:]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


STATUS_TRANSITIONS = {
    "pending": ["processing", "closed"],
    "processing": ["pending", "completed", "closed"],
    "completed": ["processing"],
    "closed": []
}


def validate_status_transition(old_status: str, new_status: str) -> tuple:
    if old_status == new_status:
        return True, ""
    allowed = STATUS_TRANSITIONS.get(old_status, [])
    if new_status not in allowed:
        return False, f"状态流转不允许: {STATUS_NAMES.get(old_status, old_status)} → {STATUS_NAMES.get(new_status, new_status)}。允许的流转: {', '.join([STATUS_NAMES.get(s, s) for s in allowed]) if allowed else '无'}"
    return True, ""


def get_user_related_filter(db: Session, current_user: models.User):
    if not current_user:
        return None
    if current_user.role == "admin":
        return None
    my_person = db.query(models.Person).filter(
        models.Person.person_name == current_user.full_name
    ).first()
    if my_person:
        return or_(
            models.AnomalyDisposal.created_by == current_user.id,
            models.AnomalyDisposal.responsible_person_id == my_person.id
        )
    return models.AnomalyDisposal.created_by == current_user.id


def is_user_related_to_disposal(db: Session, current_user: models.User, disposal: models.AnomalyDisposal) -> bool:
    if current_user.role == "admin":
        return True
    my_person = db.query(models.Person).filter(
        models.Person.person_name == current_user.full_name
    ).first()
    if disposal.created_by == current_user.id:
        return True
    return bool(my_person and disposal.responsible_person_id == my_person.id)


def check_anomaly_overdue(db: Session, current_user: models.User = None) -> list:
    alerts = []
    now = datetime.utcnow()
    active_statuses = ["pending", "processing"]

    query = db.query(models.AnomalyDisposal).filter(
        models.AnomalyDisposal.status.in_(active_statuses),
        models.AnomalyDisposal.expected_completion_time.isnot(None)
    )

    user_filter = get_user_related_filter(db, current_user)
    if user_filter is not None:
        query = query.filter(user_filter)

    overdue_disposals = query.all()

    for disposal in overdue_disposals:
        if disposal.expected_completion_time < now:
            hours_overdue = (now - disposal.expected_completion_time).total_seconds() / 3600
            level = "critical" if hours_overdue > 24 else "warning"
            batch = db.query(models.Batch).filter(models.Batch.id == disposal.batch_id).first()
            alerts.append(schemas.AlertItem(
                alert_type="anomaly_overdue",
                alert_level=level,
                batch_code=batch.batch_code if batch else None,
                message=f"异常处置单 [{disposal.disposal_no}] 超期 {hours_overdue:.1f} 小时",
                related_data={
                    "disposal_id": disposal.id,
                    "disposal_no": disposal.disposal_no,
                    "anomaly_type": disposal.anomaly_type,
                    "severity": disposal.severity,
                    "expected_completion_time": disposal.expected_completion_time.isoformat(),
                    "responsible_person_id": disposal.responsible_person_id
                }
            ))
    return alerts


def get_uncompleted_anomaly_stats(db: Session, current_user: models.User = None) -> dict:
    active_statuses = ["pending", "processing"]

    base_query = db.query(models.AnomalyDisposal).filter(
        models.AnomalyDisposal.status.in_(active_statuses)
    )

    user_filter = get_user_related_filter(db, current_user)
    if user_filter is not None:
        base_query = base_query.filter(user_filter)

    total = base_query.count()

    stats = []
    for anomaly_type, type_name in ANOMALY_TYPE_NAMES.items():
        query = db.query(models.AnomalyDisposal).filter(
            models.AnomalyDisposal.anomaly_type == anomaly_type,
            models.AnomalyDisposal.status.in_(active_statuses)
        )
        if user_filter is not None:
            query = query.filter(user_filter)
        count = query.count()
        if count > 0:
            stats.append(schemas.AnomalyStatsItem(
                anomaly_type=anomaly_type,
                anomaly_type_name=type_name,
                count=count
            ))

    return {"total_uncompleted": total, "by_type": stats}


def get_overdue_anomalies(db: Session, current_user: models.User = None) -> list:
    now = datetime.utcnow()
    active_statuses = ["pending", "processing"]

    query = db.query(models.AnomalyDisposal).filter(
        models.AnomalyDisposal.status.in_(active_statuses),
        models.AnomalyDisposal.expected_completion_time < now
    )

    user_filter = get_user_related_filter(db, current_user)
    if user_filter is not None:
        query = query.filter(user_filter)

    disposals = query.order_by(models.AnomalyDisposal.expected_completion_time.asc()).all()

    result = []
    for disposal in disposals:
        hours_overdue = (now - disposal.expected_completion_time).total_seconds() / 3600
        batch = db.query(models.Batch).filter(models.Batch.id == disposal.batch_id).first()
        person = db.query(models.Person).filter(models.Person.id == disposal.responsible_person_id).first()
        result.append(schemas.OverdueAnomalyItem(
            disposal_id=disposal.id,
            disposal_no=disposal.disposal_no,
            batch_code=batch.batch_code if batch else "",
            anomaly_type=disposal.anomaly_type,
            severity=disposal.severity,
            responsible_person_name=person.person_name if person else "",
            expected_completion_time=disposal.expected_completion_time,
            overdue_hours=round(hours_overdue, 1),
            status=disposal.status
        ))
    return result


def get_high_risk_fire_anomalies(db: Session, min_batches: int = 5, current_user: models.User = None) -> list:
    results = []
    fire_levels = db.query(models.FireLevel).all()

    user_filter = get_user_related_filter(db, current_user)

    for fl in fire_levels:
        total_query = db.query(models.Batch).filter(models.Batch.fire_level_id == fl.id)
        if user_filter is not None:
            total_query = total_query.join(models.AnomalyDisposal).filter(
                models.AnomalyDisposal.status.in_(["pending", "processing"]),
                user_filter
            )
        total = total_query.distinct(models.Batch.id).count()
        if total < min_batches:
            continue

        anomaly_query = db.query(models.AnomalyDisposal).join(models.Batch).filter(
            models.Batch.fire_level_id == fl.id,
            models.AnomalyDisposal.status.in_(["pending", "processing"])
        )
        if user_filter is not None:
            anomaly_query = anomaly_query.filter(user_filter)

        anomaly_count = anomaly_query.distinct(models.AnomalyDisposal.id).count()

        if anomaly_count > 0:
            rate = anomaly_count / total if total > 0 else 0
            results.append(schemas.HighRiskFireAnomalyItem(
                fire_level_id=fl.id,
                fire_level_code=fl.level_code,
                fire_level_name=fl.level_name,
                anomaly_count=anomaly_count,
                total_batches=total,
                anomaly_rate=round(rate, 4)
            ))

    results.sort(key=lambda x: x.anomaly_rate, reverse=True)
    return results


def get_anomaly_summary(db: Session, current_user: models.User = None) -> dict:
    now = datetime.utcnow()
    active_statuses = ["pending", "processing"]

    user_filter = get_user_related_filter(db, current_user)

    total_active_query = db.query(models.AnomalyDisposal).filter(
        models.AnomalyDisposal.status.in_(active_statuses)
    )
    if user_filter is not None:
        total_active_query = total_active_query.filter(user_filter)
    total_active = total_active_query.count()

    overdue_query = db.query(models.AnomalyDisposal).filter(
        models.AnomalyDisposal.status.in_(active_statuses),
        models.AnomalyDisposal.expected_completion_time < now
    )
    if user_filter is not None:
        overdue_query = overdue_query.filter(user_filter)
    overdue_count = overdue_query.count()

    critical_query = db.query(models.AnomalyDisposal).filter(
        models.AnomalyDisposal.status.in_(active_statuses),
        models.AnomalyDisposal.severity == "critical"
    )
    if user_filter is not None:
        critical_query = critical_query.filter(user_filter)
    critical_count = critical_query.count()

    high_query = db.query(models.AnomalyDisposal).filter(
        models.AnomalyDisposal.status.in_(active_statuses),
        models.AnomalyDisposal.severity == "high"
    )
    if user_filter is not None:
        high_query = high_query.filter(user_filter)
    high_count = high_query.count()

    today_created_query = db.query(models.AnomalyDisposal).filter(
        func.date(models.AnomalyDisposal.created_at) == func.date(now)
    )
    if user_filter is not None:
        today_created_query = today_created_query.filter(user_filter)
    today_created = today_created_query.count()

    today_completed_query = db.query(models.AnomalyDisposal).filter(
        func.date(models.AnomalyDisposal.completed_at) == func.date(now)
    )
    if user_filter is not None:
        today_completed_query = today_completed_query.filter(user_filter)
    today_completed = today_completed_query.count()

    return {
        "total_active": total_active,
        "overdue_count": overdue_count,
        "critical_count": critical_count,
        "high_count": high_count,
        "today_created": today_created,
        "today_completed": today_completed
    }


VALID_DELIVERY_BATCH_STATUSES = ["deliverable", "delivered"]

QUALITY_CONCLUSION_NAMES = {
    "qualified": "合格",
    "conditional_qualified": "条件合格",
    "unqualified": "不合格"
}


def generate_delivery_no(db: Session) -> str:
    now = datetime.now()
    prefix = f"DC{now.strftime('%Y%m%d')}"
    last_delivery = db.query(models.DeliveryConfirmation).filter(
        models.DeliveryConfirmation.delivery_no.like(f"{prefix}%")
    ).order_by(models.DeliveryConfirmation.delivery_no.desc()).first()

    if last_delivery:
        try:
            seq = int(last_delivery.delivery_no[-4:]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


def validate_batch_delivery_eligibility(batch: models.Batch) -> tuple:
    if batch.status not in VALID_DELIVERY_BATCH_STATUSES:
        return False, f"批次当前状态为 '{batch.status}'，不允许交付。仅状态为 'deliverable' 或 'delivered' 的批次可发起交付确认"
    return True, ""
