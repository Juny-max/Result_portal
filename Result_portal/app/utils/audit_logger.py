from datetime import datetime
from app import db
from app.models import AuditLog

def log_admin_action(admin_id, action, entity_type=None, entity_id=None, details=None):
    """
    Log an admin action to the audit log
    
    Args:
        admin_id (int): ID of the admin performing the action
        action (str): Action performed (e.g., 'create', 'update', 'delete')
        entity_type (str, optional): Type of entity being acted upon (e.g., 'result', 'student')
        entity_id (int, optional): ID of the entity being acted upon
        details (str, optional): Additional details about the action
    """
    try:
        log_entry = AuditLog(
            admin_id=admin_id,
            action=action,
            target_type=entity_type,
            target_id=entity_id,
            details=details,
            timestamp=datetime.utcnow()
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to log admin action: {str(e)}", exc_info=True)
