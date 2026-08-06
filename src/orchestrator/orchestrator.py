"""Top-level orchestrator that coordinates all existing modules.

``AssessmentOrchestrator`` is the single entry point for processing a user
question. It classifies the intent, routes to the appropriate pipeline,
collects intermediate results, and returns a validated ``AssessmentResponse``.
"""

from __future__ import annotations

from src.core.input_validation import validate_question
from src.core.logger import get_logger
from src.rag.retriever import retrieve
from src.response_generator.generator import generate
from src.routing.intent_classifier import classify
from src.schemas.response import AssessmentResponse
from src.schemas.intent import IntentClassification
from src.sql.executor import execute
from src.sql.planner import plan

logger = get_logger(__name__)

_OUT_OF_DOMAIN_MESSAGE: str = (
    "I'm sorry, but this question cannot be answered from the available "
    "retail sales data. Please ask a question related to the available "
    "datasets, such as sales figures, trends, comparisons, or explanations."
)


class AssessmentOrchestrator:
    """Coordinates the question-answering pipeline by delegating to existing
    specialised modules.

    The orchestrator does not contain SQL generation, retrieval, prompt
    engineering, or LLM implementation details. It only routes execution.
    """

    def __init__(self) -> None:
        logger.info("AssessmentOrchestrator initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, question: str) -> AssessmentResponse:
        """Process a user question end-to-end.

        Steps:
            1. Classify intent via the existing classifier.
            2. Route to the appropriate pipeline based on intent.
            3. Return a validated ``AssessmentResponse``.

        Args:
            question: The user's natural-language question.

        Returns:
            A validated ``AssessmentResponse`` instance.
        """
        question = validate_question(question)

        logger.info("Processing question", extra={"q_len": len(question)})

        intent_result: IntentClassification = classify(question)
        intent: str = intent_result.intent

        logger.info("Intent determined", extra={"intent": intent})

        if intent == "OUT_OF_DOMAIN":
            return self._handle_out_of_domain()
        if intent == "WHAT":
            return self._handle_what(question)
        if intent == "WHY":
            return self._handle_why(question)
        if intent == "WHAT_TO_DO":
            return self._handle_what_to_do(question)

        raise RuntimeError(f"Unknown intent: {intent}")

    # ------------------------------------------------------------------
    # Intent-specific pipelines
    # ------------------------------------------------------------------

    def _handle_what(self, question: str) -> AssessmentResponse:
        """Pipeline for WHAT intent: SQL only.

        Args:
            question: The user question.

        Returns:
            An ``AssessmentResponse`` with status ``OK``.
        """
        logger.info("Executing WHAT pipeline")

        sql = plan(question)
        rows = execute(sql)

        return self._generate_response(
            question=question,
            intent="WHAT",
            sql_results=rows,
            documents=None,
            status="OK",
        )

    def _handle_why(self, question: str) -> AssessmentResponse:
        """Pipeline for WHY intent: SQL + document retrieval.

        Args:
            question: The user question.

        Returns:
            An ``AssessmentResponse`` with status ``OK``.
        """
        logger.info("Executing WHY pipeline")

        sql = plan(question)
        rows = execute(sql)
        docs = retrieve(question)

        return self._generate_response(
            question=question,
            intent="WHY",
            sql_results=rows,
            documents=docs,
            status="OK",
        )

    def _handle_what_to_do(self, question: str) -> AssessmentResponse:
        """Pipeline for WHAT_TO_DO intent: SQL + document retrieval, always
        pending approval.

        Args:
            question: The user question.

        Returns:
            An ``AssessmentResponse`` with status ``PENDING_APPROVAL``.
        """
        logger.info("Executing WHAT_TO_DO pipeline")

        sql = plan(question)
        rows = execute(sql)
        docs = retrieve(question)

        return self._generate_response(
            question=question,
            intent="WHAT_TO_DO",
            sql_results=rows,
            documents=docs,
            status="PENDING_APPROVAL",
        )

    def _handle_out_of_domain(self) -> AssessmentResponse:
        """Pipeline for OUT_OF_DOMAIN intent: immediate abstention.

        No SQL, no retrieval, no LLM call.

        Returns:
            An ``AssessmentResponse`` with status ``ABSTAINED``.
        """
        logger.info("Executing OUT_OF_DOMAIN pipeline")

        return AssessmentResponse(
            answer=_OUT_OF_DOMAIN_MESSAGE,
            intent="OUT_OF_DOMAIN",
            citations=[],
            confidence=1.0,
            status="ABSTAINED",
        )

    # ------------------------------------------------------------------
    # Final response generation
    # ------------------------------------------------------------------

    def _generate_response(
        self,
        question: str,
        intent: str,
        sql_results: list[dict[str, object]] | None = None,
        documents: list[dict[str, object]] | None = None,
        status: str = "OK",
    ) -> AssessmentResponse:
        """Generate the final answer by calling the response generator.

        Args:
            question: The original user question.
            intent: The classified intent.
            sql_results: Rows returned by the SQL executor.
            documents: Documents returned by the retriever.
            status: The response status (``OK`` or ``PENDING_APPROVAL``).

        Returns:
            A validated ``AssessmentResponse``.
        """
        return generate(
            question=question,
            intent=intent,
            sql_rows=sql_results,
            documents=documents,
            status=status,
        )


def main() -> None:
    """Manual test: run the orchestrator with sample questions."""
    test_questions = [
        ("What were GlucoJoy sales in Delhi?", "WHAT"),
        ("Why did SparkClean sales decline?", "WHY"),
        ("What should we do to improve GlucoJoy sales?", "WHAT_TO_DO"),
        ("Who won the IPL last season?", "OUT_OF_DOMAIN"),
    ]

    orchestrator = AssessmentOrchestrator()

    for question, expected_intent in test_questions:
        print(f"\n{'='*70}")
        print(f"QUESTION: {question}")
        print(f"EXPECTED INTENT: {expected_intent}")
        print(f"{'='*70}")

        try:
            response = orchestrator.process(question)
            print(f"INTENT:     {response.intent}")
            print(f"STATUS:     {response.status}")
            print(f"ANSWER:     {response.answer[:200]}...")
            print(f"CITATIONS:  {response.citations}")
            print(f"CONFIDENCE: {response.confidence}")
        except Exception as exc:
            print(f"ERROR: {exc}")


if __name__ == "__main__":
    main()