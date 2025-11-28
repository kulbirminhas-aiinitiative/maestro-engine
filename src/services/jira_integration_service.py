"""
JIRA Integration Service
Provides APIs to fetch, update, and manage JIRA Epics and Tasks.
"""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class IssueStatus(str, Enum):
    """JIRA Issue Status"""
    TODO = "To Do"
    IN_PROGRESS = "In Progress"
    DONE = "Done"


class IssueType(str, Enum):
    """JIRA Issue Types"""
    EPIC = "Epic"
    TASK = "Task"


class Priority(str, Enum):
    """JIRA Priority Levels"""
    HIGHEST = "Highest"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class JiraIntegrationService:
    """Service to manage JIRA integration using CSV backend"""
    
    def __init__(self, epics_csv_path: str, tasks_csv_path: str):
        self.epics_csv_path = Path(epics_csv_path)
        self.tasks_csv_path = Path(tasks_csv_path)
        self._epics_cache: Optional[List[Dict[str, Any]]] = None
        self._tasks_cache: Optional[List[Dict[str, Any]]] = None
    
    def _load_csv(self, csv_path: Path) -> List[Dict[str, Any]]:
        """Load CSV file and return list of dictionaries"""
        data = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data.append(dict(row))
            logger.info(f"Loaded {len(data)} records from {csv_path}")
        except Exception as e:
            logger.error(f"Error loading CSV {csv_path}: {e}")
            raise
        return data
    
    def _save_csv(self, csv_path: Path, data: List[Dict[str, Any]]) -> None:
        """Save data to CSV file"""
        if not data:
            logger.warning(f"No data to save to {csv_path}")
            return
        
        try:
            # Remove None keys and get fieldnames from original file
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                original_fieldnames = reader.fieldnames
            
            # Clean data - remove None keys
            cleaned_data = []
            for row in data:
                cleaned_row = {k: v for k, v in row.items() if k is not None and k in original_fieldnames}
                cleaned_data.append(cleaned_row)
            
            with open(csv_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=original_fieldnames, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(cleaned_data)
            logger.info(f"Saved {len(cleaned_data)} records to {csv_path}")
        except Exception as e:
            logger.error(f"Error saving CSV {csv_path}: {e}")
            raise
    
    def reload_data(self) -> None:
        """Reload data from CSV files"""
        self._epics_cache = self._load_csv(self.epics_csv_path)
        self._tasks_cache = self._load_csv(self.tasks_csv_path)
    
    @property
    def epics(self) -> List[Dict[str, Any]]:
        """Get all epics"""
        if self._epics_cache is None:
            self.reload_data()
        return self._epics_cache
    
    @property
    def tasks(self) -> List[Dict[str, Any]]:
        """Get all tasks"""
        if self._tasks_cache is None:
            self.reload_data()
        return self._tasks_cache
    
    def get_epic_by_id(self, epic_id: str) -> Optional[Dict[str, Any]]:
        """Get epic by ID (e.g., 'EPIC-1')"""
        for epic in self.epics:
            if epic.get('Summary', '').startswith(epic_id):
                return epic
        return None
    
    def get_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task by ID (e.g., 'P0')"""
        for task in self.tasks:
            if task.get('Summary', '').startswith(task_id):
                return task
        return None
    
    def list_epics(
        self, 
        status: Optional[IssueStatus] = None,
        priority: Optional[Priority] = None
    ) -> List[Dict[str, Any]]:
        """List epics with optional filtering"""
        results = self.epics
        
        if status:
            results = [e for e in results if e.get('Status') == status.value]
        
        if priority:
            results = [e for e in results if e.get('Priority') == priority.value]
        
        return results
    
    def list_tasks(
        self,
        status: Optional[IssueStatus] = None,
        priority: Optional[Priority] = None,
        epic_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List tasks with optional filtering"""
        results = self.tasks
        
        if status:
            results = [t for t in results if t.get('Status') == status.value]
        
        if priority:
            results = [t for t in results if t.get('Priority') == priority.value]
        
        if epic_id:
            # Filter tasks by labels that contain epic reference
            results = [t for t in results if epic_id.lower() in t.get('Labels', '').lower()]
        
        return results
    
    def update_epic_status(
        self, 
        epic_id: str, 
        status: IssueStatus,
        resolution: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update epic status"""
        for i, epic in enumerate(self._epics_cache):
            if epic.get('Summary', '').startswith(epic_id):
                epic['Status'] = status.value
                if resolution:
                    epic['Resolution'] = resolution
                self._save_csv(self.epics_csv_path, self._epics_cache)
                logger.info(f"Updated {epic_id} status to {status.value}")
                return epic
        
        raise ValueError(f"Epic {epic_id} not found")
    
    def update_task_status(
        self,
        task_id: str,
        status: IssueStatus,
        resolution: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update task status"""
        for i, task in enumerate(self._tasks_cache):
            if task.get('Summary', '').startswith(task_id):
                task['Status'] = status.value
                if resolution:
                    task['Resolution'] = resolution
                self._save_csv(self.tasks_csv_path, self._tasks_cache)
                logger.info(f"Updated {task_id} status to {status.value}")
                return task
        
        raise ValueError(f"Task {task_id} not found")
    
    def get_epic_tasks(self, epic_id: str) -> List[Dict[str, Any]]:
        """Get all tasks associated with an epic"""
        # Extract numeric ID from epic_id (e.g., 'EPIC-1' -> '1')
        try:
            epic_num = epic_id.split('-')[1]
            # Tasks are linked via labels or description
            return self.list_tasks(epic_id=epic_id)
        except Exception as e:
            logger.error(f"Error getting tasks for {epic_id}: {e}")
            return []
    
    def check_epic_completion(self, epic_id: str) -> bool:
        """Check if all tasks in an epic are done"""
        tasks = self.get_epic_tasks(epic_id)
        if not tasks:
            return False
        return all(task.get('Status') == IssueStatus.DONE.value for task in tasks)
    
    def get_todo_epics(self) -> List[Dict[str, Any]]:
        """Get all 'To Do' epics"""
        return self.list_epics(status=IssueStatus.TODO)
    
    def transition_to_in_progress(self, issue_id: str, issue_type: IssueType) -> Dict[str, Any]:
        """Transition an issue to 'In Progress'"""
        if issue_type == IssueType.EPIC:
            return self.update_epic_status(issue_id, IssueStatus.IN_PROGRESS)
        else:
            return self.update_task_status(issue_id, IssueStatus.IN_PROGRESS)
    
    def transition_to_done(
        self, 
        issue_id: str, 
        issue_type: IssueType,
        resolution: str
    ) -> Dict[str, Any]:
        """Transition an issue to 'Done'"""
        if issue_type == IssueType.EPIC:
            return self.update_epic_status(issue_id, IssueStatus.DONE, resolution)
        else:
            return self.update_task_status(issue_id, IssueStatus.DONE, resolution)
    
    def get_issue_summary(self, issue_id: str, issue_type: IssueType) -> Dict[str, Any]:
        """Get comprehensive issue summary"""
        if issue_type == IssueType.EPIC:
            epic = self.get_epic_by_id(issue_id)
            if not epic:
                raise ValueError(f"Epic {issue_id} not found")
            
            tasks = self.get_epic_tasks(issue_id)
            total_tasks = len(tasks)
            done_tasks = len([t for t in tasks if t.get('Status') == IssueStatus.DONE.value])
            
            return {
                "issue": epic,
                "type": "Epic",
                "tasks": tasks,
                "progress": {
                    "total": total_tasks,
                    "done": done_tasks,
                    "percentage": (done_tasks / total_tasks * 100) if total_tasks > 0 else 0
                }
            }
        else:
            task = self.get_task_by_id(issue_id)
            if not task:
                raise ValueError(f"Task {issue_id} not found")
            return {
                "issue": task,
                "type": "Task"
            }
