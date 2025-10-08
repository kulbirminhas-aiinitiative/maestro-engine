#!/usr/bin/env python3
"""
Parallel Execution Enhancement for MAESTRO Engine

Enables true parallel execution for personas with the same priority tier.
"""

import asyncio
from collections import defaultdict
from typing import Any, Dict, List


class ParallelExecutionMixin:
    """
    Mixin to add parallel execution capabilities to the workflow engine.

    Personas with the same priority tier execute in parallel using asyncio.gather()
    """

    def _group_by_priority(self, personas: List[str]) -> Dict[int, List[str]]:
        """
        Group personas by priority tier for parallel execution

        Example:
            Input: ["backend_developer", "database_specialist", "frontend_developer"]
            Output: {
                4: ["backend_developer", "database_specialist"],  # Parallel
                5: ["frontend_developer"]
            }
        """
        priority_tiers = {
            "requirement_analyst": 1,
            "solution_architect": 2,
            "security_specialist": 3,
            "backend_developer": 4,
            "database_specialist": 4,
            "frontend_developer": 5,
            "ui_ux_designer": 5,
            "unit_tester": 6,
            "integration_tester": 7,
            "devops_engineer": 8,
            "technical_writer": 9,
        }

        grouped = defaultdict(list)
        for persona in personas:
            priority = priority_tiers.get(persona, 999)
            grouped[priority].append(persona)

        return dict(sorted(grouped.items()))

    async def execute_with_parallelism(
        self, requirement: str, session_id: str = None, resume_session_id: str = None
    ) -> Dict[str, Any]:
        """
        Execute workflow with parallel execution for same-priority personas

        Flow:
        1. Group personas by priority tier
        2. Execute each tier sequentially
        3. Within each tier, execute personas in PARALLEL
        """

        # Load or create session (same as before)
        if resume_session_id:
            session = self.session_manager.load_session(resume_session_id)
            requirement = session.requirement
        else:
            session = self.session_manager.create_session(
                requirement=requirement, output_dir=self.output_dir, session_id=session_id
            )

        # Determine pending personas
        pending_personas = [
            p for p in self.selected_personas if p not in session.completed_personas
        ]

        if not pending_personas:
            return {"success": True, "message": "All personas completed"}

        # Group by priority for parallel execution
        priority_groups = self._group_by_priority(pending_personas)

        print("=" * 80)
        print("🚀 PARALLEL EXECUTION MODE")
        print("=" * 80)
        print(f"📝 Requirement: {requirement[:100]}...")
        print(f"🆔 Session: {session.session_id}")
        print(f"✅ Already completed: {', '.join(session.completed_personas) or 'None'}")

        # Show execution plan
        print("\n📋 Execution Plan:")
        for priority, personas in priority_groups.items():
            if len(personas) > 1:
                print(f"   Tier {priority}: {', '.join(personas)} (PARALLEL ⚡)")
            else:
                print(f"   Tier {priority}: {personas[0]}")
        print("=" * 80 + "\n")

        start_time = datetime.now()

        # Execute each priority tier
        for priority, personas_in_tier in priority_groups.items():
            print(f"\n{'='*80}")
            print(f"⚡ TIER {priority}: Executing {len(personas_in_tier)} persona(s)")
            if len(personas_in_tier) > 1:
                print(f"   Running in PARALLEL: {', '.join(personas_in_tier)}")
            print("=" * 80)

            # Execute all personas in this tier in PARALLEL
            tasks = [
                self._execute_persona(persona_id, requirement, session)
                for persona_id in personas_in_tier
            ]

            # Wait for all personas in this tier to complete
            persona_contexts = await asyncio.gather(*tasks)

            # Save results from all parallel executions
            for persona_id, persona_context in zip(personas_in_tier, persona_contexts):
                session.add_persona_execution(
                    persona_id=persona_id,
                    files_created=persona_context.files_created,
                    deliverables=persona_context.deliverables,
                    duration=persona_context.duration(),
                    success=persona_context.success,
                )

                if persona_context.success:
                    print(f"   ✅ {persona_id}: {len(persona_context.files_created)} files")
                else:
                    print(f"   ❌ {persona_id}: {persona_context.error}")

            # Persist session after each tier
            self.session_manager.save_session(session)

            print(f"✅ Tier {priority} complete\n")

        # Build final result
        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds()

        result = {
            "success": True,
            "session_id": session.session_id,
            "requirement": requirement,
            "executed_personas": pending_personas,
            "all_completed_personas": session.completed_personas,
            "files": session.get_all_files(),
            "file_count": len(session.get_all_files()),
            "project_dir": str(self.output_dir),
            "total_duration": total_duration,
            "parallel_execution": True,
            "priority_groups": {f"tier_{p}": personas for p, personas in priority_groups.items()},
        }

        # Index to RAG Writer (same as before)
        quality_score = self.rag.calculate_quality_score(
            success=result["success"],
            files_generated=result["files"],
            personas_count=len(result["all_completed_personas"]),
            execution_time=total_duration,
        )

        rag_task_id = self.rag.index_workflow_execution(
            session_id=result["session_id"],
            requirement=requirement,
            personas=result["all_completed_personas"],
            collaterals=[{"path": f, "type": "file"} for f in result["files"]],
            quality_score=quality_score,
            success=result["success"],
            execution_time=total_duration,
        )

        if rag_task_id:
            result["rag_indexed"] = True
            result["rag_task_id"] = rag_task_id
            result["quality_score"] = quality_score

        print("\n" + "=" * 80)
        print("📊 PARALLEL EXECUTION SUMMARY")
        print("=" * 80)
        print(f"✅ Success: {result['success']}")
        print(f"🆔 Session: {result['session_id']}")
        print(f"👥 Total Personas: {len(pending_personas)}")
        print(f"⚡ Priority Tiers: {len(priority_groups)}")
        print(f"📁 Files Created: {result['file_count']}")
        print(f"⏱️  Duration: {total_duration:.2f}s")
        print("=" * 80)

        return result


# Example usage pattern
"""
# Inherit the mixin
class AutonomousSDLCEngineV3Parallel(
    ParallelExecutionMixin,
    AutonomousSDLCEngineV3Resumable
):
    pass

# Use parallel execution
engine = AutonomousSDLCEngineV3Parallel(
    selected_personas=[
        "backend_developer",
        "database_specialist",    # Same tier - will run in parallel
        "frontend_developer",
        "ui_ux_designer"         # Same tier - will run in parallel
    ]
)

result = await engine.execute_with_parallelism(
    requirement="Build full-stack application"
)

# Output:
# ⚡ TIER 4: Executing 2 persona(s)
#    Running in PARALLEL: backend_developer, database_specialist
#    ✅ backend_developer: 8 files
#    ✅ database_specialist: 3 files
# ✅ Tier 4 complete
#
# ⚡ TIER 5: Executing 2 persona(s)
#    Running in PARALLEL: frontend_developer, ui_ux_designer
#    ✅ frontend_developer: 12 files
#    ✅ ui_ux_designer: 5 files
# ✅ Tier 5 complete
"""
