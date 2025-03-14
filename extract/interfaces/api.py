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

    def __init__(self, api_key: str, spreadsheet_id: str, sheet_ids: List[int], sheet_names: List[str]):
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
                **({'ranges': [f"'{sn}'!A:AZ" for sn in sheet_names]} if sheet_names else {})
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
            try:
                obj = Sheet.parse(sheet)
            except Exception as error:
                sheet_index = data['sheets'].index(sheet)
                raise Exception(f'Failed to parse sheet #{sheet_index}') from error

            if obj.id not in sheet_ids:
                continue

            try:
                obj.parse_data(sheet)
            except Exception as error:
                raise Exception(f'Failed to parse sheet "{obj.title}" ({obj.id})') from error

            self._sheets[obj.id] = obj

    class MissingAPIKey(Exception):
        ...

