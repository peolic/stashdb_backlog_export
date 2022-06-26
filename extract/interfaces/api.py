# coding: utf-8
import json
from typing import List

import requests

from ..classes import Sheet
from .base import InterfaceBase


class DataInterface(InterfaceBase[Sheet]):

    FIELDS = [
        'sheets.properties',
        'sheets.data.rowData.values.formattedValue',
        'sheets.data.rowData.values.effectiveFormat.textFormat.strikethrough',
        'sheets.data.rowData.values.hyperlink',
        'sheets.data.rowData.values.textFormatRuns.format.link',
        'sheets.data.rowData.values.textFormatRuns.format.strikethrough',
        'sheets.data.rowData.values.textFormatRuns.startIndex',
        'sheets.data.rowData.values.note',
    ]

    def __init__(self, api_key: str, spreadsheet_id: str, sheet_ids: List[int]):
        super(DataInterface, self).__init__()

        if not api_key:
            raise self.MissingAPIKey(f'Google API key is required.')

        print('fetching spreadsheet via API...')
        resp = requests.get(
            url=f'https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}',
            headers={
                'User-Agent': 'Backlog Exporter (gzip)',
                'Accept-Encoding': 'gzip',
                'X-Goog-Api-Key': api_key,
                'X-Goog-FieldMask': ','.join(self.FIELDS),
            },
            params={
                'prettyPrint': False,
            },
        )

        try:
            data = resp.json()
        except ValueError:
            data = {}

        if error := data.get('error'):
            for key in ('code', 'status', 'message',):
                print(f'{key}={error.pop(key, None)}')
            if details := error.pop('details', []):
                print(f'details={json.dumps(details, indent=2)}')
            if error:
                print(error)

        if not resp.ok:
            details = '.' if data else f': {resp.text}'
            raise Exception('Request failed' + details)


        for sheet in data['sheets']:
            obj = Sheet.parse(sheet)
            if obj.id not in sheet_ids:
                continue
            obj.parse_data(sheet)
            self._sheets[obj.id] = obj

    class MissingAPIKey(Exception):
        ...

