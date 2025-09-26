import json
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.config import config
from app.google_export.exc import GSheetReadError, GSheetWriteError


def _is_retryable_error(e: BaseException) -> bool:
    """Return True, if the exception is an API temporary error."""
    if isinstance(e, TimeoutError):
        return True
    if isinstance(e, HttpError):
        return e.status_code in [429, 500, 503]
    return False


class GSpreadsheetAPI:
    def __init__(self, sheet_id: str = config.G_SPREADSHEET_ID, creds: str = config.G_SPREADSHEET_CREDS):
        self._sheet_id = sheet_id
        creds = creds.replace("\n", "\\n")
        service = build(
            "sheets",
            "v4",
            credentials=Credentials.from_service_account_info(
                info=json.loads(creds),
                scopes=["https://www.googleapis.com/auth/spreadsheets"],
            ),
        )
        self._sheet = service.spreadsheets()

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception(_is_retryable_error),
        reraise=True,
    )
    def read_sheet(self, tab_name: str, cell_range: str, sheet_id: str | None = None) -> list[list[Any]]:
        target_sheet_id = sheet_id or self._sheet_id
        if not target_sheet_id:
            raise ValueError("Sheet ID must be provided either during initialization or method call.")
        try:
            data = (
                self._sheet.values()
                .get(
                    spreadsheetId=target_sheet_id,
                    range=f"{tab_name}!{cell_range}",
                    valueRenderOption="UNFORMATTED_VALUE",
                )
                .execute()
            )
            return data.get("values", [])
        except (HttpError, TimeoutError) as e:
            raise GSheetReadError(
                f"Failed to read the data from the tab '{tab_name}', sheet ID '{target_sheet_id}'."
            ) from e

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception(_is_retryable_error),
        reraise=True,
    )
    def write_to_sheet(
        self, values: list[list[Any]], tab_name: str, start_cell: str, sheet_id: str | None = None
    ) -> dict:
        """Write down the values into the Google table with retrying attempts for temporary exceptions."""
        target_sheet_id = sheet_id or self._sheet_id
        if not target_sheet_id:
            raise ValueError("Sheet ID must be provided either during initialization or method call.")
        body = {"values": values}
        try:
            result = (
                self._sheet.values()
                .update(
                    spreadsheetId=target_sheet_id,
                    range=f"{tab_name}!{start_cell}",
                    valueInputOption="USER_ENTERED",
                    body=body,
                )
                .execute()
            )
            return result
        except (HttpError, TimeoutError) as e:
            raise GSheetWriteError(
                f"Failed to write the data to the tab '{tab_name}', sheet ID '{target_sheet_id}'."
            ) from e


gsheets = GSpreadsheetAPI()
