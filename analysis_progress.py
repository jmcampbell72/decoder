from datetime import datetime
from app import db
from models import AnalysisEvent

ANALYSIS_STAGES = [
    {
        'stage': 'team_ready',
        'label': 'Code Analysis Team Getting Ready',
        'order': 1
    },
    {
        'stage': 'architect_analysis',
        'label': 'Architect Performing Code Analysis',
        'order': 2
    },
    {
        'stage': 'business_analyst',
        'label': 'Business Analyst Reviewing Code Intent',
        'order': 3
    },
    {
        'stage': 'app_architect',
        'label': 'Application Architect Analyzing Code Patterns',
        'order': 4
    },
    {
        'stage': 'data_flow_expert',
        'label': 'Data Flow Expert Analyzing Code Flow',
        'order': 5
    },
    {
        'stage': 'consolidation',
        'label': 'Architect Consolidating and Discussing Results with Team',
        'order': 6
    },
    {
        'stage': 'completed',
        'label': 'Analysis Completed',
        'order': 7
    }
]


def initialize_analysis_events(analysis_id):
    """
    Initialize all analysis event records for a given analysis
    
    Args:
        analysis_id: The ID of the analysis to create events for
        
    Returns:
        List of created AnalysisEvent objects
    """
    events = []
    for stage_config in ANALYSIS_STAGES:
        event = AnalysisEvent(
            analysis_id=analysis_id,
            stage=stage_config['stage'],
            stage_label=stage_config['label'],
            status='pending',
            order_index=stage_config['order'],
            progress_percentage=0
        )
        db.session.add(event)
        events.append(event)
    
    db.session.commit()
    return events


def update_analysis_event(analysis_id, stage, status='in_progress', progress=None, message=None):
    """
    Update the status of a specific analysis event
    
    Args:
        analysis_id: The ID of the analysis
        stage: The stage to update (e.g., 'architect_analysis')
        status: The new status ('pending', 'in_progress', 'completed', 'error')
        progress: Optional progress percentage (0-100)
        message: Optional status message
        
    Returns:
        The updated AnalysisEvent object or None if not found
    """
    event = AnalysisEvent.query.filter_by(
        analysis_id=analysis_id,
        stage=stage
    ).first()
    
    if not event:
        return None
    
    event.status = status
    
    if status == 'in_progress' and not event.started_at:
        event.started_at = datetime.utcnow()
    
    if status == 'completed':
        event.completed_at = datetime.utcnow()
        event.progress_percentage = 100
    elif progress is not None:
        event.progress_percentage = progress
    
    if message:
        event.message = message
    
    db.session.commit()
    return event


def get_analysis_progress(analysis_id):
    """
    Get the current progress of an analysis
    
    Args:
        analysis_id: The ID of the analysis
        
    Returns:
        Dictionary with progress information
    """
    events = AnalysisEvent.query.filter_by(analysis_id=analysis_id)\
        .order_by(AnalysisEvent.order_index).all()
    
    if not events:
        return {
            'status': 'not_found',
            'events': [],
            'overall_progress': 0
        }
    
    completed_count = sum(1 for e in events if e.status == 'completed')
    total_count = len(events)
    overall_progress = int((completed_count / total_count) * 100) if total_count > 0 else 0
    
    current_stage = None
    for event in events:
        if event.status == 'in_progress':
            current_stage = event.stage
            break
    
    return {
        'status': 'success',
        'events': [e.to_dict() for e in events],
        'overall_progress': overall_progress,
        'current_stage': current_stage,
        'completed_count': completed_count,
        'total_count': total_count
    }
