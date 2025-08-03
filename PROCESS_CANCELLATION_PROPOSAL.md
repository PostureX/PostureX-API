# Process Cancellation Implementation Proposal

## Current Problem
The system lacks mechanisms to cancel ongoing analysis processes when delete operations are performed, leading to:
- Resource waste (threads continue running)
- Race conditions (processing deleted files)
- Inconsistent database states
- Potential memory leaks

## Proposed Solutions

### Solution 1: Thread Tracking with Cancellation Flags

```python
# Global thread tracking
active_analysis_threads = {}
thread_cancellation_flags = {}

class CancellableAnalysisThread:
    def __init__(self, user_id, session_id, model_name, app):
        self.user_id = user_id
        self.session_id = session_id
        self.cancelled = False
        self.thread_id = f"{user_id}_{session_id}"
        
    def cancel(self):
        self.cancelled = True
        
    def is_cancelled(self):
        return self.cancelled

def process_session_files_cancellable(user_id, session_id, model_name, app):
    """Enhanced process function with cancellation support"""
    thread_id = f"{user_id}_{session_id}"
    
    # Check for cancellation at key points
    if thread_id in thread_cancellation_flags and thread_cancellation_flags[thread_id]:
        print(f"Analysis cancelled for session {session_id}")
        return
        
    # ... existing processing logic with cancellation checks ...
    
    for obj in objects:
        # Check cancellation before processing each file
        if thread_id in thread_cancellation_flags and thread_cancellation_flags[thread_id]:
            print(f"Analysis cancelled during processing for session {session_id}")
            return
            
        # ... file processing ...

def cancel_analysis_processing(user_id, session_id):
    """Cancel active analysis for a session"""
    thread_id = f"{user_id}_{session_id}"
    thread_cancellation_flags[thread_id] = True
    
    # Update database status
    analysis = Analysis.query.filter_by(user_id=user_id, session_id=session_id).first()
    if analysis and analysis.status == "in_progress":
        analysis.status = "cancelled"
        db.session.commit()
```

### Solution 2: Database-Based Cancellation

```python
# Add 'cancelled' status to Analysis model
def process_session_files_with_db_check(user_id, session_id, model_name, app):
    """Process with database status checks"""
    with app.app_context():
        # Check if analysis was cancelled
        analysis = Analysis.query.filter_by(user_id=user_id, session_id=session_id).first()
        if not analysis or analysis.status == "cancelled":
            print(f"Analysis cancelled or not found for session {session_id}")
            return
            
        for obj in objects:
            # Periodic cancellation checks
            analysis = Analysis.query.filter_by(user_id=user_id, session_id=session_id).first()
            if not analysis or analysis.status == "cancelled":
                print(f"Analysis cancelled during processing for session {session_id}")
                return
                
            # ... file processing ...
```

### Solution 3: WebSocket Connection Management

```python
# Track WebSocket connections for cancellation
active_websocket_connections = {}

class MediaAnalysisService:
    def __init__(self, websocket_host, websocket_port, service_token, user_id=None, session_id=None):
        self.connection_id = f"{user_id}_{session_id}" if user_id and session_id else None
        # ... existing init ...
        
    async def analyze_video_cancellable(self, video_path, view, user_id=None, session_id=None):
        """Video analysis with cancellation support"""
        connection_id = f"{user_id}_{session_id}"
        
        async with websockets.connect(uri) as websocket:
            # Register connection for potential cancellation
            if connection_id:
                active_websocket_connections[connection_id] = websocket
                
            try:
                # ... existing analysis logic ...
                
                while True:
                    # Check for cancellation
                    if self.is_cancelled(connection_id):
                        print(f"Analysis cancelled for {connection_id}")
                        break
                        
                    # ... frame processing ...
                    
            finally:
                # Cleanup connection
                if connection_id in active_websocket_connections:
                    del active_websocket_connections[connection_id]
                    
    def is_cancelled(self, connection_id):
        """Check if analysis should be cancelled"""
        # Check database or cancellation flags
        pass

def cancel_websocket_connections(user_id, session_id):
    """Cancel active WebSocket connections"""
    connection_id = f"{user_id}_{session_id}"
    if connection_id in active_websocket_connections:
        # Close WebSocket connection
        asyncio.create_task(active_websocket_connections[connection_id].close())
```

## Implementation Plan

### Phase 1: Database Status Checking (Immediate)
- Add cancellation checks in process_session_files
- Update delete functions to set status to "cancelled"
- Minimal code changes, immediate benefit

### Phase 2: Thread Tracking (Short-term)
- Implement thread tracking dictionary
- Add cancellation flags
- Enhanced control over running processes

### Phase 3: WebSocket Management (Long-term)
- Track and manage WebSocket connections
- Implement connection cancellation
- Complete resource cleanup

## Modified Delete Functions

```python
# Enhanced video delete function
@video_bp.route("/delete", methods=["POST"])
@jwt_required()
def delete_session():
    user_id = str(get_jwt_identity())
    data = request.get_json()
    session_id = data["session_id"]
    
    # Cancel any running analysis first
    cancel_analysis_processing(user_id, session_id)
    
    # Then delete files
    # ... existing file deletion logic ...

# Enhanced analysis delete function  
def delete_analysis(self, user_id, analysis_id):
    analysis = Analysis.query.filter_by(id=analysis_id, user_id=user_id).first()
    session_id = analysis.session_id
    
    # Cancel running processes first
    cancel_analysis_processing(user_id, session_id)
    
    # Then delete database record and files
    # ... existing deletion logic ...
```

## Benefits
- Prevents resource waste
- Eliminates race conditions
- Provides consistent system state
- Improves user experience
- Enables proper cleanup
