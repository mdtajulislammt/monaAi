"""Self-learning Reflection Engine for JARVIS.

Intercepts execution failures, logs errors, synthesizes root causes,
persists dynamic fixes into ChromaDB, and injects past reflections
into the agent's prompt to avoid repeating mistakes.
"""
import datetime
import hashlib
import logging
import re
from typing import Any, Dict, List, Optional

from memory.vector_store import ChromaMemoryManager, get_memory_manager

logger = logging.getLogger(__name__)

COLLECTION_REFLECTIONS = "jarvis_reflections"


class ExecutionReflectionEngine:
    """Automated execution reflection loop for self-learning agent runtime."""

    def __init__(self, memory_manager: Optional[ChromaMemoryManager] = None):
        self.memory = memory_manager or get_memory_manager()
        self._col = self.memory.get_collection(COLLECTION_REFLECTIONS)

    def _diagnose_error(self, error_message: str) -> Dict[str, str]:
        """Categorize error and suggest practical mitigation based on pattern matching."""
        err_lower = error_message.lower()

        if "command not found" in err_lower or "not recognized as an internal or external command" in err_lower:
            return {
                "category": "CommandNotFound",
                "diagnosis": "The requested binary or command is not installed or not in PATH.",
                "mitigation": "Check which binary is installed or install the package via package manager (e.g. apt or pip).",
            }
        elif "permission denied" in err_lower or "access is denied" in err_lower:
            return {
                "category": "PermissionDenied",
                "diagnosis": "The command or file access was denied due to insufficient user privileges or file permissions.",
                "mitigation": "Verify file permissions or choose a user-accessible path rather than protected system locations.",
            }
        elif "timed out" in err_lower or "timeout" in err_lower:
            return {
                "category": "Timeout",
                "diagnosis": "Command exceeded timeout boundary.",
                "mitigation": "Run command with optimized flags or execute asynchronously without blocking.",
            }
        elif "no such file or directory" in err_lower or "file not found" in err_lower:
            return {
                "category": "FileNotFound",
                "diagnosis": "The target path or required file does not exist.",
                "mitigation": "Inspect the parent directory or verify path existence before executing.",
            }
        elif "security policy violation" in err_lower or "blocked" in err_lower:
            return {
                "category": "SecurityViolation",
                "diagnosis": "The command or path was blocked by JARVIS safety rules.",
                "mitigation": "Use safe, non-destructive commands within authorized workspace paths.",
            }
        elif "modulenotfounderror" in err_lower or "no module named" in err_lower:
            match = re.search(r"no module named ['\"]([^'\"]+)['\"]", err_lower)
            module = match.group(1) if match else "unknown"
            return {
                "category": "MissingDependency",
                "diagnosis": f"Python dependency '{module}' is missing in the current virtualenv.",
                "mitigation": f"Install required dependency using: pip install {module}",
            }
        else:
            return {
                "category": "ExecutionError",
                "diagnosis": "The execution returned a non-zero exit code or error output.",
                "mitigation": "Examine the error output closely, adjust arguments, and try an alternative approach.",
            }

    def log_execution(
        self,
        action: str,
        success: bool,
        output: str = "",
        error: str = "",
        context: str = "",
    ) -> Optional[str]:
        """Log tool execution result. If failed, synthesize reflection and store in vector memory."""
        if success and not error:
            logger.debug(f"Action '{action}' succeeded cleanly.")
            return None

        # Analyze error
        diagnosis = self._diagnose_error(error or output)
        timestamp = datetime.datetime.now().isoformat()
        reflection_doc = (
            f"ACTION: {action}\n"
            f"ERROR_CATEGORY: {diagnosis['category']}\n"
            f"ERROR: {error or output}\n"
            f"DIAGNOSIS: {diagnosis['diagnosis']}\n"
            f"RECOMMENDED_FIX: {diagnosis['mitigation']}\n"
            f"CONTEXT: {context}"
        )

        doc_id = f"ref_{diagnosis['category']}_{int(datetime.datetime.now().timestamp())}"
        metadata = {
            "type": "execution_reflection",
            "category": diagnosis["category"],
            "action": action[:100],
            "success": False,
            "timestamp": timestamp,
        }

        try:
            stored_id = self.memory.upsert_document(
                collection_name=COLLECTION_REFLECTIONS,
                document=reflection_doc,
                metadata=metadata,
                doc_id=doc_id,
            )
            logger.info(f"Learned reflection stored ({stored_id}) for action '{action}'")
            return stored_id
        except Exception as e:
            logger.error(f"Failed to persist reflection to ChromaDB: {e}")
            return None

    def record_learned_fix(
        self,
        action: str,
        error_encountered: str,
        working_fix: str,
    ) -> str:
        """Explicitly record a verified solution to a previously encountered problem."""
        timestamp = datetime.datetime.now().isoformat()
        doc = (
            f"ACTION: {action}\n"
            f"PAST_ERROR: {error_encountered}\n"
            f"VERIFIED_FIX: {working_fix}\n"
            f"STATUS: SOLVED"
        )
        metadata = {
            "type": "verified_fix",
            "action": action[:100],
            "success": True,
            "timestamp": timestamp,
        }
        doc_id = f"fix_{hashlib.sha256(action.encode()).hexdigest()[:8]}_{int(datetime.datetime.now().timestamp())}"
        return self.memory.upsert_document(
            collection_name=COLLECTION_REFLECTIONS,
            document=doc,
            metadata=metadata,
            doc_id=doc_id,
        )

    def retrieve_relevant_reflections(
        self,
        action_or_query: str,
        n_results: int = 3,
    ) -> List[Dict[str, Any]]:
        """Retrieve past failure reflections and learned fixes relevant to an upcoming action."""
        return self.memory.query_similar(
            collection_name=COLLECTION_REFLECTIONS,
            query_text=action_or_query,
            n_results=n_results,
        )

    def format_reflection_prompt(self, action_or_query: str) -> str:
        """Format relevant past reflections into a prompt section for the LLM."""
        reflections = self.retrieve_relevant_reflections(action_or_query, n_results=3)
        if not reflections:
            return ""

        formatted_items = []
        for r in reflections:
            doc = r["document"]
            formatted_items.append(f"• {doc}")

        return (
            "⚠️ PAST EXECUTION LESSONS & SELF-CORRECTIONS (Avoid Repeating These Mistakes):\n"
            + "\n---\n".join(formatted_items)
            + "\n"
        )


_reflection_engine_instance: Optional[ExecutionReflectionEngine] = None


def get_reflection_engine() -> ExecutionReflectionEngine:
    """Get or create singleton ExecutionReflectionEngine instance."""
    global _reflection_engine_instance
    if _reflection_engine_instance is None:
        _reflection_engine_instance = ExecutionReflectionEngine()
    return _reflection_engine_instance
