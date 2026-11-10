import json
import logging
import os
from decimal import Decimal
from typing import List, Literal, Optional

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from tracker.models import Expense

logger = logging.getLogger(__name__)


class ExpenseOperation(BaseModel):
    action: Literal["CREATE", "UPDATE", "DELETE"]
    target_id: Optional[int] = Field(default=None, description="Used for UPDATE or DELETE, referencing existing expense ID")
    category: Optional[str] = Field(default=None, description="Food, Transport, Bills, Shopping, or Other")
    amount: Optional[float] = Field(default=None, description="Expense amount in numerical format")
    description: Optional[str] = Field(default=None, description="Concise description of the expense")


class ExpenseExtractionResult(BaseModel):
    operations: List[ExpenseOperation]


def get_recent_expenses_context() -> str:
    expenses = Expense.objects.all().order_by("-date")[:20]
    data = [
        {
            "id": exp.id,
            "category": exp.category,
            "amount": float(exp.amount),
            "description": exp.description,
            "date": exp.date.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for exp in expenses
    ]
    return json.dumps(data, indent=2)


def analyze_voice_expense(audio_file_path: str) -> ExpenseExtractionResult:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not configured.")

    client = genai.Client(api_key=api_key)
    uploaded_file = client.files.upload(file=audio_file_path)

    try:
        context = get_recent_expenses_context()
        system_instruction = (
            "You are an AI expense tracking assistant for AuraLedger.\n"
            "Your task is to analyze the user's voice recording and extract the intended expense operations.\n\n"
            "Recent Expenses Context (use for target_id references in UPDATE or DELETE operations):\n"
            f"{context}\n\n"
            "Operating Rules:\n"
            "1. For CREATE: Set action to 'CREATE'. Extract category (Food, Transport, Bills, Shopping, Other), amount, and description. Leave target_id null.\n"
            "2. For UPDATE: Match with an existing expense from the recent expenses context, set target_id to its ID, action to 'UPDATE', and provide the updated fields.\n"
            "3. For DELETE: Match with an existing expense from the recent context, set target_id to its ID and action to 'DELETE'.\n"
            "4. Standard categories are strictly: Food, Transport, Bills, Shopping, Other. Map variations to the closest valid choice.\n"
            "5. If multiple operations are dictated in one recording, capture each in the operations array."
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                uploaded_file,
                "Analyze this voice dictation and extract structured expense operations.",
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=ExpenseExtractionResult,
                temperature=0.1,
            ),
        )

        if response.parsed:
            return response.parsed
        return ExpenseExtractionResult.model_validate_json(response.text)

    finally:
        try:
            client.files.delete(name=uploaded_file.name)
        except Exception as cleanup_err:
            logger.warning("Failed to delete temporary Gemini file %s: %s", uploaded_file.name, cleanup_err)


def execute_expense_operations(extraction_result: ExpenseExtractionResult) -> list[dict]:
    results = []
    valid_categories = {c.value for c in Expense.Category}

    for op in extraction_result.operations:
        action = op.action.upper()
        try:
            if action == "CREATE":
                if op.amount is None:
                    continue
                raw_category = (op.category or "").strip().title()
                category = raw_category if raw_category in valid_categories else Expense.Category.OTHER
                description = (op.description or "Voice expense").strip()
                expense = Expense.objects.create(
                    amount=Decimal(f"{op.amount:.2f}"),
                    category=category,
                    description=description,
                )
                results.append({"action": "CREATE", "status": "success", "id": expense.id})

            elif action == "UPDATE" and op.target_id is not None:
                expense = Expense.objects.get(id=op.target_id)
                if op.amount is not None:
                    expense.amount = Decimal(f"{op.amount:.2f}")
                if op.category:
                    raw_category = op.category.strip().title()
                    expense.category = raw_category if raw_category in valid_categories else Expense.Category.OTHER
                if op.description:
                    expense.description = op.description.strip()
                expense.save()
                results.append({"action": "UPDATE", "status": "success", "id": expense.id})

            elif action == "DELETE" and op.target_id is not None:
                expense = Expense.objects.get(id=op.target_id)
                deleted_id = expense.id
                expense.delete()
                results.append({"action": "DELETE", "status": "success", "id": deleted_id})

            else:
                results.append({
                    "action": action,
                    "status": "skipped",
                    "message": f"Missing target_id for {action} operation."
                })

        except Expense.DoesNotExist:
            logger.warning("Expense with ID %s not found for action %s", op.target_id, action)
            results.append({
                "action": action,
                "status": "error",
                "message": f"Expense with ID {op.target_id} does not exist."
            })
        except Exception as e:
            logger.exception("Error executing operation %s on expense ID %s", action, op.target_id)
            results.append({
                "action": action,
                "status": "error",
                "message": str(e)
            })

    return results
