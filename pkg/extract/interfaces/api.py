# coding: utf-8
from typing import Dict, List

import requests

from ..classes import Sheet


class DataInterface:

    FIELDS = [
        'sheets.properties',
        'sheets.data.rowData.values.formattedValue',
        'sheets.data.rowData.values.effectiveFormat.textFormat.strikethrough',
        'sheets.data.rowData.values.hyperlink',
        'sheets.data.rowData.values.textFormatRuns.format.link',
        'sheets.data.rowData.values.note',
    ]

    def __init__(self, api_key: str, spreadsheet_id: str, sheet_ids: List[int]):
        if not api_key:
            raise self.MissingAPIKey(f'Google API key is required.')

        print('fetching spreadsheet via API...')
        resp = requests.get(
            url=f'https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}',
            headers={
                'X-Goog-Api-Key': api_key,
                'X-Goog-FieldMask': ','.join(self.FIELDS),
            },
            params={
                'prettyPrint': False,
            },
        )
        resp.raise_for_status()

        data = resp.json()

        if error := data.get('error'):
            code = error.pop('code', None)
            status = error.pop('status', None)
            message = error.pop('message', None)
            reason = error.get('details', {}).pop('reason', None)
            print(code, status, message, reason, error)
            return

        self._sheets: Dict[int, Sheet] = {}
        for sheet in data['sheets']:
            obj = Sheet.parse(sheet)
            if obj.id not in sheet_ids:
                continue
            obj.parse_data(sheet)
            self._sheets[obj.id] = obj

    def get_sheet(self, sheet_id: int):
        return self._sheets[sheet_id]

    class MissingAPIKey(Exception):
        ...

